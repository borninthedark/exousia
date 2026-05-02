# Forgejo Runner Setup

The Forgejo Actions runner executes Vandenreich pipeline workflows
(`.forgejo/workflows/`) on the local machine. It connects to the Forgejo
instance on `exousia.network` and uses the host's Podman socket for
container-based job execution.

## Image Source

The runner image is hosted on Forgejo's own registry at
`code.forgejo.org/forgejo/runner`, **not** on Codeberg's container registry
(`codeberg.org/forgejo`). The `codeberg.org/forgejo/runner` path does not
publish container images — only the source code lives there.

- **Source code**: <https://codeberg.org/forgejo/runner>
- **Container images**: `code.forgejo.org/forgejo/runner`
- **Documentation**: <https://forgejo.org/docs/latest/admin/actions/#forgejo-runner>

## Prerequisites

1. **Container image policy** — `code.forgejo.org/forgejo` must be in
   `/etc/containers/policy.json` (requires sudo + FIDO key):

   ```json
   "code.forgejo.org/forgejo": [{"type": "insecureAcceptAnything"}]
   ```

2. **Podman socket** — the runner mounts the host's Podman socket as a
   Docker-compatible socket. It must be enabled:

   ```bash
   systemctl --user enable --now podman.socket
   ```

   This creates `/run/user/1000/podman/podman.sock`, which the quadlet
   mounts as `/var/run/docker.sock` inside the runner container.

3. **Forgejo Actions enabled** — the Forgejo instance must have Actions
   enabled in `app.ini` (already configured for Exousia).

## One-Time Registration

The runner must be registered before it can accept jobs. Registration
state persists in the `/data/.runner` file inside the volume.

### Step 1: Get a registration token

From the Forgejo API (requires an access token with repo scope):

```bash
curl -s -H "Authorization: token ${FORGEJO_TOKEN}" \
  http://localhost:3000/api/v1/repos/uryu/exousia/actions/runners/registration-token
```

Or from the Forgejo UI: **Repository Settings → Actions → Runners → Create
new runner**.

Registration tokens are single-use and expire. Generate a fresh one each
time you need to re-register.

### Step 2: Register the runner

```bash
podman run --rm \
  -v systemd-forgejo-runner-data:/data \
  --network systemd-exousia \
  code.forgejo.org/forgejo/runner:9.1.1 \
  forgejo-runner register \
    --no-interactive \
    --instance http://forgejo:3000 \
    --token <REGISTRATION_TOKEN> \
    --name exousia-runner \
    --labels "ubuntu-latest:docker://node:20"
```

This writes `/data/.runner` with the runner's UUID, auth token, and label
configuration. The file persists in the `forgejo-runner-data` volume and
survives container restarts.

### Step 3: Generate the daemon config

The runner v9 requires an explicit `config.yaml` with several settings
adjusted for the Podman rootless environment:

```bash
podman run --rm \
  -v systemd-forgejo-runner-data:/data \
  code.forgejo.org/forgejo/runner:9.1.1 \
  sh -c 'forgejo-runner generate-config > /data/config.yaml && \
    sed -i "s|docker_host: \"-\"|docker_host: \"\"|" /data/config.yaml && \
    sed -i "s|file: .runner|file: /data/.runner|" /data/config.yaml && \
    sed -i "s|privileged: false|privileged: true|" /data/config.yaml && \
    sed -i "s|valid_volumes: \[\]|valid_volumes:\n    - \"**\"|" /data/config.yaml'
```

The key changes from defaults:

