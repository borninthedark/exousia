# RKE2 on Fedora Bootc: Complete Setup Guide

**Immutable Kubernetes Infrastructure with Atomic Updates**

This guide walks through building and deploying RKE2 (Rancher Kubernetes Engine 2) on Fedora bootc, creating an immutable, reproducible Kubernetes infrastructure with atomic update capabilities.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
  - [1. Build the Bootc Image](#1-build-the-bootc-image)
  - [2. Setup Host Registry](#2-setup-host-registry)
  - [3. Create VM Disk Image](#3-create-vm-disk-image)
  - [4. Deploy the VM](#4-deploy-the-vm)
  - [5. Access the Cluster](#5-access-the-cluster)
- [Operations](#operations)
  - [Upgrading](#upgrading)
  - [Rollback](#rollback)
  - [Scaling](#scaling)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Overview

### What This Gives You

- **Immutable Infrastructure**: Entire Kubernetes node as a container image
- **Atomic Updates**: Upgrade entire k8s stack with `bootc upgrade`
- **Instant Rollback**: Boot into previous version if issues occur
- **Reproducible Builds**: Version and iterate on your cluster infrastructure
- **Clean Separation**: Kubernetes cluster isolated from Gentoo host

### Architecture Benefits

```
┌─────────────────────────────────────────────────────┐
│                  Gentoo Host                        │
│                                                     │
│  ┌─────────────────┐      ┌──────────────────┐    │
│  │ Podman Registry │◄─────┤ libvirt/KVM      │    │
│  │ (192.168.122.1) │      │                  │    │
│  └─────────────────┘      │  ┌────────────┐  │    │
│                           │  │ Fedora     │  │    │
│  ┌─────────────────┐      │  │ bootc      │  │    │
│  │ Kubeconfig      │◄─────┼──┤            │  │    │
│  │ (9p share)      │      │  │ + RKE2     │  │    │
│  └─────────────────┘      │  └────────────┘  │    │
│                           └──────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**Benefits:**
- Registry on host survives VM rebuilds
- 9p filesystem shares enable seamless kubeconfig access
- VM snapshots provide additional rollback beyond bootc
- Test image promotion workflows that mirror production

---

## Prerequisites

### Host System (Gentoo)

- **Podman** (for building and running registry)
- **libvirt/KVM** (for running VMs)
- **virsh, virt-install** (VM management)
- **Buildah** (optional, for building images)

### System Resources

Minimum recommended for single-node RKE2 cluster:

- **CPU**: 4 cores
- **Memory**: 8 GB
- **Disk**: 50 GB (for VM disk)
- **Network**: libvirt default network (virbr0)

### Network Configuration

Ensure libvirt default network is running:

```bash
sudo virsh net-start default
sudo virsh net-autostart default
```

Verify bridge IP (should be `192.168.122.1`):

```bash
ip addr show virbr0
```

---

## Quick Start

For the impatient, here's the 30-second version:

```bash
# One command quickstart
make rke2-quickstart

# Or manual steps:
# 1. Start host registry
python3 tools/rke2_ops.py registry start

# 2. Build and push bootc image
make rke2-build
make rke2-push

# 3. Build VM disk image
python3 tools/rke2_ops.py vm build

# 4. Create and start VM
python3 tools/rke2_ops.py vm create
python3 tools/rke2_ops.py vm start

# 5. Wait ~2 minutes, then get kubeconfig
python3 tools/rke2_ops.py kubeconfig

# 6. Test cluster
export KUBECONFIG=~/.kube/rke2-config
kubectl get nodes
```

---

## Detailed Setup

### 1. Build the Bootc Image

Build the Fedora bootc image with RKE2 baked in:

```bash
# Build the image
podman build -f Containerfile.rke2 -t exousia-rke2:latest .

# Optionally customize the build
podman build \
  --build-arg RKE2_VERSION=v1.28.5+rke2r1 \
  --build-arg INSTALL_RKE2_TYPE=server \
  -f Containerfile.rke2 \
  -t exousia-rke2:latest \
  .
```

**Build arguments:**
- `RKE2_VERSION`: Specific RKE2 version (default: latest)
- `INSTALL_RKE2_TYPE`: `server` or `agent` (default: server)

### 2. Setup Host Registry

Start a local container registry for the VM to pull images from:

```bash
# Start registry on libvirt bridge
python3 tools/rke2_ops.py registry start

# Verify registry is running
python3 tools/rke2_ops.py registry status

# View connection info
python3 tools/rke2_ops.py registry info
```

The registry will be accessible at:
- **From host**: `http://localhost:5000`
- **From VMs**: `http://192.168.122.1:5000`

**Push the bootc image to the registry:**

```bash
# Tag for local registry
podman tag exousia-rke2:latest localhost:5000/exousia-rke2:latest

# Push to registry
podman push localhost:5000/exousia-rke2:latest

# Verify
curl http://192.168.122.1:5000/v2/_catalog
```

### 3. Create VM Disk Image

Build a bootable disk image from the bootc container:

```bash
# Build qcow2 disk image (50GB by default)
python3 tools/rke2_ops.py vm build

# Custom disk size
RKE2_DISK_SIZE=100G python3 tools/rke2_ops.py vm build
```

This uses `bootc-image-builder` to create a qcow2 disk image at:
`/var/lib/libvirt/images/rke2-node-1.qcow2`

**What happens during build:**
1. Pulls bootc image from registry
2. Generates disk image with bootc installed
3. Applies cloud-init configuration
4. Creates UEFI boot environment

### 4. Deploy the VM

Create and start the VM:

```bash
# Create VM definition
python3 tools/rke2_ops.py vm create

# Start the VM
python3 tools/rke2_ops.py vm start

# Check status
python3 tools/rke2_ops.py vm status
```

**VM will:**
1. Boot from the bootc image
2. Run cloud-init to configure hostname, mounts
3. Start RKE2 server service
4. Export kubeconfig to host via 9p share

**Monitor startup:**

```bash
# Watch VM console (Ctrl+] to exit)
sudo virsh console rke2-node-1

# Check RKE2 logs
sudo virsh console rke2-node-1
# Then inside VM: journalctl -u rke2-server -f
```

### 5. Access the Cluster

Once RKE2 starts (usually 2-3 minutes), retrieve the kubeconfig:

```bash
# Get kubeconfig from VM
python3 tools/rke2_ops.py kubeconfig

# Use the kubeconfig
export KUBECONFIG=~/.kube/rke2-config
kubectl cluster-info

# Verify nodes
kubectl get nodes

# Check system pods
kubectl get pods -A
```

**Manual kubeconfig retrieval:**

```bash
# Kubeconfig is exported to host at:
cat /var/lib/libvirt/rke2/kubeconfig/rke2.yaml

# Copy and update server address
cp /var/lib/libvirt/rke2/kubeconfig/rke2.yaml ~/.kube/rke2-config

# Get VM IP
VM_IP=$(sudo virsh domifaddr rke2-node-1 | grep -oP '(?<=ipv4\s{1,})[\d.]+' | head -1)

# Update server address
sed -i "s|https://127.0.0.1:6443|https://${VM_IP}:6443|" ~/.kube/rke2-config

# Test
kubectl --kubeconfig ~/.kube/rke2-config get nodes
```

---

## Operations

### Upgrading

Upgrade the entire Kubernetes stack atomically using bootc:

**1. Build new image version:**

```bash
# Build new image with updates
podman build -f Containerfile.rke2 -t localhost:5000/exousia-rke2:v2 .
podman push localhost:5000/exousia-rke2:v2
```

**2. Upgrade inside VM:**

```bash
# Connect to VM console
sudo virsh console rke2-node-1

# Switch to new image
sudo bootc switch localhost:5000/exousia-rke2:v2

# Or upgrade to latest
sudo bootc upgrade

# Reboot to apply
sudo systemctl reboot
```

**3. Verify upgrade:**

```bash
# Wait for VM to come back up
sleep 60

# Check bootc status
sudo virsh console rke2-node-1
sudo bootc status

# Verify RKE2
rke2-status
```

### Rollback

If upgrade fails, rollback to previous image:

**Automatic rollback (on boot failure):**
- bootc will automatically boot into previous deployment if current fails

**Manual rollback:**

```bash
# Connect to VM
sudo virsh console rke2-node-1

# Rollback to previous deployment
sudo bootc rollback

# Reboot
sudo systemctl reboot
```

**VM snapshot rollback (instant):**

```bash
# Create snapshot before upgrade
sudo virsh snapshot-create-as rke2-node-1 pre-upgrade

# After upgrade, if needed:
sudo virsh snapshot-revert rke2-node-1 pre-upgrade
```

### Scaling

**Multi-node clusters:**

To create additional nodes:

```bash
# Build agent image (vs server)
podman build \
  --build-arg INSTALL_RKE2_TYPE=agent \
  -f Containerfile.rke2 \
  -t localhost:5000/exousia-rke2-agent:latest \
  .
podman push localhost:5000/exousia-rke2-agent:latest

# Create additional VMs
RKE2_VM_NAME=rke2-agent-1 \
RKE2_IMAGE_REGISTRY=localhost:5000/exousia-rke2-agent:latest \
  python3 tools/rke2_ops.py vm build

RKE2_VM_NAME=rke2-agent-1 python3 tools/rke2_ops.py vm create
RKE2_VM_NAME=rke2-agent-1 python3 tools/rke2_ops.py vm start
```

**Configure agent to join server:**

Edit `/etc/rancher/rke2/config.yaml` on agent:

```yaml
server: https://192.168.122.100:9345
token: <server-node-token>
```

Get token from server:

```bash
sudo cat /var/lib/rancher/rke2/server/node-token
```

---

## Configuration

### RKE2 Configuration

Edit `custom-configs/rke2/config.yaml` before building image:

```yaml
# Cluster networking
cluster-cidr: "10.42.0.0/16"
service-cidr: "10.43.0.0/16"

# CNI plugin
cni: "canal"  # or calico, cilium, flannel

# API server TLS SANs
tls-san:
  - "192.168.122.100"
  - "rke2.example.com"

# Disable components
disable:
  - rke2-ingress-nginx
```

### Registry Configuration

Edit `custom-configs/rke2/registries.yaml` to customize registry mirrors:

```yaml
mirrors:
  docker.io:
    endpoint:
      - "http://192.168.122.1:5000"

configs:
  "192.168.122.1:5000":
    tls:
      insecure_skip_verify: true
```

### Cloud-init Configuration

Customize `k8s/rke2/cloud-init.yaml` for:
- Hostname and networking
- SSH keys
- Custom RKE2 config overrides
- Node labels and taints

### Libvirt Domain

Customize `k8s/rke2/libvirt-domain.xml` for:
- CPU and memory allocation
- Additional storage volumes
- Network configuration
- UEFI/TPM settings

---

## Troubleshooting

### RKE2 Won't Start

Check RKE2 logs:

```bash
./tools/rke2-vm-manager.sh ssh
sudo journalctl -u rke2-server -f
```

Common issues:
- **Registry unreachable**: Verify host registry is running and accessible from VM
- **Firewall blocking**: Check firewall rules (ports 6443, 9345, 10250)
- **Insufficient resources**: Ensure VM has enough CPU/memory

### Kubeconfig Not Exported

Verify 9p mount:

```bash
sudo virsh console rke2-node-1

# Check mount
mount | grep kubeconfigshare

# Manually export
sudo cp /etc/rancher/rke2/rke2.yaml /mnt/host/kubeconfig/rke2.yaml
```

### Registry Connection Failed

Test registry from VM:

```bash
sudo virsh console rke2-node-1

# Test registry connectivity
curl http://192.168.122.1:5000/v2/_catalog

# Check registry config
cat /etc/rancher/rke2/registries.yaml
```

### VM Won't Boot

Check libvirt logs:

```bash
sudo virsh dumpxml rke2-node-1
sudo journalctl -u libvirtd -f
```

Console access:

```bash
sudo virsh console rke2-node-1
```

### Bootc Upgrade Failed

Check bootc status:

```bash
sudo virsh console rke2-node-1
sudo bootc status

# View bootc logs
sudo journalctl -u bootc-fetch -f
```

Rollback if needed:

```bash
sudo bootc rollback
sudo systemctl reboot
```

---

## Advanced Usage

### Custom RKE2 Version

Build with specific RKE2 version:

```bash
podman build \
  --build-arg RKE2_VERSION=v1.28.5+rke2r1 \
  -f Containerfile.rke2 \
  -t localhost:5000/exousia-rke2:v1.28.5 \
  .
```

### Air-gapped Installation

Pre-populate registry with required images:

```bash
# Get RKE2 image list (from VM)
sudo virsh console rke2-node-1
/var/lib/rancher/rke2/bin/rke2 images list

# Pull and push to local registry (on host)
for img in $(cat /tmp/rke2-images.txt); do
  podman pull $img
  podman tag $img localhost:5000/${img#*/}
  podman push localhost:5000/${img#*/}
done
```

### High Availability Setup

Create 3-node control plane:

1. Build server image for all 3 nodes
2. Configure first node as cluster init
3. Join remaining nodes with same token
4. Use external load balancer for API

### Storage Integration

Add persistent storage:

```bash
# Create additional disk
qemu-img create -f qcow2 /var/lib/libvirt/images/rke2-storage.qcow2 100G

# Attach to VM (edit libvirt-domain.xml)
# Inside VM, format and mount
sudo mkfs.xfs /dev/vdb
sudo mount /dev/vdb /mnt/host/storage
```

Use with local-path-provisioner:

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
```

### Monitoring with Prometheus

Deploy monitoring stack:

```bash
# Install kube-prometheus-stack
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install kube-prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace
```

### GitOps with Flux/ArgoCD

Bootstrap Flux on RKE2:

```bash
flux bootstrap github \
  --owner=<github-user> \
  --repository=fleet-infra \
  --branch=main \
  --path=clusters/rke2-bootc
```

---

## Additional Resources

### Official Documentation

- [RKE2 Documentation](https://docs.rke2.io/)
- [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)
- [bootc Upstream](https://github.com/containers/bootc)

### Community

- [RKE2 GitHub](https://github.com/rancher/rke2)
- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)

### Tools

- [bootc-image-builder](https://github.com/osbuild/bootc-image-builder)
- [libvirt](https://libvirt.org/)
- [Podman](https://podman.io/)

---

## License

This configuration is part of the Exousia project and is licensed under the MIT License.

## Contributing

Contributions welcome! Please submit issues and pull requests to the [Exousia repository](https://github.com/borninthedark/exousia).

---

**Built with bootc + RKE2**

*Immutable infrastructure for Kubernetes, powered by atomic updates.*
