# Supported Distributions

Exousia now supports building bootc images for multiple Linux distributions beyond Fedora, including all bootcrew distros!

## Fedora Atomic Variants

All Fedora Atomic desktop variants are supported with version-pinned base images:

### Officially Supported Fedora Atomic Desktops

| Image Type | Desktop Environment | Base Image |
|------------|---------------------|------------|
| `fedora-bootc` | None (minimal) | `quay.io/fedora/fedora-bootc` |
| `fedora-silverblue` | GNOME | `quay.io/fedora/fedora-silverblue` |
| `fedora-kinoite` | KDE Plasma | `quay.io/fedora/fedora-kinoite` |
| `fedora-sway-atomic` | Sway (Wayland) | `quay.io/fedora/fedora-sway-atomic` |

### Community Fedora Atomic Desktops

| Image Type | Desktop Environment | Base Image |
|------------|---------------------|------------|
| `fedora-onyx` | Budgie | `quay.io/fedora-ostree-desktops/onyx` |
| `fedora-budgie` | Budgie | `quay.io/fedora-ostree-desktops/budgie` |
| `fedora-cinnamon` | Cinnamon | `quay.io/fedora-ostree-desktops/cinnamon` |
| `fedora-cosmic` | COSMIC | `quay.io/fedora-ostree-desktops/cosmic` |
| `fedora-deepin` | Deepin | `quay.io/fedora-ostree-desktops/deepin` |
| `fedora-lxqt` | LXQt | `quay.io/fedora-ostree-desktops/lxqt` |
| `fedora-mate` | MATE | `quay.io/fedora-ostree-desktops/mate` |
| `fedora-xfce` | Xfce | `quay.io/fedora-ostree-desktops/xfce` |

## Bootcrew Distros

