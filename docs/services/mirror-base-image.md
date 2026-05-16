# Base Image Mirror

Mirrors the upstream Fedora Sway Atomic base image from Quay.io to the
local container registry daily, ensuring hermetic builds use a local copy.

## Service Details

| Property | Value |
|----------|-------|
| Timer | `mirror-base-image.timer` |
| Service | `mirror-base-image.service` |
| Schedule | Daily at 07:30 local time |
| Source | `quay.io/fedora/fedora-sway-atomic:44` |
| Destination | `localhost:5000/fedora-sway-atomic:44` |
| Tool | `skopeo copy` |

## Unit Files

- `~/.config/systemd/user/mirror-base-image.timer`
- `~/.config/systemd/user/mirror-base-image.service`

## How It Works

The timer triggers a oneshot service that runs `skopeo copy` to pull
the latest `fedora-sway-atomic:44` image from Quay.io and push it to
the local registry at `localhost:5000`. The local registry does not
require TLS verification (`--dest-tls-verify=false`).

The Pernida pipeline's Gremmy (Build) job checks the local registry
first and falls back to Quay.io upstream if unavailable. When the
local mirror is present, the build pins by digest for hermetic builds.

## Scheduling

The timer runs at 07:30 daily with `Persistent=true`, so missed runs
(e.g. system was off) execute on next boot. The Pernida scheduled
build runs at 11:30 ET (15:30 UTC), giving the mirror 4 hours to
complete before the build triggers.

## Management

```bash
# Check timer status and next trigger
systemctl --user status mirror-base-image.timer

# Check last run result
systemctl --user status mirror-base-image.service

# View logs from last run
journalctl --user -eu mirror-base-image -n 20

# Trigger a manual mirror now
systemctl --user start mirror-base-image.service
```

## Updating the Fedora Version

When upgrading to a new Fedora release, update the `SRC` and `DST`
environment variables in `mirror-base-image.service` to reference the
new version tag (e.g. `44` to `45`).
