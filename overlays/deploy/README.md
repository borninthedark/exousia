# Deploy Overlay

Podman Quadlet definitions for self-hosted apps. This overlay ships in the
image at `/usr/share/exousia/deploy/` and is also available in the repo at
`overlays/deploy/`.

## Lifecycle Commands

| Command | Action | Reboot behavior |
|---------|--------|-----------------|
| `just install <app>` | Copy quadlet files, reload systemd | Starts on boot |
| `just engage <app>` | Install + start now | Starts on boot |
| `just disengage <app>` | Stop now, keep files | Restarts on boot |
| `just remove <app>` | Stop + delete files | Gone |

Service groups (`forgejo`, `temporal`) expand to their full dependency
stacks automatically.

## DNS + HTTPS

All apps resolve as `<app>.<hostname>.local` (e.g. `forgejo.exousia.local`).
A wildcard DNS record (`*.exousia.local → 127.0.0.1`) means no DNS changes
are needed — only a Caddyfile entry per app.

| App | URL | Backend |
|-----|-----|---------|
| Forgejo | `https://forgejo.exousia.local` | `forgejo:3000` |
| Registry | `https://registry.exousia.local` | `registry:5000` |
| Plane | `https://plane.exousia.local` | `plane-proxy:8080` |
| Ollama | `https://ollama.exousia.local` | `ollama:11434` |
| Open WebUI | `https://webui.exousia.local` | `open-webui:3080` |
| Temporal | `https://temporal.exousia.local` | `temporal-ui:8233` |

## Quadlets

| File | Service | Purpose |
|------|---------|---------|
| `coredns.container` | CoreDNS | Wildcard DNS for `*.exousia.local` (port 5354) |
| `caddy.container` | Caddy | HTTPS reverse proxy with `tls internal` |
| `forgejo.container` | Forgejo | Git forge (`forgejo.exousia.local`) |
| `forgejo-db.container` | Forgejo DB | PostgreSQL for Forgejo |
| `forgejo-runner.container` | Forgejo Runner | Forgejo Actions CI ([setup](../../docs/forgejo-runner.md)) |
| `exousia-registry.container` | Registry | OCI registry (`registry.exousia.local`) |
| `ollama.container` | Ollama | LLM inference server |
| `open-webui.container` | Open WebUI | Chat UI for Ollama |
| `plane-*.container` | Plane | Project management stack |
| `temporal-*.container` | Temporal | Workflow orchestration |

## Quick Start (fresh setup)

```bash
# Prerequisites (one-time, requires sudo)
sudo sysctl -w net.ipv4.ip_unprivileged_port_start=80
loginctl enable-linger $(whoami)

# Start DNS + reverse proxy
just dns-start

# Trust Caddy's internal CA (for browser HTTPS)
just dns-trust-ca

# Engage apps
just engage forgejo
just engage ollama
just engage open-webui
```

## See Also

- [Local Build Pipeline](../../docs/local-build-pipeline.md) — full setup guide
- [Quadlet Services Reference](../../docs/quadlet-services.md) — ports, volumes, policy
- [Temporal Orchestration Plan](../../docs/plan-temporal-orchestration.md)