Based on the [bootcrew organization](https://github.com/orgs/bootcrew/repositories), these distros build bootc from source with composefs support:

| Image Type | Distribution | Base Image | Package Manager |
|------------|--------------|------------|-----------------|
| `arch` | Arch Linux | `docker.io/archlinux/archlinux:latest` | pacman |
| `gentoo` | Gentoo | `ghcr.io/gentoo/stage3:systemd` | portage/emerge |
| `debian` | Debian (unstable) | `debian:unstable` | apt/dpkg |
| `ubuntu` | Ubuntu (Mantic) | `ubuntu:mantic` | apt/dpkg |
| `opensuse` | openSUSE Tumbleweed | `registry.opensuse.org/opensuse/tumbleweed:latest` | zypper/rpm |
| `proxmox` | Proxmox (Debian-based) | `debian:unstable` | apt/dpkg |

## Building Images

### Using Workflow Dispatch (GitHub Actions)

1. Go to **Actions** → **Bootc DevSecOps Pipeline**
2. Click **Run workflow**
3. Select your desired **image type** (e.g., `arch`, `fedora-kinoite`, etc.)
4. Select distro version (for Fedora) or leave as `current` (for bootcrew)
5. Click **Run workflow**

The built images are automatically tagged with:
- OS family and version (e.g., `arch-latest`, `fedora-43`)
- Image type (e.g., `fedora-kinoite`, `debian`)
- Git commit SHA
- Branch name

### Using YAML Configs Locally

Each distro has a pre-configured YAML file in `yaml-definitions/`:

```bash
# Build Arch bootc image
python3 tools/yaml-to-containerfile.py \
  --config yaml-definitions/arch-bootc.yml \
  --image-type arch \
  --output Containerfile.arch

buildah build -f Containerfile.arch -t localhost/arch-bootc:latest .
```

```bash
# Build Fedora Kinoite with custom packages
python3 tools/yaml-to-containerfile.py \
  --config yaml-definitions/fedora-kinoite.yml \
  --image-type fedora-kinoite \
  --fedora-version 43 \
  --output Containerfile.kinoite

buildah build -f Containerfile.kinoite -t localhost/fedora-kinoite:43 .
```

## Image Tags

Built images are tagged with the following patterns:

- **OS-Version**: `{os-family}-{version}` (e.g., `fedora-43`, `arch-latest`, `debian-unstable`)
- **Image Type**: `{image-type}` (e.g., `fedora-kinoite`, `arch`, `ubuntu`)
- **Main**: `main` (for main branch builds)
- **SHA**: `sha-{git-commit-sha}`
- **Branch**: `{branch-name}` (for branch builds)
- **Nightly**: `nightly` (for scheduled builds)

### Examples

**Docker Hub (Primary - Public Access):**
```bash
# Fedora Kinoite 43
docker.io/<username>/exousia:fedora-43
docker.io/<username>/exousia:fedora-kinoite

# Arch Linux bootc
docker.io/<username>/exousia:arch-latest
docker.io/<username>/exousia:arch

# Ubuntu bootc
docker.io/<username>/exousia:ubuntu-mantic
docker.io/<username>/exousia:ubuntu
```

**GHCR (Secondary - Pipeline/CI Use Only):**
```bash
# GHCR images are built for CI/CD pipeline use only
# Cannot be used with `bootc switch` for deployment
# For deployment, use Docker Hub images above
ghcr.io/<org>/exousia:fedora-kinoite
```

## Creating Custom Configs

Create a new YAML file for your custom image:

```yaml
# my-custom-arch.yml
name: my-custom-arch
description: Custom Arch Linux bootc image
image-type: arch
base-image: docker.io/archlinux/archlinux:latest

labels:
  org.opencontainers.image.title: "My Custom Arch"
  org.opencontainers.image.description: "Custom Arch Linux bootc"

modules:
  # Build bootc and configure bootcrew-style filesystem
  - type: bootcrew-setup
    system-deps:
      - base
      - linux
      - linux-firmware
      - ostree
      - dracut
      - btrfs-progs

  # Add custom packages (Arch-specific)
  - type: script
    scripts:
      - pacman -S --noconfirm neovim htop docker

  # Validation
  - type: script
    scripts:
      - bootc container lint
```

Then build it:

```bash
python3 tools/yaml-to-containerfile.py \
  --config my-custom-arch.yml \
  --image-type arch \
  --output Containerfile.custom

buildah build -f Containerfile.custom -t my-arch:latest .
```

## Module Reference

### `bootcrew-setup` Module

Automatically builds bootc from source and configures the filesystem for bootcrew distros:

```yaml
- type: bootcrew-setup
  system-deps:
    - base  # Base system packages
    - linux  # Kernel
    - ostree  # OSTree
    - dracut  # Initramfs builder
    - btrfs-progs  # Filesystem tools
```

This module:
1. Installs system dependencies using the distro's package manager
2. Builds bootc from source (clones from GitHub)
3. Generates dracut initramfs with composefs support
4. Restructures filesystem for ostree/bootc (symlinks /home → /var/home, etc.)
5. Configures composefs and readonly sysroot
6. Adds the `containers.bootc 1` label

### `rpm-ostree` Module (Fedora only)

Manages packages on Fedora-based images:

```yaml
- type: rpm-ostree
  repos:
    - https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-43.noarch.rpm
  install:
    - neovim
    - htop
  remove:
    - firefox-langpacks
```

### `script` Module (All distros)

Runs arbitrary shell commands:

```yaml
- type: script
  scripts:
    - echo "Hello from ${BUILD_IMAGE_TYPE}"
    - bootc container lint
```

### `files` Module (All distros)

Copies files into the image:

```yaml
- type: files
  files:
    - src: custom-configs/
      dst: /etc/
      mode: "0644"
```

## Testing

The test suite automatically adapts to different distros:

```bash
# Run tests (Bats)
TEST_IMAGE_TAG="localhost/arch-bootc:latest" \
  buildah unshare -- bats -r custom-tests

# Run Python tests
python3 tools/test_yaml_to_containerfile.py
```

Tests will automatically skip non-applicable checks (e.g., RPM tests on Debian-based images).

## Deployment

Deploy any built image using bootc with Docker Hub:

```bash
# Arch Linux bootc
sudo bootc switch docker.io/<username>/exousia:arch-latest
sudo bootc upgrade && sudo systemctl reboot

# Fedora Kinoite
sudo bootc switch docker.io/<username>/exousia:fedora-kinoite
sudo bootc upgrade && sudo systemctl reboot

# Ubuntu bootc
sudo bootc switch docker.io/<username>/exousia:ubuntu-mantic
sudo bootc upgrade && sudo systemctl reboot
```

**Important Notes:**
- **Docker Hub Only**: The `bootc switch` command only works with Docker Hub images
- **GHCR Not Supported**: GHCR images cannot be used for bootc deployment (CI/CD use only)
- Replace `<username>` with your Docker Hub username

## Contributing

To add support for a new distro:

1. Add distro config to `BOOTCREW_DISTROS` in `tools/yaml-to-containerfile.py`
2. Create YAML template in `yaml-definitions/{distro}-bootc.yml`
3. Add distro to workflow dispatch options in `.github/workflows/build.yml`
4. Update tests to handle distro-specific behaviors
5. Test the build pipeline

See existing bootcrew distros for examples!
