# K3s Lightweight Kubernetes

K3s runs as a rootless Podman container for CKA exam preparation and local
Kubernetes workload testing.

## Architecture

- Single-node K3s server (no external agents)
- Traefik disabled (`--disable=traefik`) — Caddy handles ingress
- API server exposed on `127.0.0.1:6443`
- Web UI proxied through Caddy at `https://k3s.exousia.local`
- Protected by Authelia SSO

## Container Configuration

The K3s container runs privileged with full network and cgroup capabilities:

```ini
[Container]
Image=docker.io/rancher/k3s:latest
ContainerName=k3s
Volume=k3s-data.volume:/var/lib/rancher/k3s
Volume=k3s-data.volume:/etc/rancher
PublishPort=127.0.0.1:6443:6443
Network=exousia.network:alias=k3s
Environment=K3S_KUBECONFIG_MODE=644
Exec=server --disable=traefik --tls-san=localhost --tls-san=exousia
SecurityLabelDisable=true
AddCapability=NET_ADMIN NET_RAW SYS_ADMIN
PodmanArgs=--privileged
```

## Prerequisites

### Cgroup v2 cpuset delegation

K3s requires cpuset cgroup delegation for rootless containers. A systemd
drop-in at `/usr/lib/systemd/system/user@.service.d/delegate.conf` enables
this:

```ini
[Service]
Delegate=cpu cpuset io memory pids
```

This is baked into the Exousia image build. For manual setup on a live system:

```bash
sudo mkdir -p /etc/systemd/system/user@.service.d
sudo tee /etc/systemd/system/user@.service.d/delegate.conf <<EOF
[Service]
Delegate=cpu cpuset io memory pids
EOF
sudo systemctl daemon-reload
```

### kubectl

kubectl is built into the Exousia image (`base-core.yml` package list). It is
not layered via rpm-ostree.

## Usage

### Start K3s

```bash
just engage k3s
```

### Get kubeconfig

```bash
podman exec k3s cat /etc/rancher/k3s/k3s.yaml > ~/.kube/config
# Fix the server address if needed
sed -i 's|127.0.0.1|localhost|g' ~/.kube/config
```

### Verify cluster

```bash
kubectl get nodes
kubectl get pods -A
```

### Deploy a test workload

```bash
kubectl create deployment nginx --image=nginx
kubectl expose deployment nginx --port=80 --type=NodePort
kubectl get svc nginx
```

Services exposed via NodePort are accessible on `localhost:<nodePort>` since
K3s binds to the host network via the published port range.

### Stop K3s

```bash
just disengage k3s
```

## Networking

K3s is on `exousia.network` with alias `k3s`. Other containers can reach the
K3s API at `https://k3s:6443`. The Caddy reverse proxy handles external
access with TLS termination and `tls_insecure_skip_verify` for the self-signed
K3s API certificate.

Services deployed inside K3s that use NodePort or LoadBalancer types are
accessible from the host via `localhost:<port>` (ports published through
the container).

## Persistent Data

All K3s state is stored in the `k3s-data` named volume:

- `/var/lib/rancher/k3s` — cluster data, etcd, manifests
- `/etc/rancher` — kubeconfig and server configuration

Data persists across container restarts. Only `podman volume rm k3s-data`
destroys it.

## Monitoring

- Uptime Kuma: TCP monitor on `k3s:6443`
- Dashy: `https://k3s.exousia.local` (Infrastructure section, status check
  disabled — K3s API requires mTLS which Dashy cannot perform)
- Status page: included in Infrastructure group
