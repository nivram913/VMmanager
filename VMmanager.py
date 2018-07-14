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

        if not os.path.exists(self.vms_home):
            raise VMmanagerException(self.vms_home + " doesn't exist.\nContact your system administrator.\n")

        self.vms = []
        self._load_vms()
    
    def _load_vms(self):
        directories = os.listdir(self.vms_home)
        for d in directories:
            if os.path.exists(self.vms_home + '/' + d + '/config.json'):
                self.vms.append(d)

    def _get_status(self, vm):
        return os.path.exists(self.vms_home + '/' + vm + '/monitor')

    def list(self, args):
        parser = argparse.ArgumentParser(prog='list', description='List all VMs')
        parser.add_argument('-c', dest='config', action='store_true', help='Include configuration')
        parser.add_argument('-s', dest='status', action='store_true', help='Include status')
        parser.add_argument('name', nargs='?', default='')
        args = parser.parse_args(args)

        if args.name != '':
            vms = args.name
        else:
            vms = self.vms

        for v in vms:
            print(v)
            if args.status:
                print(self._get_status(v))
            if args.config:
                with open(self.vms_home + '/' + v + '/config.json') as f:
                    print(f.readline())

    def create(self, args):
        parser = argparse.ArgumentParser(prog='create', description='Create a new VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('--disk', required=True, help='Disk size (understand suffix M and G)')
        parser.add_argument('--ram', required=True, help='Memory size (understand suffix M and G)')
        parser.add_argument('--cdrom', required=False, help='Iso file to put in virtual CD-ROM')
        parser.add_argument('--network', required=True, choices=['none', 'NAT', 'bridge'], help='Network type')
        args = parser.parse_args(args)

    def modify(self, args):
        parser = argparse.ArgumentParser(prog='modify', description='Modify an existing VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('--ram', required=False, help='Memory size (understand suffix M and G)')
        parser.add_argument('--cdrom', required=False, help='Iso file to put in virtual CD-ROM')
        parser.add_argument('--network', required=False, choices=['none', 'NAT', 'bridge'], help='Network type')
        args = parser.parse_args(args)

    def delete(self, args):
        parser = argparse.ArgumentParser(prog='delete', description='Delete an existing VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation if VM is running')
        parser.add_argument('--preserve-disk', action='store_true', help="Don't delete disk")
        args = parser.parse_args(args)

    def state(self, args):
        parser = argparse.ArgumentParser(prog='state', description='Get state of all/a running VM')
        parser.add_argument('name', nargs='?', default='')
        args = parser.parse_args(args)

    def snapshot(self, args):
        parser = argparse.ArgumentParser(prog='snapshot', description='Take a snapshot of a stopped VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('snapshot_name', nargs=1)
        args = parser.parse_args(args)

    def run(self, args):
        parser = argparse.ArgumentParser(prog='run', description='Launch a VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('--boot', required=False, choices=['cdrom', 'disk'], help="Select boot device")
        args = parser.parse_args(args)

    def stop(self, args):
        parser = argparse.ArgumentParser(prog='stop', description='Stop a running VM')
        parser.add_argument('name', nargs=1)
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation')
        args = parser.parse_args(args)


def usage():
    usage = """Usage: {} <operation> [-h] [arguments...]
<operation> = list|create|modify|delete|state|snapshot|run|stop

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
