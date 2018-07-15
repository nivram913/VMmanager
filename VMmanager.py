#!/usr/bin/python3

import os
import sys
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

        self.vms = []
        self._load_vms()

    def _load_vms(self):
        self.vms = os.listdir(self.vms_home)

    def is_running(self, vm):
        """
        Check if a VM is running
        :param vm: VM name (string)
        :return: True if VM is running, False if VM is stopped or VM doesn't exist
        """
        return os.path.exists(self.vms_home + '/' + vm + '/monitor')

    def _run_command(self, cmd):
        return subprocess.run(cmd.split(' '), stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def list(self, name=None, status=False):
        """
        List VMs
        :param name: VM name (optional) (string)
        :param status: Include VM status (boolean)
        :return: An array of dictionary representing a VM
        """
        vms_list = []

        if name is not None:
            vms = [name]

            # Check existing VM
            if not os.path.exists(self.vms_home + '/' + name):
                raise VMmanagerException("Could not list VM: doesn't exist")
        else:
            vms = self.vms

        for v in vms:
            # Fetch MAC address
            with open(self.vms_home + '/' + v + '/mac_addr') as f:
                mac = f.readline()

            if status:
                vms_list.append({'name': v, 'mac': mac, 'status': 'RUNNING' if self.is_running(v) else 'STOPPED'})
            else:
                vms_list.append({'name': v, 'mac': mac})

        return vms_list

    def create(self, name, disk_size):
        """
        Create a new VM
        :param name: VM name (string)
        :param disk_size: Disk size (string) (ex: 20G)
        :return: 0 if ok
        :raise: VMmanagerException if error occurs
        """
        # Check existing VM
        if os.path.exists(self.vms_home + '/' + name):  # or args.name in self.vms:
            raise VMmanagerException("Could not create VM: file already exist")

        # Create directory
        os.mkdir(self.vms_home + '/' + name)

        # Create disk
        disk_size = disk_size.replace('M', '').replace('G', '')
        disk_size *= 1000 if disk_size[:-1] == 'M' else 1000000
        if disk_size > 50000000:
            raise VMmanagerException("Could not create VM: disk can't be greater than 50 Go")

        r = self._run_command('qemu-img -f qcow2 {}/disk.img {}'.format(self.vms_home + '/' + name, disk_size))
        if r.returncode != 0:
            os.rmdir(self.vms_home + '/' + name)
            raise VMmanagerException("Could not create disk")

        # Generate MAC address
        uid = len(self.vms)
        mac = '52:54:00:12:34:{}'.format(hex(uid)[2:])
        with open(self.vms_home + '/' + name + '/mac_addr') as f:
            f.write(mac)

        return 0

    def delete(self, name, force=False):
        """
        Delete an existing VM
        :param name: VM name (string)
        :param force: Force deletion if VM is running (boolean)
        :return: 0 if ok
        :raise: VMmanagerException if error occurs
        """
        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + name):  # or args.name not in self.vms:
            raise VMmanagerException("Could not delete VM: doesn't exist")

        # Check running status and eventually stop it
        if self.is_running(name):
            if not force:
                raise VMmanagerException('VM is running.')
            else:
                self.stop(name, True)

        # Remove files
        os.remove(self.vms_home + '/' + name + '/disk.img')
        os.remove(self.vms_home + '/' + name + '/mac_addr')
        os.rmdir(self.vms_home + '/' + name)

        return 0

    def run(self, name, ram_size):
        """
        Run an existing VM with ram_size amount of memory
        :param name: VM name (string)
        :param ram_size: Amount of memory allocated (string) (ex: 1G)
        :return: 0 if ok
        :raise: VMmanagerException if error occurs
        """
        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + name):
            raise VMmanagerException("Could not run VM: doesn't exist")

        # Check running status
        if self.is_running(name):
            raise VMmanagerException("Could not run VM: already running")

        # Fetch MAC address
        with open(self.vms_home + '/' + name + '/mac_addr') as f:
            mac = f.readline()

        # Run VM
        cmd = 'kvm -m {mem} {img}.img -display none -monitor unix:{path}/monitor,server,nowait ' \
              '-k fr -netdev bridge,id=hn0 -device virtio-net-pci,netdev=hn0,id=nic1,mac={mac} -daemonize' \
            .format(mem=ram_size,
                    img=self.vms_home + '/' + name + '/' + name,
                    path=self.vms_home + '/' + name,
                    mac=mac)

        r = self._run_command(cmd)
        if r.returncode != 0:
            raise VMmanagerException("Could not run VM: kvm returns {}".format(r.returncode))

        return 0

    def stop(self, name, force=False):
        """
        Stop a running VM
        :param name: VM name (string)
        :param force: Force stop with SIGTERM (boolean)
        :return: 0 if ok
        :raise: VMmanagerException if error occurs
        """
        # Check existing VM
        if not os.path.exists(self.vms_home + '/' + name):
            raise VMmanagerException("Could not stop VM: doesn't exist")

        # Check running status
        if not self.is_running(name):
            raise VMmanagerException("Could not stop VM: not running")

        # Connecting to UNIX socket (QEMU monitor)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.vms_home + '/' + name + '/monitor')
        except socket.error as e:
            raise VMmanagerException('Could not stop VM: error with UNIX socket')

        try:
            sock.sendall('system_powerdown'.encode('ascii'))
        finally:
            sock.close()

        time.sleep(5)

        # Check VM state
        if self.is_running(name):
            if not force:
                raise VMmanagerException('Could not stop VM')
            else:
                # Force shutdown
                self._run_command("pkill -f 'qemu-system-x86_64.*{}.*'".format(name))

        return 0


