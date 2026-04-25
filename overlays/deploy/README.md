# Deploy Overlay

Podman Quadlet container definitions for local infrastructure services.

## Quadlets

| File | Service | Purpose |
|------|---------|---------|
| `forgejo.container` | Forgejo | Local Git forge for development |
| `forgejo-runner.container` | Forgejo Runner | Executes Forgejo Actions workflows |
| `exousia-registry.container` | Container Registry | Local OCI registry at `localhost:5000` |
| `freebsd.container` | FreeBSD | FreeBSD 14.4 runtime environment on the shared `exousia.network` |
| `plane-*.container` | Plane | Local project planning stack on the shared `exousia.network` |
| `plane-*.volume` | Plane | Persistent Plane data volumes for Postgres, Valkey, RabbitMQ, and MinIO |
| `plane.env.example` | Plane | Example environment file for the Quadlet-managed Plane stack |

## Usage

All quadlets are **disabled by default** (`[Install]` is commented out).
Install the quadlet files, then explicitly start the services you need:

```bash
make quadlet-install   # Install quadlet files to systemd
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
make plane-env-init
make plane-quadlet-start
```

The startup sequence follows Plane's Podman Quadlet guidance: shared network,
core dependencies, backend services, then frontend services.

## See Also

- [Local Build Pipeline](../../docs/local-build-pipeline.md) -- Full setup guide
