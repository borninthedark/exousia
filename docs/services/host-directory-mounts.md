# Host Directory Mounts

Services that mount host directories for media ingestion and library access.

## Mount Summary

| Service | Host Path | Container Path | Mode | Purpose |
|---------|-----------|----------------|------|---------|
| Navidrome | `~/Music` | `/music` | read-only | Music library |
| Immich | `~/Pictures` | `/usr/src/app/external/pictures` | read-only | External photo library |
| Paperless | `~/Documents` | `/usr/src/paperless/consume` | read-write | Document consumption |

## SELinux

All host bind mounts use the `:z` volume flag to apply shared SELinux
relabeling. Without this flag, SELinux enforcing mode blocks container
access to `user_home_t` labeled files.

```ini
Volume=%h/Pictures:/usr/src/app/external/pictures:ro,z
```

The `:z` flag tells podman to relabel the host directory with
`container_file_t` so the container process can read it. Use lowercase
`:z` (shared) rather than `:Z` (private) since multiple containers or
the host user may access these directories.

## UID Mapping

Each service handles UID mapping differently due to rootless podman's
user namespace remapping:

| Service | Internal User | UID | Mapping Strategy |
|---------|--------------|-----|------------------|
| Navidrome | `uryu` | 1000 | `UserNS=keep-id` — host UID maps directly to container UID 1000 |
| Immich | `node` | 1000 | `UserNS=keep-id` — host UID maps directly to container UID 1000 |
| Paperless | `paperless` | 1000 | `USERMAP_UID=1000` / `USERMAP_GID=1000` — init runs as root, then drops to UID 1000 |

Paperless cannot use `UserNS=keep-id` because its s6 init system
requires root to chown directories and run migrations before dropping
privileges to the `paperless` user.

## Service-Specific Notes

### Immich — External Library

After mounting `~/Pictures`, configure the external library in Immich:

1. Go to **Administration > External Libraries > Create Library**
2. Set import path to `/usr/src/app/external/pictures`
3. Click **Scan** to index existing photos

Immich treats external libraries as read-only references — originals
stay on disk, thumbnails and metadata are stored in the upload volume.

### Paperless — Consume Directory

Paperless automatically watches `/usr/src/paperless/consume` for new
files. Any document placed in `~/Documents` will be ingested on the
next consumption cycle (default: every ~10 minutes).

The mount is read-write because Paperless's init script requires
ownership of the consume directory. By default, Paperless deletes
files from the consume directory after ingestion. To preserve
originals in `~/Documents`, set `PAPERLESS_CONSUMER_DELETE_DUPLICATES=false`
and `PAPERLESS_CONSUMER_ENABLE_BARCODES=false` in the quadlet, or
configure consumption behavior via the web UI.

All documents consumed from `~/Documents` are automatically tagged
with `local-import` via `PAPERLESS_CONSUMER_TAGS=local-import`.

### Navidrome — Music Library

Navidrome scans `/music` on a configurable schedule (`ND_SCANSCHEDULE=1h`).
Drop music files into `~/Music/` and they will appear in the library
within an hour, or trigger a manual scan from **Settings > Scan Library**.
