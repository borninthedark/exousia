# Navidrome Music Server

Self-hosted music streaming server with Subsonic API support.

## Service Details

| Property | Value |
|----------|-------|
| Image | `docker.io/deluan/navidrome:latest` |
| Container | `navidrome` |
| Port | `4533` |
| URL | `https://sound.exousia.local` |
| Network | `exousia.network` |
| Music path | `/var/home/uryu/Music/Navidrome` (read-only mount, `:z` SELinux relabel) |
| Data volume | `navidrome-data` |
| Auto-update | Yes (`io.containers.autoupdate=registry`) |

## Quadlet Files

- `~/.config/containers/systemd/navidrome.container`
- `~/.config/containers/systemd/navidrome-data.volume`

## Configuration

Environment variables set in the quadlet:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ND_SCANSCHEDULE` | `1h` | Rescan music library every hour |
| `ND_LOGLEVEL` | `info` | Log verbosity |
| `ND_BASEURL` | `/` | Base URL path |

Additional configuration is done via the web UI after first login.

## Management

```bash
# Start/stop/restart
systemctl --user start navidrome
systemctl --user stop navidrome
systemctl --user restart navidrome

# Logs
journalctl --user -eu navidrome -f

# Force rescan of music library
# Use the web UI: Settings > Scan Library
```

## Container Signing Policy

`docker.io/deluan` is allowlisted in `/etc/containers/policy.json`.
The system default policy is `reject` — new image sources must be
explicitly added.

## Subsonic Clients

Navidrome implements the Subsonic API. Compatible clients:

- **Android**: Symfonium, DSub, Ultrasonic
- **iOS**: play:Sub, SubStreamer
- **Desktop**: Sublime Music, Sonixd
- **Web**: Built-in web UI at port 4533

## First Run

1. Navigate to `https://sound.exousia.local`
2. Create the admin user on the setup page
3. Drop music files into `~/Music/Navidrome/`
4. Library scans automatically every hour, or trigger manually from Settings
