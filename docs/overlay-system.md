# Overlay System

Overlays are the static files, configs, packages, and scripts that get COPY'd
into the container image at build time. The Python transpiler reads the YAML
blueprint and emits `COPY` directives that map overlay paths into the image
filesystem.

## Directory Structure

```text
overlays/
├── base/                               # Shared across all image types
│   ├── configs/
│   │   ├── pam.d/                      # PAM authentication (sudo, U2F)
│   │   ├── polkit-1/rules.d/          # Polkit authorization rules
│   │   └── tmpfiles.d/                # systemd-tmpfiles entries
│   ├── packages/
│   │   ├── common/
│   │   │   ├── base.yml               # Core packages (dnf install)
│   │   │   ├── flatpaks.yml           # Flatpak application list
│   │   │   ├── remove.yml             # Packages to remove (processed first)
│   │   │   └── zfs.yml                # ZFS packages (optional)
│   │   └── window-managers/
│   │       └── sway.yml               # Sway-specific packages
│   ├── sysusers/
│   │   ├── atomic.conf                # sysusers.d for atomic images
│   │   └── bootc.conf                 # sysusers.d for bootc images
│   └── tools/
│       ├── build-zfs-kmod             # ZFS DKMS build script (Python)
│       ├── generate-readme            # README generator (Python)
│       └── verify-flatpak-installation # Flatpak verification script
├── sway/                               # Sway desktop environment
│   ├── configs/
│   │   ├── greetd/config.toml         # Login manager configuration
│   │   ├── plymouth/themes/           # Boot splash themes
│   │   ├── sway/
│   │   │   ├── config                 # Main Sway config (sway-config-minimal)
│   │   │   └── config.d/             # Layered config overrides
│   │   └── swaylock/config            # Lock screen configuration
│   ├── repos/
│   │   └── nwg-shell.repo            # Additional package repository
│   ├── scripts/
│   │   ├── runtime/                   # Scripts installed to the image
│   │   │   ├── autotiling             # Automatic window tiling
│   │   │   ├── layered-include        # Config include helper
│   │   │   ├── lid                    # Laptop lid switch handler
│   │   │   └── volume-helper          # Volume control wrapper
│   │   └── setup/                     # Build-time setup scripts
│   │       ├── dracut-rebuild         # Initramfs regeneration
│   │       ├── ensure-sway-session    # Session file validation
│   │       └── setup-plymouth-theme   # Plymouth theme installer
│   └── session/
│       ├── environment                # Session environment variables
│       ├── start-sway                 # Session entry point
│       └── sway.desktop               # Desktop entry for greetd
└── deploy/                             # Local dev infrastructure (Quadlets)
    ├── exousia.network                # Shared Podman network
    ├── exousia-registry.container     # Local container registry
    ├── exousia-registry-data.volume   # Registry persistent storage
    ├── forgejo.container              # Self-hosted git forge
    ├── forgejo-data.volume            # Forgejo persistent storage
    ├── forgejo-runner.container       # Forgejo Actions runner
    └── forgejo-runner-data.volume     # Runner persistent storage
```

## How Overlays Map to the Image

The transpiler (`tools/yaml-to-containerfile.py`) reads the blueprint and
generates `COPY` directives. The general mapping:

| Overlay Path | Image Destination | Purpose |
|---|---|---|
| `base/configs/pam.d/` | `/etc/pam.d/` | PAM authentication modules |
| `base/configs/polkit-1/` | `/etc/polkit-1/` | Authorization policies |
| `base/configs/tmpfiles.d/` | `/etc/tmpfiles.d/` | Temp file rules |
| `base/sysusers/` | `/etc/sysusers.d/` | System user definitions |
| `base/tools/` | `/usr/local/bin/` | Build and utility scripts |
| `sway/configs/sway/` | `/etc/sway/` | Sway window manager config |
| `sway/configs/greetd/` | `/etc/greetd/` | Login manager config |
| `sway/configs/plymouth/` | `/usr/share/plymouth/` | Boot splash themes |
| `sway/configs/swaylock/` | `/etc/swaylock/` | Lock screen config |
| `sway/repos/` | `/etc/yum.repos.d/` | Package repositories |
| `sway/scripts/runtime/` | `/usr/local/bin/` | Runtime helper scripts |
| `sway/scripts/setup/` | (executed at build time) | Build-time setup |
| `sway/session/` | `/usr/share/wayland-sessions/` | Session files |

## Package System

Packages are declared in YAML files under `base/packages/`. The package loader
(`tools/package_loader.py`) reads these files and emits `dnf install` commands.

**Processing order:**

1. `common/remove.yml` -- packages removed first to avoid conflicts
2. `common/base.yml` -- core system packages
3. `window-managers/sway.yml` -- desktop-specific packages
4. `common/zfs.yml` -- ZFS packages (only if `build.enable_zfs: true`)
5. `common/flatpaks.yml` -- Flatpak applications (installed post-build)

See `overlays/base/packages/README.md` for the package list format.

## Base vs. Sway

- **base/** contains everything shared across image variants: authentication,
  system users, package lists, and utility scripts. If both `fedora-bootc` and
  `fedora-sway-atomic` need it, it goes here.
- **sway/** contains everything specific to the Sway desktop: window manager
  config, greetd, Plymouth themes, runtime scripts, and session definitions.

## Deploy (Quadlets)

The `deploy/` directory is **not** baked into the image. These are Podman
Quadlet files for local development infrastructure. See
[Local Build Pipeline](local-build-pipeline.md) for usage.

## Adding New Overlays

1. Place the file under the appropriate directory (`base/` or `sway/`)
2. Update the YAML blueprint (`adnyeus.yml`) to reference the new overlay path
3. The transpiler will generate the corresponding `COPY` directive
4. Run `just build-bootc` or `just build-atomic` to verify
5. Add Bats tests in `custom-tests/image_content.bats` to validate the file
   exists in the built image

---

**[Back to Documentation Index](README.md)** | **[Back to Main README](../README.md)**