| Setting | Default | Changed To | Reason |
|---------|---------|------------|--------|
| `docker_host` | `"-"` | `""` | Auto-detect without socket forwarding to job containers |
| `runner.file` | `.runner` | `/data/.runner` | Absolute path required with `keep-id` (can't write to `/`) |
| `privileged` | `false` | `true` | Required for buildah in Gremmy build jobs |
| `valid_volumes` | `[]` | `["**"]` | Allow job containers to mount workspace volumes |

## Daemon Configuration Reference

The generated `/data/config.yaml` controls how the runner daemon operates.
Key settings for the Podman rootless environment:

### Runner section

```yaml
runner:
  file: /data/.runner        # absolute path — relative paths fail with keep-id
  capacity: 1                # concurrent jobs (increase for parallel pipelines)
  timeout: 3h                # max job duration
  shutdown_timeout: 3h       # graceful shutdown window for running jobs
  fetch_interval: 2s         # polling interval for new jobs
```

- `file` **must** be an absolute path (`/data/.runner`). The default
  relative path `.runner` fails because the runner process runs as uid 1000
  via `keep-id` and cannot write to the container's root filesystem.

### Container section

```yaml
container:
  network: ""                # auto-create per-job networks
  privileged: true           # required for buildah/podman-in-podman
  docker_host: ""            # auto-detect, do NOT mount into job containers
  valid_volumes:
    - "**"                   # allow job containers to mount any volume
```

- `docker_host` — controls how the runner communicates with the container
  runtime and whether it forwards the socket into job containers.

  **This setting is the most critical for rootless Podman.** The wrong
  value causes `mkdir /var/run/docker.sock: permission denied` when
  creating job containers. Here's why:

  When `docker_host` is set to an explicit path like
  `unix:///var/run/docker.sock`, the runner daemon can connect to the
  Podman API socket fine (because the quadlet mounts it at that path).
  However, the runner also tries to **forward** that socket into every job
  container it creates — it passes a bind-mount flag like
  `-v /var/run/docker.sock:/var/run/docker.sock` to the `docker create`
  call. In rootless Podman, the container runtime cannot `mkdir` at
  `/var/run/docker.sock` inside the job container's filesystem because the
  process runs as a non-root user. This results in:

  ```text
  failed to create container: 'Error response from daemon: make cli opts():
  making volume mountpoint for volume /var/run/docker.sock:
  mkdir /var/run/docker.sock: permission denied'
  ```

  **Resolution:** Set `docker_host` to `""` (empty string). This tells the
  runner to auto-detect an available Docker/Podman socket without attempting
  to mount it into job containers. The runner itself still communicates with
  Podman via the socket mounted by the quadlet, but job containers don't
  get the socket forwarded — which is the correct behavior since job
  containers don't need Docker-in-Docker access.

  | Value | Behavior | Rootless Podman |
  |-------|----------|-----------------|
  | `""` or `"-"` | Auto-detect, no mount forwarding | Works |
  | `"automount"` | Auto-detect + mount into job containers | Fails (permission denied) |
  | `"unix:///var/run/docker.sock"` | Explicit path + mount into job containers | Fails (permission denied) |

- `privileged: true` — required for job containers that run buildah or
  podman (e.g., Gremmy build jobs). Without this, container builds inside
  jobs fail with permission errors.

- `valid_volumes` — controls which volumes job containers can mount. The
  default (`[]`) blocks all volume mounts. Setting `"**"` allows any volume,
  which is needed for job containers to access the workspace and build cache.

### Cache section

```yaml
cache:
  enabled: true              # enables ACTIONS_CACHE_URL for job containers
  port: 0                    # random port for internal cache server
```

The cache server runs inside the runner container and provides
`ACTIONS_CACHE_URL` to job containers for the
`actions/cache` action. It starts automatically but logs a non-fatal
warning (`Could not start the cache server`) if the port is already in use.

## Quadlet Configuration

The runner quadlet (`overlays/deploy/forgejo-runner.container`) is the
systemd unit definition that manages the runner container lifecycle:

```ini
[Unit]
Description=Forgejo Actions runner
After=forgejo.service
Requires=forgejo.service

[Container]
Image=code.forgejo.org/forgejo/runner:9.1.1
ContainerName=forgejo-runner
Volume=forgejo-runner-data.volume:/data:U
Volume=%t/podman/podman.sock:/var/run/docker.sock:ro
Network=exousia.network:alias=forgejo-runner
Label=io.containers.autoupdate=registry
UserNS=keep-id
SecurityLabelDisable=true
WorkingDir=/data
Exec=forgejo-runner -c /data/config.yaml daemon

[Service]
Restart=always
TimeoutStartSec=300
```

### Podman-Specific Quadlet Directives

| Directive | Value | Purpose |
|-----------|-------|---------|
| `UserNS=keep-id` | - | Maps the container's uid to the host user. Without this, the Podman socket (owned by uid 1000 on the host) appears as a different uid inside the container and access is denied. |
| `SecurityLabelDisable=true` | - | Disables SELinux labeling. Required because SELinux blocks cross-container socket access even when POSIX permissions allow it. |
| `Volume=...:/data:U` | `:U` flag | Recursively chowns volume contents to match the container user's uid mapping. Without `:U`, files created by earlier runs (without `keep-id`) are owned by a different mapped uid and the runner cannot write to `/data/.runner` or `/data/config.yaml`. |
| `Volume=%t/podman/podman.sock:/var/run/docker.sock:ro` | `:ro` | Mounts the host's Podman socket as the Docker-compatible socket path. `%t` expands to `$XDG_RUNTIME_DIR` (`/run/user/1000`). Read-only is sufficient — the runner only issues API calls, it doesn't modify the socket. |
| `WorkingDir=/data` | `/data` | Sets the container working directory. The runner resolves relative paths (like `.env`) against this directory. |
| `Exec=forgejo-runner -c /data/config.yaml daemon` | - | Overrides the default entrypoint (which just prints help) to run the daemon with the generated config. |

### Why These Settings Exist

The Forgejo runner image was designed for Docker, not rootless Podman.
These quadlet settings bridge the gap:

1. **UID mapping** — Docker runs containers as root by default, so the
   runner image assumes uid 0 can read/write everything. Rootless Podman
   maps the host user into the container via user namespaces. `keep-id`
   ensures the container's uid 1000 maps to the host's uid 1000, matching
   the Podman socket ownership.

2. **SELinux** — Fedora enables SELinux by default. The runner container
   needs to communicate with the host's Podman socket (a cross-domain
   operation), which SELinux blocks. `SecurityLabelDisable=true` is the
   simplest fix for a local dev runner.

