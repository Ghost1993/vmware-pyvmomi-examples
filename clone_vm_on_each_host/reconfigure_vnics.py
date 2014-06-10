'''
Copyright 2013-2014 Reubenur Rahman
All Rights Reserved
@author: reuben.13@gmail.com
'''
import time
from pyVmomi import vim, vmodl

class ReconfigureVNics:
    def __init__(self, logger):
        self.logger = logger

    def wait_for_task(self, task, actionName='job', hideResult=False):
        #print 'Waiting for %s to complete.' % actionName
        
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
            self.logger.info(out)
            raise task.info.error # should be a Fault... check XXX
        
        # may not always be applicable, but can't hurt.
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
     
    def configure_vnics(self, si, content, ovs_vm_name, nic_nets, nic_type):
        devices = []
        try:
            self.logger.debug("Configuring NICs for VM %s" % ovs_vm_name)
            vm = self.get_obj(content, [vim.VirtualMachine], ovs_vm_name)
            for net_name in nic_nets:
                nicspec = vim.vm.device.VirtualDeviceSpec()
                nicspec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
                nicspec.device = nic_type
                nicspec.device.wakeOnLanEnabled = True
                nicspec.device.deviceInfo = vim.Description()
		
		#Configuration for DVPortgroups
                pg_obj = self.get_obj(content, [vim.dvs.DistributedVirtualPortgroup], net_name)
                dvs_port_connection = vim.dvs.PortConnection()
                dvs_port_connection.portgroupKey= pg_obj.key
                dvs_port_connection.switchUuid= pg_obj.config.distributedVirtualSwitch.uuid
                nicspec.device.backing = vim.vm.device.VirtualEthernetCard.DistributedVirtualPortBackingInfo()
                nicspec.device.backing.port = dvs_port_connection
                #Configuration for Standard switch port groups
		#nicspec.device.backing = vim.vm.device.VirtualEthernetCard.NetworkBackingInfo()
		#nicspec.device.backing.network = self.get_obj(content, [vim.Network], net_name)
		#nicspec.device.backing.deviceName = net_name

                nicspec.device.connectable = vim.vm.device.VirtualDevice.ConnectInfo()
                nicspec.device.connectable.startConnected = True
                nicspec.device.connectable.allowGuestControl = True
                                                                   
                devices.append(nicspec)
             
            vmconf = vim.vm.ConfigSpec(deviceChange=devices)
            
            task = vm.ReconfigVM_Task(vmconf)
            # Wait for Network Reconfigure to complete
            self.wait_for_task(task, si)        
                          
        except vmodl.MethodFault, e:
            self.logger.error("Caught vmodl fault: %s" % e.msg)
            return 1
        except Exception, e:
            self.logger.error("Caught exception: %s" % str(e))
            return 1
        
