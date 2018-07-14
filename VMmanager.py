#!/usr/bin/python3

import os
import sys
import getpass
import argparse


class VMmanagerException(Exception):
    pass


class VMmanager:
    def __init__(self, user):
        self.user = user
        self.vms_home = '/opt/VMs/' + user

        if not os.path.exists(vms_home):
            sys.stderr.write(vms_home + " doesn't exist.\nContact your system administrator.\n")
            raise VMmanagerException()

        self.vms = []
        self._load_vms()
    
    def _load_vms(self):
        directories = os.listdir(self.vms_home)
        for d in directories:
            if os.path.exists(self.vms_home + '/' + d + '/config.json'):
                self.vms.append(d)

    def list(self, args):
        parser = argparse.ArgumentParser(description='List all VMs')
        parser.add_argument('-c', nargs='?', help='')

        if vm != '':
            vms = vm
        else:
            vms = self.vms

        for v in vms:
            print(v)
            if status:
                print(self.get_status(v))
            if config:
                with open(self.vms_home + '/' + d + '/config.json') as f:
                    print(f.readline())

    def get_status(self, vm):
        return os.path.exists(self.vms_home + '/' + vm + '/monitor')

    def create(self, args):
        if len(args) != 7 and len(args) != 9:
            usage()

        name = args[0]
        disk_size = 0
        ram_size = 0
        cdrom = ''
        network = 'none'
        for i in range(len(args)):
            arg = args.pop(0)
            if arg == '--disk':
                disk_size = args[i + 1]
            elif arg == '--ram':
                ram_size = args[i + 1]
            elif arg == '--cdrom':
                cdrom = args[i + 1]
            elif arg == '--network':
                network = args[i + 1]


def usage():
    usage = """Usage: {} <operation> [arguments...]
<operation> = list|create|modify|delete|state|snapshot|run|stop

list - List all VMs
    list [-c] [-s] [name]
    -c include configuration
    -s include status

create - Create a new VM
    create <name> --disk <size> --ram <size> [--cdrom <iso file>] --network none|NAT|bridge

modify - Modify an existing VM
    modify <name> [--ram <size>] [--cdrom <iso file>|none] [--network none|NAT|bridge]

delete - Delete an existing VM
    delete [-f] [--preserve-disk] <name>
    -f force operation if VM is running

state - Get state of all/a running VM
    state [name]

snapshot - Take a snapshot of a stopped VM
    snapshot <name> <snapshot name>

run - Launch a VM
    run <name> [--boot cdrom|disk]
    
stop - Stop a running VM
    stop [-f] <name>
    -f force operation

""".format(sys.argv[0])
    sys.stderr.write(usage)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()

    manager = VMmanager(getpass.getuser())

    operation = sys.argv.pop(1)
    args = sys.argv[1:]
    
    if operation == 'list':
        manager.list(args)
    elif operation == 'create':
        manager.create(args)
    elif operation == 'modify':
        manager.modify(args)
    elif operation == 'delete':
        manager.delete(args)
    elif operation == 'state':
        manager.state(args)
    elif operation == 'snapshot':
        manager.snapshot(args)
    elif operation == 'run':
        manager.run(args)
    elif operation == 'stop':
        manager.stop(args)
    else:
        usage()