3. **Volume ownership** — Volumes created without `keep-id` have files
   owned by the root-mapped uid. When the container switches to `keep-id`,
   those files appear as a different (unmapped) uid. The `:U` flag fixes
   this by chowning on each start.

## Starting the Runner

```bash
just engage forgejo-runner    # or: just forgejo-start (starts all Forgejo services)
```

Verify it's running:

```bash
systemctl --user status forgejo-runner.service
```

The runner should show `declared successfully` and `[poller 0] launched`
in the logs:

```bash
journalctl --user -eu forgejo-runner.service -n 10
```

## Re-Registration

If the runner's registration is invalidated (e.g., token expired, Forgejo
DB reset), you need to re-register:

```bash
# Remove stale registration
podman volume rm systemd-forgejo-runner-data

# Re-create volume, register, and generate config
# (repeat Steps 1-3 from One-Time Registration above)
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `manifest unknown` on pull | Wrong image registry | Use `code.forgejo.org/forgejo/runner`, not `codeberg.org` |
| `permission denied` on socket | Podman socket not running | `systemctl --user enable --now podman.socket` |
| `permission denied` on `/data/.runner` | Volume ownership mismatch with `keep-id` | Use `:U` volume flag |
| `docker_host config was invalid` | Missing or default daemon config | Generate `/data/config.yaml` with explicit `docker_host` |
| `start-limit-hit` | Rapid restart loop from earlier failures | `systemctl --user reset-failed forgejo-runner.service` |
| `mkdir /var/run/docker.sock: permission denied` | `docker_host` set to explicit path or `automount` — runner tries to forward socket into job containers, rootless podman can't mkdir | Set `docker_host: ""` in config.yaml (empty = auto-detect without forwarding) |
| Runner exits immediately (status 0) | Image default cmd is `forgejo-runner` (shows help) | Quadlet must set `Exec=forgejo-runner daemon` |
| `Could not start the cache server` | Cache port conflict (non-fatal warning) | Ignorable — cache is disabled but jobs still run |

---

**[Back to Documentation Index](README.md)** | **[Quadlet Services](quadlet-services.md)**
