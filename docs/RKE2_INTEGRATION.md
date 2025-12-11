# RKE2 Integration Guide

**Immutable Kubernetes Infrastructure with Atomic Updates**

## Overview

RKE2 (Rancher Kubernetes Engine 2) is integrated into all Exousia bootc images by default, providing an immutable Kubernetes platform with atomic update capabilities.

## Features

- **Enabled by Default**: All bootc images include RKE2 out-of-the-box
- **Atomic Updates**: Upgrade entire cluster with `bootc upgrade`
- **Instant Rollback**: Boot into previous version with `bootc rollback`
- **Unified Management**: Single `rke2_ops` tool for all operations
- **Desktop & Server**: Works on laptops and servers alike

## Configuration

### Enabling/Disabling RKE2

RKE2 is enabled by default in `adnyeus.yml`:

```yaml
build:
  enable_plymouth: true
  enable_rke2: true  # Enable RKE2 Kubernetes
```

To disable RKE2:

```yaml
build:
  enable_rke2: false
```

### RKE2 Configuration Files

Configuration files are located in `custom-configs/rke2/`:

- **`registries.yaml`** - Container registry mirrors (points to host registry at 192.168.122.1:5000)
- **`config.yaml`** - RKE2 server configuration (CNI, networking, TLS SANs)
- **`kubeconfig-export.conf`** - Systemd drop-in for kubeconfig export

## Usage

### On Desktop/Laptop

After building and booting an Exousia image with RKE2:

```bash
# Check RKE2 status
sudo systemctl status rke2-server

# Access the cluster
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
kubectl get nodes

# View cluster info
kubectl cluster-info
```

### Management with rke2_ops

The `rke2_ops` Python tool provides unified management:

```bash
# Registry management (for VM deployments)
rke2_ops registry start
rke2_ops registry status
rke2_ops registry info

# VM management (for testing)
rke2_ops vm build
rke2_ops vm create
rke2_ops vm start
rke2_ops vm status

# Kubeconfig management
rke2_ops kubeconfig

# Full quickstart
rke2_ops quickstart
```

## Architecture

### Desktop/Laptop Deployment

```
┌────────────────────────────────┐
│     Fedora bootc + Sway        │
│                                │
│  ┌──────────────────────────┐  │
│  │  RKE2 Server             │  │
│  │  (runs natively)         │  │
│  │                          │  │
│  │  kubectl → localhost     │  │
│  └──────────────────────────┘  │
│                                │
│  Desktop apps + k8s workloads  │
└────────────────────────────────┘
```

### VM-Based Deployment

```
┌──────────────────────────────────────────┐
│           Host (Gentoo/Fedora)           │
│                                          │
│  ┌──────────┐      ┌────────────────┐   │
│  │ Registry │◄─────┤ libvirt/KVM    │   │
│  │ :5000    │      │  ┌──────────┐  │   │
│  └──────────┘      │  │ Fedora   │  │   │
│                    │  │ bootc    │  │   │
│  ┌──────────┐      │  │          │  │   │
│  │Kubeconfig│◄─────┼──┤ + RKE2   │  │   │
│  │(9p share)│      │  └──────────┘  │   │
│  └──────────┘      └────────────────┘   │
└──────────────────────────────────────────┘
```

## Operations

### Upgrading the Cluster

Build a new image version:

```bash
# Modify adnyeus.yml or package definitions
# Build new image
make build-bootc

# Push to registry
podman tag exousia:latest localhost:5000/exousia:v2
podman push localhost:5000/exousia:v2
```

Inside the system:

```bash
# Switch to new image
sudo bootc switch localhost:5000/exousia:v2

# Or upgrade to latest
sudo bootc upgrade

# Reboot to apply
sudo systemctl reboot
```

### Rolling Back

If an upgrade fails or causes issues:

```bash
# Automatic rollback on boot failure
# bootc will automatically boot previous deployment

# Manual rollback
sudo bootc rollback
sudo systemctl reboot
```

