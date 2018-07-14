#!/usr/bin/python3

import os
import sys
import stat
import socket
import re
import getpass
import grp
import argparse
import subprocess
import time


class VMmanagerException(Exception):
    pass


class VMmanager:
    def __init__(self, user):
        self.user = user
        self.vms_home = '/opt/VMs/' + user

        # Check VMs home directory
        if not os.path.isdir(self.vms_home):
            raise VMmanagerException(self.vms_home + " doesn't exist.")

        if not os.access(self.vms_home, os.W_OK):
            raise VMmanagerException(self.vms_home + " isn't writable.")

        # Check groups
        groups = [g.gr_name for g in grp.getgrall() if user in g.gr_mem]
        if 'kvm' not in groups:
            raise VMmanagerException(user + " isn't in kvm group.")

        # Check setuid bit of /usr/lib/qemu/qemu-bridge-helper
        mode = os.stat('/usr/lib/qemu/qemu-bridge-helper')
        if mode.st_mode & stat.S_ISUID == 0:
            raise VMmanagerException("/usr/lib/qemu/qemu-bridge-helper hasn't setuid bit set.")

        self.vms = []
        self._load_vms()

    def _load_vms(self):
        self.vms = os.listdir(self.vms_home)

    def _is_running(self, vm):
        return os.path.exists(self.vms_home + '/' + vm + '/monitor')

    def _validate_vm_name(self, name):
        regex = re.compile('[a-zA-Z0-9_-]{1,32}')
        if regex.fullmatch(name) is None:
            raise argparse.ArgumentTypeError('Invalid VM name. Must be [a-zA-Z0-9_-]{1,32}')
        return name

    def _validate_size(self, value):
        regex = re.compile('[1-9][0-9]*(M|G)')
        if regex.fullmatch(value) is None:
            raise argparse.ArgumentTypeError('Invalid size.')
        return value

    def _run_command(self, cmd):
        return subprocess.run(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def list(self, args):
        parser = argparse.ArgumentParser(prog='list', description='List all VMs')
        parser.add_argument('--status', action='store_true', help='Include status')
        parser.add_argument('--name', required=False, type=self._validate_vm_name, help='Existing VM name')
        args = parser.parse_args(args)

        if args.name is not None:
            vms = [args.name]

            # Check existing VM
            if not os.path.exists(self.vms_home + '/' + args.name):
                raise VMmanagerException("Could not list VM: doesn't exist")
        else:
            vms = self.vms

        for v in vms:
            # Fetch MAC address
            with open(self.vms_home + '/' + v + '/mac_addr') as f:
                mac = f.readline()

            if args.status:
                print('{name} ({mac}): {status}'.format(name=v, mac=mac,
                                                        status='RUNNING' if self._is_running(v) else 'STOPPED'))
            else:
                print('{name} ({mac})'.format(name=v, mac=mac))

    def create(self, args):
        parser = argparse.ArgumentParser(prog='create', description='Create a new VM')
        parser.add_argument('--name', required=True, type=self._validate_vm_name, help='VM name')
        parser.add_argument('--disk', required=True, type=self._validate_size,
                            help='Disk size (understand suffix M and G)')
        args = parser.parse_args(args)

        # Check existing VM
        if os.path.exists(self.vms_home + '/' + args.name):  # or args.name in self.vms:
            raise VMmanagerException("Could not create VM: file already exist")

        # Create directory
        os.mkdir(self.vms_home + '/' + args.name)

        # Create disk
        disk_size = args.disk.replace('M', '').replace('G', '')
        disk_size *= 1000 if args.disk[:-1] == 'M' else 1000000
        if disk_size > 50000000:
            raise VMmanagerException("Could not create VM: disk can't be greater than 50 Go")

        r = self._run_command('qemu-img -f qcow2 {}/disk.img {}'.format(self.vms_home + '/' + args.name, args.disk))
        if r.returncode != 0:
            os.rmdir(self.vms_home + '/' + args.name)
            raise VMmanagerException("Could not create disk")

        # Generate MAC address
        uid = len(self.vms)
        mac = '52:54:00:12:34:{}'.format(hex(uid)[2:])
        with open(self.vms_home + '/' + args.name + '/mac_addr') as f:
            f.write(mac)

        print('{} created successfully'.format(args.name))

    def delete(self, args):
        parser = argparse.ArgumentParser(prog='delete', description='Delete an existing VM')
        parser.add_argument('--name', required=True, type=self._validate_vm_name, help='Existing VM name')
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation if VM is running')
        args = parser.parse_args(args)

        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + args.name):  # or args.name not in self.vms:
            raise VMmanagerException("Could not delete VM: doesn't exist")

        # Check running status and eventually stop it
        if self._is_running(args.name):
            if not args.force:
                raise VMmanagerException('VM is running.')
            else:
                self.stop([args.name, '-f'])

        # Remove files
        os.remove(self.vms_home + '/' + args.name + '/disk.img')
        os.remove(self.vms_home + '/' + args.name + '/mac_addr')
        os.rmdir(self.vms_home + '/' + args.name)

        print('{} removed'.format(args.name))

    def state(self, args):
        self.list(args.append('--status'))

    def run(self, args):
        parser = argparse.ArgumentParser(prog='run', description='Launch a VM')
        parser.add_argument('--name', required=True, type=self._validate_vm_name, help='Existing VM name')
        parser.add_argument('--ram', required=True, type=self._validate_size,
                            help='Memory size (understand suffix M and G)')
        args = parser.parse_args(args)

        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + args.name):
            raise VMmanagerException("Could not run VM: doesn't exist")

        # Check running status
        if self._is_running(args.name):
            raise VMmanagerException("Could not run VM: already running")

        # Fetch MAC address
        with open(self.vms_home + '/' + args.name + '/mac_addr') as f:
            mac = f.readline()

        # Run VM
        cmd = 'kvm -m {mem} {img}.img -display none -monitor unix:{path}/monitor,server,nowait ' \
              '-k fr -netdev bridge,id=hn0 -device virtio-net-pci,netdev=hn0,id=nic1,mac={mac} -daemonize'\
            .format(mem=args.ram,
                    img=self.vms_home + '/' + args.name + '/' + args.name,
                    path=self.vms_home + '/' + args.name,
                    mac=mac)

        r = self._run_command(cmd)
        if r.returncode != 0:
            raise VMmanagerException("Could not run VM: kvm returns {}".format(r.returncode))

        print('{} started'.format(args.name))

    def stop(self, args):
        parser = argparse.ArgumentParser(prog='stop', description='Stop a running VM')
        parser.add_argument('--name', required=True, type=self._validate_vm_name, help='Existing VM name')
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation')
        args = parser.parse_args(args)

        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + args.name):
            raise VMmanagerException("Could not stop VM: doesn't exist")

        # Check running status
        if not self._is_running(args.name):
            raise VMmanagerException("Could not stop VM: not running")

        # Connecting to UNIX socket (QEMU monitor)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.vms_home + '/' + args.name + '/monitor')
        except socket.error as e:
            raise VMmanagerException('Could not stop VM: error with UNIX socket')

        try:
            sock.sendall('system_powerdown')
        finally:
            sock.close()

        time.sleep(5)

        # Check VM state
        if self._is_running(args.name):
            if not args.force:
                raise VMmanagerException('Could not stop VM')
            else:
                # Force shutdown
                self._run_command("pkill -f 'qemu-system-x86_64.*{}.*'".format(args.name))
        else:
            print('{} stopped'.format(args.name))


def usage():
    usage = """Usage: {} <operation> [-h] [arguments...]
<operation> = list|create|delete|state|run|stop

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
    elif operation == 'delete':
        manager.delete(args)
    elif operation == 'state':
        manager.state(args)
    elif operation == 'run':
        manager.run(args)
    elif operation == 'stop':
        manager.stop(args)
    else:
        usage()
