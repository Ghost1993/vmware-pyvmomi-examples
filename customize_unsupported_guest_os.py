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

inputs = {'vcenter_ip': '15.22.10.11',
          'vcenter_password': 'Password123',
          'vcenter_user': 'Administrator',
          'vm_name': 'CustomTest',
          'user': 'root',
          'password': 'iforgot',
          'vm_ip': '10.10.10.23',
          'netmask': '255.255.255.0',
          'gateway': '10.10.10.1',
          'hostname': 'TestVM2'
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


def exec_command(content, vm, creds, args, program_path):
    cmdspec = vim.vm.guest.ProcessManager.ProgramSpec(arguments=args, programPath=program_path)
    output = content.guestOperationsManager.processManager.StartProgramInGuest(vm=vm, auth=creds, spec=cmdspec)

    return output


def main():
    try:
        si = None
        try:
            print "Trying to connect to VCENTER SERVER . . ."
            # Vsphere 5.1 = "vim.version.version8"
            #Vsphere 5.5 = "vim.version.version9"
            si = connect.Connect(inputs['vcenter_ip'], 443, inputs['vcenter_user'], inputs['vcenter_password'], version="vim.version.version8")
        except IOError, e:
            pass
            atexit.register(Disconnect, si)

        print "Connected to VCENTER SERVER !"

        content = si.RetrieveContent()

        vm = get_obj(content, [vim.VirtualMachine], inputs['vm_name'])

        if vm.runtime.powerState != 'poweredOn':
            print "WARNING:: Power on your VM before customizing"
            sys.exit()

        creds = vim.vm.guest.NamePasswordAuthentication(username=inputs['user'], password=inputs['password'])

        args = """ -ne '#!/bin/sh\n\n\
export VM_IP=%s\n\
export NETMASK=%s\n\
export GATEWAY=%s\n\
export HOST_NAME="%s"\n\n\
echo "source-directory /etc/network/interfaces.d" >> /etc/network/interfaces.new\n\
echo "auto lo" >> /etc/network/interfaces.new\n\
echo "iface lo inet loopback" >> /etc/network/interfaces.new\n\
echo "" >> /etc/network/interfaces.new\n\
echo "auto eth0" >> /etc/network/interfaces.new\n\
echo "iface eth0 inet static" >> /etc/network/interfaces.new\n\
echo "address $VM_IP" >> /etc/network/interfaces.new\n\
echo "netmask $NETMASK" >> /etc/network/interfaces.new\n\
echo "gateway  $GATEWAY">> /etc/network/interfaces.new\n\
mv /etc/network/interfaces.new /etc/network/interfaces\n\n\
echo $HOST_NAME > /etc/hostname\n\
echo "127.0.1.1    $HOST_NAME" >>  /etc/hosts\n\n\
if [ -e /home/customize_script.sh ]; then\n\
    rm /home/customize_script.sh\n\
fi\n\
' >> /home/customize_script.sh""" % (inputs['vm_ip'], inputs['netmask'], inputs['gateway'], inputs['hostname'])

        output = exec_command(content, vm, creds, args, '/bin/echo')

        print "Waiting for the Customization script to generate..."
        time.sleep(10)
        permission = exec_command(content, vm, creds, "+x '/home/customize_script.sh'", '/bin/chmod')
        if not output and permission or output and permission < 0:
            print "ERROR:: Something went wrong while creating customization script. Manually verify"
        else:
            print "Successfully created the Customization script"

        exec_command(content, vm, creds, "/home/customize_script.sh", '/usr/bin/sudo')
        print "Successfully customized VM", inputs['vm_name']

        print "Restarting VM to apply hostname change"
        vm.RebootGuest()

    except vmodl.MethodFault, e:
        if e.msg == "The guest operations agent could not be contacted.":
            print "ERROR:: VMware Tools is either not installed or nut running inside VM. Please verify and run again."
            return 1
        print "Caught vmodl fault: %s" % e.msg
        return 1
    except Exception, e:
        print "Caught exception: %s" % str(e)
        return 1

# Start program
if __name__ == "__main__":
    main()
