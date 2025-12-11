# RKE2 on Fedora Bootc - Quick Start

**30-second setup for a local Kubernetes cluster**

## TL;DR

```bash
make rke2-quickstart
export KUBECONFIG=~/.kube/rke2-config
kubectl get nodes
```

## Manual Steps

### 1. Start Registry (30 seconds)

```bash
./tools/setup-rke2-registry.sh start
```

**What this does:**
- Starts Podman registry on `192.168.122.1:5000`
- VMs can pull images from your host
- Survives VM rebuilds

### 2. Build & Push Image (3-5 minutes)

```bash
make rke2-build
make rke2-push
```

**What this does:**
- Builds Fedora bootc image with RKE2
- Pushes to local registry at `localhost:5000`

### 3. Build VM Disk (2-3 minutes)

```bash
make rke2-vm-build
```

**What this does:**
- Creates qcow2 disk image from bootc container
- Disk: `/var/lib/libvirt/images/rke2-node-1.qcow2`
- Size: 50GB (customizable)

### 4. Create & Start VM (2 minutes)

```bash
make rke2-vm-create
make rke2-vm-start
```

**What this does:**
- Defines libvirt VM with 4 CPU, 8GB RAM
- Mounts 9p shares for kubeconfig
- Boots the bootc image

### 5. Get Kubeconfig (immediate)

Wait ~2 minutes for RKE2 to start, then:

```bash
make rke2-kubeconfig
```

**What this does:**
- Copies kubeconfig from VM to `~/.kube/rke2-config`
- Updates server address to VM IP
- Ready to use with kubectl

### 6. Use Cluster

```bash
export KUBECONFIG=~/.kube/rke2-config
kubectl cluster-info
kubectl get nodes
kubectl get pods -A
```

## Common Operations

### Check Status

```bash
# VM status
make rke2-vm-status

# SSH into VM
./tools/rke2-vm-manager.sh ssh

# Inside VM: Check RKE2
rke2-status
```

### Stop/Start

```bash
# Stop VM
make rke2-vm-stop

# Start VM
make rke2-vm-start

# Restart
./tools/rke2-vm-manager.sh restart
```

### Upgrade

```bash
# Build new image version
make rke2-build
podman tag exousia-rke2:latest localhost:5000/exousia-rke2:v2
podman push localhost:5000/exousia-rke2:v2

# SSH into VM
./tools/rke2-vm-manager.sh ssh

# Upgrade
sudo bootc switch localhost:5000/exousia-rke2:v2
sudo bootc upgrade
sudo systemctl reboot
```

### Rollback

```bash
# SSH into VM
./tools/rke2-vm-manager.sh ssh

# Rollback to previous version
sudo bootc rollback
sudo systemctl reboot
```

### Clean Up

```bash
# Destroy VM (keeps disk)
./tools/rke2-vm-manager.sh destroy

# Purge everything
./tools/rke2-vm-manager.sh purge
./tools/setup-rke2-registry.sh stop
```

## Troubleshooting

### RKE2 not starting?

```bash
# SSH into VM
./tools/rke2-vm-manager.sh ssh

# Check logs
sudo journalctl -u rke2-server -f

# Check status
rke2-status
```

### Can't connect to cluster?

```bash
# Verify VM IP
sudo virsh domifaddr rke2-node-1

# Re-fetch kubeconfig
make rke2-kubeconfig

# Test from inside VM
./tools/rke2-vm-manager.sh ssh
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
kubectl get nodes
```

### Registry issues?

```bash
# Check registry status
./tools/setup-rke2-registry.sh status

# Test from host
curl http://192.168.122.1:5000/v2/_catalog

# Test from VM
./tools/rke2-vm-manager.sh ssh
curl http://192.168.122.1:5000/v2/_catalog
```

## Next Steps

- **Deploy applications**: `kubectl apply -f your-app.yaml`
- **Install Helm**: `kubectl apply -f https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3`
- **Setup monitoring**: Install Prometheus/Grafana
- **Add more nodes**: Build agent images and join cluster
- **GitOps**: Bootstrap Flux or ArgoCD

## Resources

- [Full Documentation](../../docs/RKE2_BOOTC_SETUP.md)
- [RKE2 Docs](https://docs.rke2.io/)
- [bootc Docs](https://containers.github.io/bootc/)

---

**Built with Exousia**

*Immutable Kubernetes infrastructure in minutes*
