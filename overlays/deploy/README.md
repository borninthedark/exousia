# Deploy Overlay

Podman Quadlet container definitions for local infrastructure services.

## Quadlets

| File | Service | Purpose |
|------|---------|---------|
| `forgejo.container` | Forgejo | Local Git forge for development |
| `forgejo-runner.container` | Forgejo Runner | Executes Forgejo Actions workflows |
| `exousia-registry.container` | Container Registry | Local OCI registry at `localhost:5000` |
| `plane-*.container` | Plane | Local project planning stack on the shared `exousia.network` |
| `plane-*.volume` | Plane | Persistent Plane data volumes for Postgres, Valkey, RabbitMQ, and MinIO |
| `plane.env.example` | Plane | Example environment file for the Quadlet-managed Plane stack |

## Usage

```bash
make quadlet-install   # Install quadlet files to systemd
make quadlet-start     # Start all services
```

### Plane

Plane is wired as a second user-level Quadlet stack that shares
`exousia.network` with Forgejo and the registry. That keeps service discovery
simple for the whole Exousia project:

- browser-facing Forgejo URL: `http://localhost:3000`
- browser-facing Plane URL: `http://localhost:8080`
- in-network Forgejo URL for Plane integrations: `http://forgejo:3000`

Bootstrap the Plane environment file, then install and start the stack:

```bash
make plane-env-init
make quadlet-install
make plane-quadlet-start
```

The startup sequence follows Plane's Podman Quadlet guidance: shared network,
core dependencies, backend services, then frontend services.

Quadlets are systemd-native: Podman generates `.service` units from the
`.container` definitions. Auto-update is enabled via
`io.containers.autoupdate=registry`.

## See Also

- [Local Build Pipeline](../../docs/local-build-pipeline.md) -- Full setup guide