## Use Cases

### Local Development

Run a full Kubernetes cluster on your laptop:

- Test deployments locally before production
- Develop Helm charts and operators
- Learn Kubernetes without cloud costs
- CI/CD integration testing

### Immutable Infrastructure

Production-grade immutable infrastructure:

- Version entire k8s stack as container images
- Promote images through dev → staging → prod
- Instant rollback on failures
- Reproducible cluster deployments

### Edge Computing

Kubernetes at the edge:

- Immutable OS + k8s for edge nodes
- Remote updates with atomic rollback
- Minimal resource footprint
- Offline operation support

## Integration Details

### What Gets Installed

When `enable_rke2: true`:

1. **RKE2 Binaries** - Server components in `/usr/local/bin`
2. **kubectl** - In `/var/lib/rancher/rke2/bin`
3. **Configuration** - Registry mirrors, server config, systemd units
4. **Firewall Rules** - Ports 6443, 9345, 10250, 2379-2380
5. **SELinux Contexts** - Proper labeling for `/var/lib/rancher/rke2`
6. **Bootc Kargs** - Cgroups v2 and swap accounting
7. **Management Tools** - `rke2_ops` Python script

### Systemd Integration

RKE2 server service is enabled and starts with graphical.target:

```bash
# Service control
sudo systemctl status rke2-server
sudo systemctl start rke2-server
sudo systemctl stop rke2-server

# View logs
sudo journalctl -u rke2-server -f
```

### Network Configuration

Default RKE2 networking:

- **Pod CIDR**: 10.42.0.0/16
- **Service CIDR**: 10.43.0.0/16
- **CNI**: Canal (default)
- **DNS**: 10.43.0.10

Customize in `custom-configs/rke2/config.yaml`.

## Testing

### Automated Tests

RKE2 integration tests are in `custom-tests/image_content.bats`:

```bash
# Run all tests
make test

# Run RKE2-specific tests
bats custom-tests/image_content.bats -f "RKE2"
```

Tests verify:
- RKE2 binaries installed
- Configuration files present
- Systemd integration
- Firewall rules
- SELinux contexts
- Management tools

### Manual Testing

Build and test RKE2 image:

```bash
# Build image
make build-bootc

# Run container for testing
podman run --rm -it exousia:latest /bin/bash

# Inside container
ls -la /usr/local/bin/rke2
ls -la /etc/rancher/rke2/
systemctl list-unit-files | grep rke2
```

## Dedicated RKE2 Images

For minimal server deployments without desktop:

```yaml
# yaml-definitions/rke2-bootc.yml
name: exousia-rke2-bootc
description: Minimal Fedora bootc with RKE2

desktop:
  window_manager: null
  desktop_environment: null
  include_common: false

build:
  enable_plymouth: false
  enable_rke2: true
```

Build:

```bash
make rke2-build
```

This creates a minimal image with only RKE2, no desktop environment.

## Troubleshooting

### RKE2 Won't Start

Check service status:

```bash
sudo systemctl status rke2-server
sudo journalctl -u rke2-server -f
```

Common issues:
- Ports already in use (6443, 9345)
- SELinux denials (check `ausearch -m avc`)
- Firewall blocking access

### Can't Access Cluster

Verify kubeconfig:

```bash
ls -la /etc/rancher/rke2/rke2.yaml
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
kubectl cluster-info
```

### Image Too Large

Disable RKE2 for smaller images:

```yaml
build:
  enable_rke2: false
```

RKE2 adds ~500MB to the image size.

## References

- [RKE2 Documentation](https://docs.rke2.io/)
- [Bootc Documentation](https://containers.github.io/bootc/)
- [Exousia README](../README.md)
- [YAML Manifests](../yaml-definitions/)

## Contributing

Improvements to RKE2 integration are welcome:

- Enhanced configuration options
- Additional CNI plugins
- High availability setups
- Air-gapped deployments

Submit PRs to the [Exousia repository](https://github.com/borninthedark/exousia).
