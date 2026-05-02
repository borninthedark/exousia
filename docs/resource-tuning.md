# Resource Tuning

Living document for Quadlet and runner resource allocation on the Exousia
local development stack.

## Host Capacity

| Resource | Total | Reserved (host) | Available (containers) |
|----------|-------|-----------------|------------------------|
| CPU | 8 cores | 2 cores | 6 cores |
| RAM | 32 GB | ~5 GB | ~27 GB |

Host reservation covers the OS, Forgejo, registry, and desktop (Sway +
Waybar + kitty). Adjust if running additional stacks (Plane, Temporal,
Ollama).

## Forgejo Runner Job Containers

The runner's `container.options` in `/data/config.yaml` controls per-job
resource limits. Changes take effect after `systemctl --user restart
forgejo-runner`.

### Profiles

| Profile | Capacity | CPUs/job | RAM/job | Use case |
|---------|----------|----------|---------|----------|
| Default | 2 | 3 | 12GB | Parallel CI (Bambietta + Askin) |
| Heavy build | 1 | 6 | 24GB | Full image build (Gremmy) |

### Switching profiles

```bash
# Heavy build (single job, max resources)
podman exec forgejo-runner sed -i 's/capacity: .*/capacity: 1/' /data/config.yaml
podman exec forgejo-runner sed -i 's/--cpus [0-9]* --memory [0-9]*g/--cpus 6 --memory 24g/' /data/config.yaml
systemctl --user restart forgejo-runner

# Default (parallel CI)
podman exec forgejo-runner sed -i 's/capacity: .*/capacity: 2/' /data/config.yaml
podman exec forgejo-runner sed -i 's/--cpus [0-9]* --memory [0-9]*g/--cpus 3 --memory 12g/' /data/config.yaml
systemctl --user restart forgejo-runner
```

### Guidelines

- **capacity × CPUs/job + host reserved = total cores** — never overcommit
  CPU. Memory can be slightly overcommitted since not all jobs peak
  simultaneously.
- The `buildah-layers` volume persists across restarts. Changing capacity
  does not invalidate the layer cache.
- Restarting the runner while a job is running will kill that job. Check
  `podman ps` for active job containers before restarting.

## Quadlet Service Defaults

Quadlet containers do not set explicit resource limits — they share the
host's cgroup slice. If a service is misbehaving:

```bash
# Inspect current resource usage
systemctl --user status <service>.service
podman stats --no-stream <container-name>

# Set transient limits (until next restart)
systemctl --user set-property <service>.service CPUQuota=200% MemoryMax=4G
```

For persistent limits, add to the `.container` quadlet file:

```ini
[Service]
CPUQuota=200%        # 2 cores max
MemoryMax=4G         # 4GB hard limit
MemoryHigh=3G        # throttle above 3GB (soft limit)
```

### Service resource expectations

| Service | Typical CPU | Typical RAM | Notes |
|---------|-------------|-------------|-------|
| Forgejo | <0.5 core | 200-400 MB | Spikes during git operations |
| Forgejo Runner | <0.1 core | 50 MB | Daemon only; job containers are separate |
| Registry | <0.1 core | 30 MB | I/O bound during push/pull |
| Ollama (idle) | 0 | ~300 MB | Model loaded in memory |
| Ollama (inference) | 4-8 cores | 5-8 GB | Depends on model size |
| Open WebUI | <0.2 core | 200 MB | Node.js frontend |
| Temporal (3 svc) | <0.5 core | 400 MB | Mostly idle unless running workflows |
| Plane (13 svc) | 1-2 cores | 2-3 GB | Postgres + multiple Node services |

### Avoiding contention

- Don't run Ollama inference during heavy builds — both are CPU/RAM
  intensive. Stop Ollama or use the heavy build profile.
- Plane's 13 containers add ~2-3 GB baseline. If running Plane + builds,
  use the default profile (capacity 2, 3 CPUs / 12GB).
- K3s is privileged and unbound by default. Set resource limits if running
  alongside other stacks.

## Monitoring

```bash
# Overall system
podman stats --no-stream

# Specific service journal
journalctl --user -u <service>.service -f

# cgroup resource accounting
systemd-cgtop --user
```

---

**[Back to Documentation Index](README.md)** | **[Forgejo Runner](forgejo-runner.md)** | **[Quadlet Services](quadlet-services.md)**
