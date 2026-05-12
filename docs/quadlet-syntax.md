# Quadlet Syntax Guide

Podman Quadlet lets you declare containers, volumes, and networks as systemd
unit files. Systemd generates the `podman run` commands automatically — no
compose files, no extra daemons.

## File Types

| Extension | Purpose | Systemd Unit |
|-----------|---------|--------------|
| `.container` | Container definition | `<name>.service` |
| `.volume` | Named volume | `<name>-volume.service` |
| `.network` | Podman network | `<name>-network.service` |

Place files in `~/.config/containers/systemd/` (user scope) or
`/etc/containers/systemd/` (system scope). Systemd picks them up on
`daemon-reload`.

## Container File Structure

```ini
[Unit]
Description=My service
After=my-db.service          # start order
Requires=my-db.service       # hard dependency

[Container]
Image=ghcr.io/org/app:latest
ContainerName=my-app
Network=exousia.network:alias=my-app
PublishPort=127.0.0.1:8080:8080
Volume=my-data.volume:/app/data
Environment=KEY=value
EnvironmentFile=%h/.config/my-app/my-app.env
Label=io.containers.autoupdate=registry

[Service]
Restart=always
TimeoutStartSec=300

[Install]
WantedBy=default.target
```

## Key Directives

### [Container]

| Directive | Example | Notes |
|-----------|---------|-------|
| `Image` | `ghcr.io/org/app:latest` | Full registry path required |
| `ContainerName` | `my-app` | Maps to `podman run --name` |
| `Network` | `exousia.network:alias=my-app` | Reference `.network` file + DNS alias |
| `PublishPort` | `127.0.0.1:8080:3000` | `host:container` — always bind to 127.0.0.1 |
| `Volume` | `my-data.volume:/app/data` | Reference `.volume` file for named volumes |
| `Volume` | `%h/.config/app:/config:z` | Bind mount with SELinux relabel |
| `Environment` | `DB_HOST=my-db` | Single env var |
| `EnvironmentFile` | `%h/.config/app/app.env` | Load env vars from file |
| `Exec` | `serve` | Override container CMD |
| `Label` | `io.containers.autoupdate=registry` | Enable `podman auto-update` |
| `ShmSize` | `128m` | Shared memory (needed by some postgres configs) |
| `ReadOnly` | `true` | Read-only root filesystem |
| `Tmpfs` | `/var/run/app` | Tmpfs mount for runtime state |
| `AddCapability` | `SYS_ADMIN` | Add Linux capability |

### [Unit]

| Directive | Example | Notes |
|-----------|---------|-------|
| `After` | `my-db.service` | Start after this unit |
| `Requires` | `my-db.service` | Hard dependency — if db fails, this stops |
| `Wants` | `my-db.service` | Soft dependency — this starts regardless |

### [Service]

| Directive | Example | Notes |
|-----------|---------|-------|
| `Restart` | `always` | Restart policy |
| `TimeoutStartSec` | `300` | Allow time for image pulls |

### [Install]

| Directive | Example | Notes |
|-----------|---------|-------|
| `WantedBy` | `default.target` | Auto-start on boot (with linger) |

Comment out `[Install]` to prevent boot start while keeping the file installed.

## Volume File

Minimal — just declares a named volume:

```ini
[Volume]
```

Reference from containers as `my-data.volume:/mount/point`.

## Network File

```ini
[Network]
NetworkName=exousia
Subnet=10.89.1.0/24
```

Reference from containers as `exousia.network:alias=<name>`.

## Specifiers

| Specifier | Expands To |
|-----------|------------|
| `%h` | User home directory (`/var/home/uryu`) |
| `%n` | Unit name |
| `%N` | Unit name without suffix |

## Common Patterns

### Caddy reverse proxy port

Caddy runs inside the container network. Always use the **container-internal
port**, not the host-mapped port:

```caddyfile
# Container: PublishPort=127.0.0.1:8233:8080
# Caddyfile:
temporal.exousia.local {
    reverse_proxy temporal-ui:8080    # internal port, NOT 8233
}
```

### SELinux bind mounts

Add `:z` to bind-mounted host paths so podman relabels for SELinux:

```ini
Volume=%h/.config/app:/config:z
```

### Secrets outside version control

Use `EnvironmentFile` pointing to a file not tracked by git:

```ini
EnvironmentFile=%h/.config/my-app/my-app.env
```

### Service group (multi-container stack)

Define dependency chains with `After` + `Requires`:

```text
db.container         → no dependencies
redis.container      → no dependencies
app.container        → After=db.service redis.service
                       Requires=db.service redis.service
```

Start the last service in the chain — systemd pulls in all dependencies.

## Creating a New Quadlet

1. Create `.container` file in `overlays/deploy/`
2. Create `.volume` files for each persistent volume
3. Add the service group to `justfile` `_expand_group()` (if multi-container)
4. Add Caddy entry in `overlays/deploy/caddy/Caddyfile` (use internal port)
5. Add image namespace to `/etc/containers/policy.json`
6. Pull the image: `podman pull <image>`
7. Engage: `just engage <name>`
8. Test: `curl -sk https://<name>.exousia.local`

---

**[Back to Documentation Index](README.md)** | **[Back to Main README](../README.md)**
