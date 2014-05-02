'''
Created on Apr 14, 2014

@author: reuben.13@gmail.com
© Reubenur Rahman
'''
import atexit
import argparse
import sys
import time

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect

def GetArgs():
    """
    Supports the command-line arguments listed below.
    """
    parser = argparse.ArgumentParser(description='Process args for retrieving all the Virtual Machines')
    parser.add_argument('-s', '--host', required=True, action='store', help='Vcenter Server IP to connect to')
    parser.add_argument('-o', '--port', type=int, default=443,   action='store', help='Port to connect on')
    parser.add_argument('-u', '--user', required=True, action='store', help='User name to use when connecting to Vcenter')
    parser.add_argument('-p', '--password', required=True, action='store', help='Password to use when connecting to Vcenter')
    parser.add_argument('-d', '--dest', required=True, action='store', help='Destination host name to migrate')
    parser.add_argument('-v', '--vm', required=True, action='store', help='Virtual Machine name to migrate')
    args = parser.parse_args()
    return args

def get_obj(content, vimtype, name):
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

def WaitTask(task, actionName='job', hideResult=False):
    """
    Waits and provides updates on a vSphere task
    """
    
    while task.info.state == vim.TaskInfo.State.running:
        time.sleep(2)
    
    if task.info.state == vim.TaskInfo.State.success:
        if task.info.result is not None and not hideResult:
            out = '%s completed successfully, result: %s' % (actionName, task.info.result)
            print out
        else:
            out = '%s completed successfully.' % actionName
            print out
    else:
        out = '%s did not complete successfully: %s' % (actionName, task.info.error)
        raise task.info.error
        print out
    
    return task.info.result

def main():
    args = GetArgs()
    try:
        si = None
        try:
            print "Trying to connect to VCENTER SERVER . . ."
            si = connect.Connect(args.host, int(args.port), args.user, args.password, service="hostd")
        except IOError, e:
            pass
            atexit.register(Disconnect, si)

        print "Connected to VCENTER SERVER !"
        
        content = si.RetrieveContent()
        
        vm_name = args.vm
        host_name = args.dest
        
        vm = get_obj(content, [vim.VirtualMachine], vm_name)
        destination_host = get_obj(content, [vim.HostSystem], host_name)
        
        resource_pool = vm.resourcePool
        
        if vm.runtime.powerState != 'poweredOn':
            print "WARNING:: Migration is only for Powered On VMs"
            sys.exit()
        
        """
        Migrate operation is only supported using shared datastore. 
        vSphere 5.1 and upper version supports migration without 
        shared data store but it will migrate both host and datastore.
        And this option is available only from vSphere Web Client.
        
        I don't have a shared datastore so I am using Relocate instead
        of Migrate
        """
	#migrate_priority = vim.VirtualMachine.MovePriority.defaultPriority

        #task = vm.Migrate(pool=resource_pool, host=destination_host, priority=migrate_priority)
        
        vm_relocate_spec = vim.vm.RelocateSpec()
        vm_relocate_spec.host = destination_host
        vm_relocate_spec.pool = resource_pool
        datastores = destination_host.datastore
        #Assuming Migrating between local datastores
        for datastore in datastores:
            if datastore.summary.type == 'VMFS':
                vm_relocate_spec.datastore = datastore
                break

        print "Invoking Migrate Operation . . ."
        task = vm.Relocate(spec=vm_relocate_spec)

        # Wait for Migrate to complete
        WaitTask(task, si)        
        
    except vmodl.MethodFault, e:
        print "Caught vmodl fault: %s" % e.msg
        return 1
    except Exception, e:
        print "Caught exception: %s" % str(e)
        return 1
    
# Start program
if __name__ == "__main__":
    main()
