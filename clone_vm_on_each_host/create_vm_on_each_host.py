'''
Copyright 2013-2014 Reubenur Rahman
All Rights Reserved
@author: reuben.13@gmail.com
'''

import atexit
import time
import logging
import ConfigParser

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect
from reconfigure_vnics import ReconfigureVNics

class CreateVM:
    def __init__(self):
        config = ConfigParser.RawConfigParser()
        #Read the ovs.ini file and collect all the credentials and required params
        config.read('ovs2.ini')
        self.settings = {
            'vcenter_ip' : config.get('vmware', 'vcenter_ip'),
            'vcenter_username' : config.get('vmware', 'vcenter_username'),
            'vcenter_password' : config.get('vmware', 'vcenter_password'),
            'datacenter' : config.get('vmware', 'datacenter'),
            'clusters' : config.get('vmware', 'clusters').split(','),
            'skip_hosts' : config.get('vmware', 'skip_hosts').split(','),
            'template_name' : config.get('template', 'template_name'),
            'vm_name' : config.get('template', 'vm_name'),
            'domain' : config.get('network', 'domain')}
        self.portgroups = config.get('network', 'port_groups').split(',')
        self.nic_type = config.get('network', 'nic_type')
        if self.nic_type == "pcnet":
            self.nic_type = vim.vm.device.VirtualPCNet32()
        elif self.nic_type == "e1000":
            self.nic_type = vim.vm.device.VirtualE1000()
        elif self.nic_type == "vmxnet2":
            self.nic_type = vim.vm.device.VirtualVmxnet2()
        elif self.nic_type == "vmxnet3":
            self.nic_type = vim.vm.device.VirtualVmxnet3()
        else:
            self.nic_type = vim.vm.device.VirtualPCNet32()
        
        logLevel = config.get('logger', 'log_level')
        log_file = config.get('logger', 'log_file')
        
        if logLevel == 'DEBUG':
            log_level = logging.DEBUG
        elif logLevel == 'INFO':
            log_level = logging.INFO
        else:
            log_level = logging.WARN
            
        self.logger = logging.getLogger('vmcreation')
        hdlr = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr) 
        self.logger.setLevel(log_level)  

    def wait_for_task(self, task, actionName='job', hideResult=False):
        """
        Waits and provides updates on a vSphere task
        """
        
        while task.info.state == vim.TaskInfo.State.running:
            time.sleep(2)
        
        if task.info.state == vim.TaskInfo.State.success:
            if task.info.result is not None and not hideResult:
                out = '%s completed successfully, result: %s' % (actionName, task.info.result)
                self.logger.info(out)
            else:
                out = '%s completed successfully.' % actionName
                self.logger.info(out)
        else:
            out = '%s did not complete successfully: %s' % (actionName, task.info.error)
            raise task.info.error
            self.logger.info(out)
        
        return task.info.result
   
    def get_obj(self, content, vimtype, name):
        """
        Get the vsphere object associated with a given text name
        """
        obj = None
        container = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
        for c in container.view:
            if c.name == name:
                obj = c
                break
        return obj


    def __connect_to_vcenter(self):
        """
        Connect to Vcenter Server with specified credentials
        @return: Service Instance
        """
        self.logger.info("Trying to connect to Vcenter Server %s" % self.settings['vcenter_ip'])
        si = None
        try:
            si = connect.Connect(self.settings['vcenter_ip'], 443, self.settings['vcenter_username'], self.settings['vcenter_password'], service="hostd")
        except IOError, e:
            pass
        if not si:
            self.logger.error("Could not connect to the specified Vcenter Server using the specified username %s and password %s" % (self.settings['vcenter_username'], self.settings['vcenter_password']))
            return -1
        self.logger.info("Connected to Vcenter Server %s" % self.settings['vcenter_ip'])
        atexit.register(Disconnect, si)
        return si

    def create_vm(self):
        """
        Manage and collect data for cloning and configuring VM from template
        """
        try:
            si = self.__connect_to_vcenter()

            content = si.RetrieveContent()

            datacenter = self.get_obj(content, [vim.Datacenter], self.settings['datacenter'])
            # get the folder where VMs are kept for this datacenter
            vmFolder = datacenter.vmFolder
            template_vm = self.get_obj(content, [vim.VirtualMachine], self.settings['template_name'])
            vm_name = self.settings['vm_name']
            clusters = self.settings['clusters']
            devices = []
            

            for cluster_name in clusters:
                cluster_obj = self.get_obj(content, [vim.ClusterComputeResource], cluster_name)
                hosts = cluster_obj.host
                all_hosts = []
                for host_system in hosts:
                    all_hosts.append(host_system.name)
                skip_hosts = self.settings['skip_hosts']
                #Skip the hosts on which we don't want to deploy VM
                available_hosts = [h for h in all_hosts if h not in skip_hosts]
                
                for host_name in available_hosts:
                    host = self.get_obj(content, [vim.HostSystem], host_name)
                    datastores = host.datastore
                    relospec = vim.vm.RelocateSpec()
                    
                    for datastore in datastores:
                        #Storing the VM in local datastore of each host
                        if datastore.summary.type == 'VMFS':
                            self.logger.debug("Storing the VM in %s" % datastore.name)
                            relospec.datastore = datastore
                            break

                    relospec.host = host
                    relospec.pool = cluster_obj.resourcePool
                    network_list = []
                    networks = host.network
                    for network in networks:
                        network_list.append(network.name)

                    port_groups = self.portgroups

                    nic_nets = [pg for pg in network_list if pg in port_groups]

                    for device in template_vm.config.hardware.device:
                        if isinstance(device, vim.vm.device.VirtualEthernetCard):
                            self.logger.error("Please remove all NICs from template before cloning")


                    actual_vm_name = vm_name+"_"+host.name
           
                    cloneSpec = vim.vm.CloneSpec(powerOn=True, template=False, location=relospec)

                    self.logger.debug("Cloning and creating VM %s" % actual_vm_name)
                    task = template_vm.Clone(name=actual_vm_name, folder=vmFolder, spec=cloneSpec)
                    job_status = self.wait_for_task(task, si)
                    
		    #We can easily add the nic configuration specs with clonespec but intentionally I am 
		    #configuring the NICs in a separate job
                    if job_status:
                        self.logger.info("Cloning and creating VM %s" % actual_vm_name)
                        ReconfigureVNics(self.logger).configure_vnics(si, content, actual_vm_name, nic_nets, self.nic_type)
                    else:
                        self.logger.error("Error occured while cloning VM. Couldn't reconfigure NICs")
                    del nic_nets[:]
  
        except vmodl.MethodFault, e:

            self.logger.error("Caught vmodl fault: %s" % e.msg)
            return 1
        except Exception, e:

            self.logger.error("Caught exception: %s" % str(e))
            return 1

        self.logger.info("Finished all tasks successfully")
        return 0
#END
