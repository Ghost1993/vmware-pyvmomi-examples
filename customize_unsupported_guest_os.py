'''
Copyright 2014-2015 Reubenur Rahman
All Rights Reserved
@author: reuben.13@gmail.com
'''

import atexit
import argparse
import sys
import time

from pyVmomi import vim, vmodl
from pyVim import connect
from pyVim.connect import Disconnect, SmartConnect

inputs = {'vcenter_ip': '15.21.18.11',
          'vcenter_password': 'Password123',
          'vcenter_user': 'Administrator',
          'vm_name': 'ubuntu14',
          'vm_ip': '10.10.10.45',
          'subnet': '255.255.255.0',
          'gateway': '10.10.10.1',
          'dns': '11.110.135.51, 11.110.135.52'
          }

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

def main():
    #args = GetArgs()
    try:
        si = None
        try:
            print "Trying to connect to VCENTER SERVER . . ."
	    #"vim.version.version8" for VMware 5.1 
            si = connect.Connect(inputs['vcenter_ip'], 443, inputs['vcenter_user'], inputs['vcenter_password'], version="vim.version.version8")
        except IOError, e:
            pass
            atexit.register(Disconnect, si)

        print "Connected to VCENTER SERVER !"
        
        content = si.RetrieveContent()
        
        #vm_name = args.vm
        vm_name = inputs['vm_name']      
        vm = get_obj(content, [vim.VirtualMachine], vm_name)

        if vm.runtime.powerState != 'poweredOn':
            print "WARNING:: Power on your VM before customizing"
            sys.exit()
        
        print "Started Customizatrion. Writing configuration inside VM."
        creds = vim.vm.guest.NamePasswordAuthentication(username='root', password='iforgot')
	#This is just an example. I am wildly modifying interfaces file.
        #You have to be carefull with the linux commands while modifying
        #the config files such as /etc/hosts or /etc/network/interfaces
	args = "'auto eth0\n\
iface eth0 inet static\n\
address %s\n\
netmask %s\n\
gateway %s\n\
dns-nameservers %s\n' > /etc/network/interfaces" % (inputs['vm_ip'], inputs['subnet'], inputs['gateway'], inputs['dns'])
        spec = vim.vm.guest.ProcessManager.ProgramSpec(arguments=args, programPath='/bin/echo')
        output = si.content.guestOperationsManager.processManager.StartProgramInGuest(vm=vm, auth=creds, spec=spec)
	if not output or output < 0:
            print "ERROR:: Something went wrong while customizing guest os. Manually verify"
        else:
            print "Customized the guest succesfully"
    except vmodl.MethodFault, e:
        print "Caught vmodl fault: %s" % e.msg
        return 1
    except Exception, e:
        print "Caught exception: %s" % str(e)
        return 1
    
# Start program
if __name__ == "__main__":
    main()