# MAIN
if __name__ == "__main__":
    def usage():
        usage = """Usage: {} <operation> [-h] [arguments...]
<operation> = list|create|delete|status|run|stop

""".format(sys.argv[0])
        sys.stderr.write(usage)
        sys.exit(1)

    def _validate_vm_name(name):
        regex = re.compile('[a-zA-Z0-9_-]{1,32}')
        if regex.fullmatch(name) is None:
            raise argparse.ArgumentTypeError('Invalid VM name. Must be [a-zA-Z0-9_-]{1,32}')
        return name

    def _validate_size(value):
        regex = re.compile('[1-9][0-9]*(M|G)')
        if regex.fullmatch(value) is None:
            raise argparse.ArgumentTypeError('Invalid size.')
        return value

    if len(sys.argv) < 2:
        usage()

    manager = VMmanager(getpass.getuser())

    operation = sys.argv.pop(1)
    args = sys.argv[1:]

    if operation == 'list' or operation == 'status':
        parser = argparse.ArgumentParser(prog='list', description='List all VMs')
        if operation == 'list':
            parser.add_argument('--status', action='store_true', help='Include status')
        parser.add_argument('--name', required=False, type=_validate_vm_name, help='Existing VM name')
        args = parser.parse_args(args)
        if operation == 'list':
            status = args.status
        else:
            status = True

        try:
            vms_list = manager.list(args.name, status)
        except VMmanagerException as e:
            print(e)
            sys.exit(1)

        for v in vms_list:
            if status:
                print('{name} ({mac}): {status}'.format(name=v['name'], mac=v['mac'], status=v['status']))
            else:
                print('{name} ({mac})'.format(name=v['name'], mac=v['mac']))

    elif operation == 'create':
        parser = argparse.ArgumentParser(prog='create', description='Create a new VM')
        parser.add_argument('--name', required=True, type=_validate_vm_name, help='VM name')
        parser.add_argument('--disk', required=True, type=_validate_size,
                            help='Disk size (understand suffix M and G)')
        args = parser.parse_args(args)

        try:
            manager.create(args.name, args.disk)
        except VMmanagerException as e:
            print(e)
            sys.exit(1)

        print('{} created successfully'.format(args.name))

    elif operation == 'delete':
        parser = argparse.ArgumentParser(prog='delete', description='Delete an existing VM')
        parser.add_argument('--name', required=True, type=_validate_vm_name, help='Existing VM name')
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation if VM is running')
        args = parser.parse_args(args)

        try:
            manager.delete(args.name, args.force)
        except VMmanagerException as e:
            print(e)
            sys.exit(1)

        print('{} removed'.format(args.name))

    elif operation == 'run':
        parser = argparse.ArgumentParser(prog='run', description='Launch a VM')
        parser.add_argument('--name', required=True, type=_validate_vm_name, help='Existing VM name')
        parser.add_argument('--ram', required=True, type=_validate_size,
                            help='Memory size (understand suffix M and G)')
        args = parser.parse_args(args)

        try:
            manager.run(args.name, args.ram)
        except VMmanagerException as e:
            print(e)
            sys.exit(1)

        print('{} started'.format(args.name))

    elif operation == 'stop':
        parser = argparse.ArgumentParser(prog='stop', description='Stop a running VM')
        parser.add_argument('--name', required=True, type=_validate_vm_name, help='Existing VM name')
        parser.add_argument('-f', dest='force', action='store_true', help='Force operation')
        args = parser.parse_args(args)

        try:
            manager.stop(args.name, args.force)
        except VMmanagerException as e:
            print(e)
            sys.exit(1)

        print('{} stopped'.format(args.name))

    else:
        usage()
