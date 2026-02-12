# Deploy Overlay

Podman Quadlet container definitions for local infrastructure services.

## Quadlets

| File | Service | Purpose |
|------|---------|---------|
| `forgejo.container` | Forgejo | Local Git forge for the Espada CI pipeline |
| `forgejo-runner.container` | Forgejo Runner | Executes Forgejo Actions workflows |
| `exousia-registry.container` | Container Registry | Local OCI registry at `localhost:5000` |

## Usage

```bash
make quadlet-install   # Install quadlet files to systemd
make quadlet-start     # Start all services
```

Quadlets are systemd-native: Podman generates `.service` units from the
`.container` definitions. Auto-update is enabled via
`io.containers.autoupdate=registry`.

## See Also

- [Local Build Pipeline](../../docs/local-build-pipeline.md) -- Full setup guide
