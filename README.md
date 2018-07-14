# VMmanager
A QEMU/KVM virtual machine manager

## Description
This tool serve to administrate virtual machines with Qemu/KVM on an headless server. You can:

- Create, delete, modify VMs
- Run, stop VMs
- Configure network between "NAT", "bridge" and "none"
- Choose amount of memory and disk size

## Usage


## Prerequisites
Each user who wants to administrate VMs have to:

- are in the *kvm* group
- have a directory */opt/VMs/<username\>*

The utility */usr/lib/qemu/qemu-bridge-helper* must have capability **CAP_NET_ADMIN** set:
```sh
sudo setcap cap_net_admin+ep /usr/lib/qemu/qemu-bridge-helper
```
