# Deploy Overlay

Podman Quadlet container definitions for local infrastructure services.

## Quadlets

| File | Service | Purpose |
|------|---------|---------|
| `forgejo.container` | Forgejo | Local Git forge for development |
| `forgejo-runner.container` | Forgejo Runner | Executes Forgejo Actions workflows ([setup guide](../../docs/forgejo-runner.md)) |
| `exousia-registry.container` | Container Registry | Local OCI registry at `localhost:5000` |
| `freebsd.container` | FreeBSD | FreeBSD 14.4 runtime environment on the shared `exousia.network` |
| `plane-*.container` | Plane | Local project planning stack on the shared `exousia.network` |
| `plane-*.volume` | Plane | Persistent Plane data volumes for Postgres, Valkey, RabbitMQ, and MinIO |
| `plane.env.example` | Plane | Example environment file for the Quadlet-managed Plane stack |
| `temporal-server.container` | Temporal | Durable workflow engine for LLM agent orchestration |
| `temporal-db.container` | Temporal | Temporal PostgreSQL persistence |
| `temporal-db-data.volume` | Temporal | Persistent Temporal database storage |
| `temporal-ui.container` | Temporal | Temporal web dashboard |
| `open-webui.container` | Open WebUI | Chat interface for Ollama/Qwen3 (port 3080) |
| `open-webui-data.volume` | Open WebUI | Persistent Open WebUI data |

## Usage

All quadlets are **disabled by default** (`[Install]` is commented out).
Install the quadlet files, then explicitly start the services you need:

```bash
just quadlet-install   # Install quadlet files to systemd
```

To enable auto-start on login, uncomment `[Install]` / `WantedBy=default.target`
in each `.container` file, then run `systemctl --user daemon-reload`.

Quadlets are systemd-native: Podman generates `.service` units from the
`.container` definitions. Auto-update is enabled via
`io.containers.autoupdate=registry`.

### Plane

Plane is wired as a user-level Quadlet stack that shares
`exousia.network` with Forgejo and the registry. That keeps service discovery
simple for the whole Exousia project:

- browser-facing Forgejo URL: `http://localhost:3000`
- browser-facing Plane URL: `http://localhost:8080`
- in-network Forgejo URL for Plane integrations: `http://forgejo:3000`

Bootstrap the Plane environment file, then start the stack:

```bash
just plane-install
just plane-start
```

The startup sequence follows Plane's Podman Quadlet guidance: shared network,
core dependencies, backend services, then frontend services.

### Temporal

Temporal provides durable workflow orchestration for coordinating LLM agents
(Claude, Gemini, Codex, Qwen3). It shares `exousia.network` with all other
services:

- browser-facing Temporal UI: `http://localhost:8233`
- gRPC endpoint (for workers): `localhost:7233`
- in-network gRPC endpoint: `temporal:7233`

```bash
just temporal-start
just temporal-stop
just temporal-status
```

See [Temporal Orchestration Plan](../../docs/plan-temporal-orchestration.md) for
the full architecture and workflow design.

### Open WebUI

Open WebUI provides a browser-based chat interface for Ollama. It requires
Ollama to be running (declared via `Requires=ollama.service`):

- browser-facing URL: `http://localhost:3080`
- in-network URL: `http://open-webui:8080`
- connects to Ollama via `http://ollama:11434` on `exousia.network`

```bash
just engage open-webui
just disengage open-webui
```

## See Also

- [Local Build Pipeline](../../docs/local-build-pipeline.md) -- Full setup guide
