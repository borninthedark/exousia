# Exousia: Declarative Bootc Builder

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/build.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/borninthedark/exousia/actions/workflows/build.yml)
[![Last Build: Fedora 43 • Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%E2%80%A2%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/borninthedark/exousia/actions/workflows/build.yml?query=branch%3Amain+is%3Asuccess)
[![Code Quality](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/build.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=Code%20Quality)](https://github.com/borninthedark/exousia/actions/workflows/build.yml)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)
<img src=".github/quincy-pentacle.svg" alt="Custom Quincy Pentacle" width="28" />

This repository contains the configuration to build a custom, container-based immutable operating system using the upstream [**bootc project**](https://github.com/bootc-dev/bootc). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions. Fedora's [bootc documentation](https://docs.fedoraproject.org/en-US/bootc/) remains an authoritative, distro-specific reference alongside the upstream project docs.

**Note on Theming:** The "Reiatsu" (霊圧, spiritual pressure) build status badge and Quincy pentacle imagery are inspired by *BLEACH*, the manga and anime series created by **Tite Kubo**. These thematic elements are used purely as playful project aesthetics and status indicators, with full credit and acknowledgment to the original creator.

## Highly Experimental Disclaimer

⚠️ This project is highly experimental. There are **no guarantees** about stability, data safety, or fitness for any purpose. Running these builds or scripts can leave your system in a non-working state, require recovery steps, or force a full reinstall. Proceed only if you understand the risks and are comfortable rebuilding your environment from scratch.

## Philosophy: Exousia

Exousia (ἐξουσία) is Greek for "authority" and "power."

This is a personal project for building my own DevSecOps-hardened laptop OS using the bootc project. Still under development, but the goal is full control and transparency over packages, settings, and behaviors.

The build pipeline supports both bootc and atomic base images, each with their own defaults and configurations. Automated tests help ensure things actually work as development progresses.

## CI/CD Workflow: Fedora Bootc DevSec CI

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire image lifecycle. The workflow is triggered on:
- Pushes and pull requests to the `main` branch
- Nightly schedule (`20 4 * * *` UTC)
- Manual workflow dispatch with version/image type selection
- Webhook-triggered `repository_dispatch` events of type `api`

### 1. Build Stage

The first stage assembles the container image and prepares it for subsequent stages.

- **Lint**: Generated container definitions are linted using **Hadolint** to ensure best practices
- **Tagging**: Image tags are dynamically generated based on event triggers (`latest`, `nightly`, branch name, commit SHA)
- **Build**: The image is built using **Buildah**, a daemonless container image builder optimized for CI environments
- **Version Switching**: Supports dynamic Fedora version and base image type switching via workflow dispatch

### 2. Test Stage

After a successful build, the image and repository scripts undergo automated testing.

- **Integration Tests**: **Bats (Bash Automated Testing System)** runs tests against the built container
- **Script Analysis**: All shell scripts are linted with **ShellCheck**
- **Bootc Validation**: Runs `bootc container lint` to verify bootc compliance

### 3. Scan Stage

Security scanning ensures the image meets security standards.

- **Vulnerability Scan**: **Trivy** scans for `CRITICAL` and `HIGH` severity CVEs
- **Static Analysis**: **Semgrep** performs static code analysis

### 4. Push & Sign Stage

If tests pass and the event is not a pull request, the image is published and cryptographically signed.

- **Push**: Image pushed to **GitHub Container Registry (GHCR)** and **Docker Hub**
- **Sign**: Images signed using **Cosign** and **Sigstore** for integrity verification

---

## Triggering Builds Remotely

You can trigger builds programmatically using the webhook API. This is useful for automation, CI/CD integration, or testing different configurations.

### Quick Start

**Prerequisites:**
- GitHub Personal Access Token with `repo` scope ([Create one here](https://github.com/settings/tokens))
- Python 3.7+ with `requests` library: `pip install requests`

**Basic Usage:**

 > Default behavior: When you omit `--yaml`, `--os`, `--de`, and `--wm`, the dispatcher auto-loads the repository's `adnyeus.yml` blueprint.

```bash
# Set your GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# Trigger a build using repo defaults (auto-falls back to adnyeus.yml)
python api/webhook_trigger.py

# Trigger specific image type and version
python api/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43 \
  --enable-plymouth
```

**Using YAML Definitions and Desktop Environments:**

```bash
# Use a YAML definition file (auto-prepends yaml-definitions/)
python api/webhook_trigger.py \
  --yaml sway-bootc.yml \
  --distro-version 44

# Use custom path (any directory)
python api/webhook_trigger.py \
  --yaml custom/my-config.yml \
  --distro-version 44

# Use a local YAML file (will be validated and sent securely)
python api/webhook_trigger.py \
  --yaml /path/to/my-custom-config.yml \
  --image-type fedora-sway-atomic \
  --distro-version 43

# Build with specific window manager (auto-selects YAML)
python api/webhook_trigger.py \
  --wm sway \
  --distro-version 43

# Build with specific desktop environment (auto-selects YAML)
python api/webhook_trigger.py \
  --de kde \
  --distro-version 44

# Build with combined DE+WM (e.g., LXQt with Sway)
python api/webhook_trigger.py \
  --de lxqt \
  --wm sway \
  --distro-version 43

# Build with OS specification for auto-selection
python api/webhook_trigger.py \
  --os fedora \
  --image-type fedora-bootc \
  --de lxqt \
  --distro-version 43

# Build with custom configuration and disable Plymouth
python api/webhook_trigger.py \
  --yaml sway-atomic.yml \
  --disable-plymouth \
  --verbose
```

**Direct API Usage (cURL):**

> Default behavior: If you omit `yaml_config`, `yaml_content`, `os`, `desktop_environment`, and `window_manager`, the dispatcher falls back to the repository `adnyeus.yml` blueprint.

```bash
# Trigger build with auto-selected YAML (defaults to adnyeus.yml when no selectors are provided)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "44",
      "enable_plymouth": true
    }
  }'

# Trigger build with specific YAML definition (just the filename - searches yaml-definitions/ and repo)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "44",
      "enable_plymouth": true,
      "yaml_config": "sway-bootc.yml"
    }
  }'

# Trigger build with specific window manager (auto-selects YAML)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "43",
      "enable_plymouth": true,
      "window_manager": "sway"
    }
  }'

# Trigger build with specific desktop environment (auto-selects YAML)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "44",
      "enable_plymouth": true,
      "desktop_environment": "kde"
    }
  }'

# Trigger build with combined DE+WM (e.g., LXQt with Sway)
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "image_type": "fedora-bootc",
      "distro_version": "43",
      "enable_plymouth": true,
      "desktop_environment": "lxqt",
      "window_manager": "sway"
    }
  }'

# Trigger build with OS specification for auto-selection
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{
    "event_type": "api",
    "client_payload": {
      "os": "fedora",
      "image_type": "fedora-bootc",
      "distro_version": "43",
      "enable_plymouth": true,
      "desktop_environment": "lxqt"
    }
  }'
```

View your triggered builds at: **https://github.com/borninthedark/exousia/actions**

📚 **Complete documentation:** [Webhook API Guide](docs/WEBHOOK_API.md)

---

## Getting Started

### Prerequisites

- A system running Fedora (preferably an Atomic variant)
- Access to either Docker Hub or GHCR
- Basic understanding of bootc and container workflows

### Using the Pre-built Image

#### From Docker Hub (Recommended)

```bash
# Switch to the custom bootc image
sudo bootc switch docker.io/borninthedark/exousia:latest

# Apply the update
sudo bootc upgrade
sudo systemctl reboot
```

#### From GitHub Container Registry

```bash
# Switch to the custom bootc image
sudo bootc switch ghcr.io/borninthedark/exousia:latest

# Apply the update
sudo bootc upgrade
sudo systemctl reboot
```

### Building Locally

```bash
# Clone the repository
git clone https://github.com/borninthedark/exousia.git
cd $(basename borninthedark/exousia)

# Build the image
make build

# Push to local registry (optional)
make push
```

---

## RKE2 Kubernetes Integration

**Immutable Kubernetes infrastructure built into every bootc image.**

### Overview

All Exousia bootc images include RKE2 (Rancher Kubernetes Engine 2) by default, providing:

- **Immutable Infrastructure**: Entire k8s stack as a container image
- **Atomic Updates**: Upgrade cluster with `bootc upgrade`
- **Instant Rollback**: Boot previous version with `bootc rollback`
- **Desktop & Server**: Works on laptops and production servers

### Quick Start

After building and booting an Exousia image:

```bash
# Check RKE2 status
sudo systemctl status rke2-server

# Access cluster
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml
kubectl get nodes
```

### Configuration

Enable/disable RKE2 in `adnyeus.yml`:

```yaml
build:
  enable_plymouth: true
  enable_rke2: true  # Enabled by default
```

### Use Cases

- **Local Development**: Full k8s cluster on your laptop
- **Immutable Infrastructure**: Production-grade atomic deployments
- **Edge Computing**: Kubernetes at the edge with rollback

### Documentation

- **[RKE2 Integration Guide](docs/RKE2_INTEGRATION.md)** - Complete documentation
- **[rke2_ops Tool](tools/rke2_ops.py)** - Unified management CLI

For VM-based testing and deployment:

```bash
# Quick start - all in one command
make rke2-quickstart

# Or step by step
python3 tools/rke2_ops.py registry start
python3 tools/rke2_ops.py vm build
python3 tools/rke2_ops.py vm create
python3 tools/rke2_ops.py vm start
python3 tools/rke2_ops.py kubeconfig
```

---

## Customization

### Switching Fedora Versions and Image Types

**Recommended: Use the Webhook API** for programmatic version and image type switching:

```bash
# Switch to Fedora 44 with bootc base
python api/webhook_trigger.py \
  --image-type fedora-bootc \
  --distro-version 44

# Switch to Fedora 43 Sway Atomic
python api/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43

# Use custom YAML configuration
python api/webhook_trigger.py \
  --yaml-config yaml-definitions/fedora-bootc.yml \
  --distro-version 44
```

**Alternative: GitHub Actions UI:**

1. Go to **Actions** → **Fedora Bootc DevSec CI**
2. Click **Run workflow**
3. Select desired Fedora version and image type
4. Click **Run workflow**

The README will automatically update to reflect the new configuration.

### Modifying Packages

Edit the package lists in `custom-pkgs/`:

- `packages.add` - Packages to install
- `packages.remove` - Packages to remove from base image

#### Fedora Hyprland COPR setup

If you are building the Hyprland profile on Fedora, add the COPR repositories before validating or building packages:

1. Enable the Hyprland COPR maintained by **lionheartp**:
   ```bash
   sudo dnf copr enable lionheartp/Hyprland
   sudo dnf update --refresh
   ```
2. Add the supporting COPRs called out in the package definition when you need optional components:
   - `erikreider/SwayNotificationCenter` for SwayNC
   - `tofik/nwg-shell` if you plan to install `nwg-displays`
3. Be aware of package availability constraints:
   - `wallust` is provided by the Hyprland COPR; without the repo it will be reported missing during validation.
   - `nwg-displays` requires the `nwg-shell` COPR and may not exist in the base Fedora repos.

These repos match the expectations defined in `packages/window-managers/hyprland.yml` and prevent false negatives during validation.

### Adding Custom Configuration

Place configuration files in the appropriate `custom-configs/` subdirectories:

- `custom-configs/sway/` - Sway window manager configuration
- `custom-configs/greetd/` - Display manager configuration
- `custom-configs/plymouth/` - Boot splash configuration

### Plymouth Boot Splash Configuration

The Plymouth boot splash configuration is toggleable on both base image types via the `enable_plymouth` flag:

| Base Image Type | Plymouth Support | Details |
|-----------------|------------------|---------|
| `fedora-bootc` | ✅ Custom themes supported | Uses `custom-configs/plymouth/themes/bgrt-better-luks/` and bootc kargs when enabled |
| `fedora-sway-atomic` | ✅ Custom themes supported | Uses `custom-configs/plymouth/themes/bgrt-better-luks/` when enabled |

**To use custom Plymouth themes:**

1. Set `enable_plymouth: true` in your BlueBuild YAML (default in provided configs).
2. Place your theme in `custom-configs/plymouth/themes/bgrt-better-luks/`.
3. Build either `fedora-bootc` or `fedora-sway-atomic` variants to apply the theme.

### Greetd Display Manager

**⚠️ IMPORTANT: The greetd display manager is only available for `fedora-bootc` base images.**

The greetd display manager availability depends on your base image type:

| Base Image Type | Greetd Support | Details |
|-----------------|----------------|---------|
| `fedora-bootc` | ✅ Available | greetd.service enabled, custom config in `custom-configs/greetd/` |
| `fedora-sway-atomic` | ❌ Not available | Uses SDDM display manager instead |

**Note:** The `fedora-sway-atomic` image uses SDDM (Simple Desktop Display Manager) by default. Switch to `fedora-bootc` if you need greetd.

**To use greetd display manager:**

1. Use the webhook API or workflow dispatch to build with the fedora-bootc image type

2. Customize the greetd configuration in `custom-configs/greetd/config.toml` as needed

### Custom Scripts

Add executable scripts to `custom-scripts/` - they will be copied to `/usr/local/bin/`

---

## RKE2 on Bootc: Immutable Kubernetes

Build Kubernetes clusters with atomic updates using RKE2 on Fedora bootc.

### Overview

Exousia now supports building RKE2 (Rancher Kubernetes) on Fedora bootc, giving you:

- **Immutable Infrastructure**: Entire k8s node as a container image
- **Atomic Updates**: Upgrade cluster with `bootc upgrade`
- **Instant Rollback**: Boot into previous version on failures
- **Clean Separation**: Kubernetes isolated from your host system

### Architecture

```
┌──────────────────────────────────────────┐
│           Host (Gentoo/Fedora)           │
│                                          │
│  ┌──────────┐      ┌────────────────┐   │
│  │ Registry │◄─────┤ libvirt/KVM    │   │
│  │ :5000    │      │  ┌──────────┐  │   │
│  └──────────┘      │  │ Fedora   │  │   │
│                    │  │ bootc    │  │   │
│  ┌──────────┐      │  │          │  │   │
│  │Kubeconfig│◄─────┼──┤ + RKE2   │  │   │
│  │(9p share)│      │  └──────────┘  │   │
│  └──────────┘      └────────────────┘   │
└──────────────────────────────────────────┘
```

### Quick Start

```bash
# One command to rule them all
make rke2-quickstart

# Use your cluster
export KUBECONFIG=~/.kube/rke2-config
kubectl get nodes
```

**Manual steps:**

```bash
# 1. Start local registry
make rke2-registry-start

# 2. Build and push bootc image
make rke2-build
make rke2-push

# 3. Build VM disk image
make rke2-vm-build

# 4. Create and start VM
make rke2-vm-create
make rke2-vm-start

# 5. Get kubeconfig (wait ~2 min)
make rke2-kubeconfig
```

### Operations

**Upgrade cluster:**

```bash
# Build new image
make rke2-build
podman tag exousia-rke2:latest localhost:5000/exousia-rke2:v2
podman push localhost:5000/exousia-rke2:v2

# Upgrade (inside VM)
sudo bootc switch localhost:5000/exousia-rke2:v2
sudo bootc upgrade
sudo systemctl reboot
```

**Rollback:**

```bash
# Automatic on boot failure, or manual:
sudo bootc rollback
sudo systemctl reboot
```

### Documentation

- **[Quick Start Guide](k8s/rke2/QUICKSTART.md)** - Get started in 30 seconds
- **[Complete Setup Guide](docs/RKE2_BOOTC_SETUP.md)** - Full documentation and troubleshooting
- **[Configuration Templates](k8s/rke2/)** - Cloud-init, libvirt XML, RKE2 configs

### Benefits

- **Reproducible**: Version entire k8s stack as container images
- **Testable**: Promote images through dev → staging → prod
- **Resilient**: Instant rollback on failures
- **Efficient**: Registry on host, shared across VMs
- **Flexible**: Works on Gentoo, Fedora, or any libvirt-capable host

---

## Package validation and dependency tooling

### Package dependency transpiler CLI

Use `tools/package_dependency_checker.py` to translate package dependencies across distros and confirm they are installed locally. The tool auto-selects the native package manager (dnf, pacman, apt, zypper, emerge, pkg) and standardizes the output for cross-distro comparisons.

Common invocation patterns:

- Fedora (dnf repoquery):
  ```bash
  python3 tools/package_dependency_checker.py --packages python3-requests neovim
  ```
- Arch Linux (pacman):
  ```bash
  python3 tools/package_dependency_checker.py --distro arch --packages python-requests hyprland
  ```
- Debian/Ubuntu (apt):
  ```bash
  python3 tools/package_dependency_checker.py --distro debian --packages python3-requests sway
  ```
  ```bash
  python3 tools/package_dependency_checker.py --distro ubuntu --packages python3-requests plymouth
  ```
- OpenSUSE (zypper):
  ```bash
  python3 tools/package_dependency_checker.py --distro opensuse --packages python3-requests waybar
  ```
- Gentoo (emerge):
  ```bash
  python3 tools/package_dependency_checker.py --distro gentoo --packages dev-python/requests greetd
  ```
- FreeBSD (pkg):
  ```bash
  python3 tools/package_dependency_checker.py --distro freebsd --packages py311-requests sway
  ```

Use `--verify-only` to quickly flag missing packages and `--json` for machine-readable output. The checker reports which dependencies were found, what each package provides, and whether anything is absent on the target system.

### Validation CLI image-type mapping

`tools/validate_installed_packages.py` supports `--image-type` to infer the distro when you only know the build target. The resolver auto-maps atomic image types (for example, `fedora-bootc`, `fedora-sway-atomic`, or `fedora-onyx`) to `fedora`, then falls back to distro detection when a mapping is unknown.

Usage examples:

- Map a bootc image type to Fedora automatically:
  ```bash
  python3 tools/validate_installed_packages.py --yaml adnyeus.yml --image-type fedora-bootc
  ```
- Override with a specific distro (skips auto-mapping):
  ```bash
  python3 tools/validate_installed_packages.py --wm hyprland --distro arch
  ```
- Combine mapping with verbose logging to see the resolved distro:
  ```bash
  python3 tools/validate_installed_packages.py --de kde --image-type fedora-sway-atomic --verbose
  ```

### Troubleshooting validation failures

- **Common naming differences:** Package names often vary by distro. If validation fails, cross-check whether the package uses `python3-` prefixes on Fedora/Debian-based images versus `python-` prefixes on Arch, or category names like `dev-python/` on Gentoo.
- **Missing repositories:** Errors mentioning missing packages frequently mean a required repository is not configured (for example, the Hyprland COPR for `wallust` or `nwg-shell` for `nwg-displays`). Add the repo and rerun validation.
- **Distro-specific gotchas:** Some packages are split differently (e.g., `plymouth-plugin-two-step` exists on Fedora but not on Arch). Use `--distro` or `--image-type` to align expectations with your target platform and adjust the package list accordingly.

### Package naming equivalents

Use these mappings when reconciling package lists between distros:

- Fedora/Debian: `python3-requests`
- Arch: `python-requests`
- Gentoo: `dev-python/requests`
- FreeBSD: `py311-requests`

Aligning names before validation reduces false positives when comparing configurations across platforms.

---

## Required Secrets

To use the full CI/CD pipeline, configure these secrets in your repository:

**Settings → Secrets and variables → Actions**

### For GitHub Container Registry (GHCR):
- `GHCR_PAT`: Personal Access Token with `write:packages` scope

### For Docker Hub:
- `DOCKERHUB_USERNAME`: Your Docker Hub username
- `DOCKERHUB_TOKEN`: Access token with Read, Write, Delete permissions

### For Code Coverage (Codecov):
- `CODECOV_TOKEN`: Repository upload token from [codecov.io](https://codecov.io)
  1. Sign up at https://codecov.io with your GitHub account
  2. Add your repository to Codecov
  3. Copy the repository upload token
  4. Add as `CODECOV_TOKEN` secret in GitHub Actions

**Benefits:**
- Detailed coverage reports with branch coverage tracking
- PR comments showing coverage changes
- Coverage trend visualization
- Integration with GitHub checks

---

## Known Issues

### GHCR Authentication

Currently experiencing authentication issues with `bootc switch` and `bootc upgrade` when using GHCR. The commands work flawlessly with Docker Hub. While `skopeo inspect` and `podman pull` work with GHCR, bootc operations return "403 Forbidden | Invalid Username/Password" errors.

**Workaround:** Use Docker Hub for bootc operations until this is resolved.

---

## Documentation

Comprehensive documentation organized by use case:

### Getting Started

New to Exousia? Start here:
- **[BOOTC_UPGRADE.md](docs/BOOTC_UPGRADE.md)** - Complete guide to using, upgrading, and switching bootc images
- **[BOOTC_IMAGE_BUILDER.md](docs/BOOTC_IMAGE_BUILDER.md)** - Build bootable disk images for local testing

### API Documentation

Use the REST API to manage configurations programmatically:
- **[API Overview](docs/api/README.md)** - FastAPI backend architecture and features
- **[API Endpoints](docs/api/endpoints.md)** - Complete endpoint reference with examples
- **[Development Guide](docs/api/development.md)** - Contributing to the API

The API enables:
- YAML configuration validation and storage
- Dynamic Containerfile transpilation
- GitHub Actions build triggering
- Build status tracking

### Building & Customization

Customize and build your own images:
- **[TESTING.md](docs/TESTING.md)** - Run the 52+ automated test suite before building

### Testing & Quality

For contributors and developers:
- **[Testing Guide](docs/testing/guide.md)** - In-depth testing architecture and best practices
- **[Testing README](docs/testing/README.md)** - Quick start for running tests
- **[Test Suite Details](docs/testing/test_suite.md)** - Detailed test documentation
- **[Writing Tests](docs/reference/writing-tests.md)** - Guide for contributing new tests

### Reference

Detailed guides and troubleshooting:
- **[Plymouth Usage](docs/reference/plymouth_usage_doc.md)** - Configure boot splash screens
- **[Troubleshooting](docs/reference/troubleshooting.md)** - Common issues and solutions

---

## External Resources

### Official Documentation
- [bootc Project](https://github.com/bootc-dev/bootc)
- [bootc Documentation](https://bootc-dev.github.io/bootc/)
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/) _(secondary Fedora-focused guidance)_
- [Base Images](https://docs.fedoraproject.org/en-US/bootc/base-images/)
- [Building Containers](https://docs.fedoraproject.org/en-US/bootc/building-containers/)

### Community Resources
- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)
- [bootc Issue Tracker](https://gitlab.com/fedora/bootc/tracker)
- [BlueBuild](https://blue-build.org/) - Declarative image builder for bootc
- [BlueBuild Module Reference](https://blue-build.org/reference/module/)

### Articles & Guides
- [Getting Started With Bootc](https://docs.fedoraproject.org/en-US/bootc/getting-started/)
- [How to rebase to Fedora Silverblue 43 Beta](https://fedoramagazine.org/how-to-rebase-to-fedora-silverblue-43-beta/)
- [A Great Journey Towards Fedora CoreOS and Bootc](https://fedoramagazine.org/a-great-journey-towards-fedora-coreos-and-bootc/)
- [Building Your Own Atomic Bootc Desktop](https://fedoramagazine.org/building-your-own-atomic-bootc-desktop/)

### Technical References
- [Bootupd RPM dependency workaround](https://github.com/coreos/bootupd/issues/468)
- [Unification of boot loader updates](https://gitlab.com/fedora/bootc/tracker/-/issues/61)
- [Add Plymouth to Fedora-Bootc](https://www.reddit.com/r/Fedora/comments/1nq636t/comment/ngbgfkh/)

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- The bootc project maintainers and the Fedora community
- [Universal Blue](https://universal-blue.org/) for pioneering container-native desktop workflows
- [BlueBuild](https://blue-build.org/) for the declarative YAML specification that inspired my build system
- [bootcrew](https://github.com/bootcrew) for community-driven bootc projects and examples
- [Buildah](https://buildah.io/), [Skopeo](https://github.com/containers/skopeo), and [Podman](https://podman.io/) communities
  for advancing daemonless container tooling
- The broader container and immutable OS community
- All contributors to the referenced documentation and guides
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### Creative Acknowledgments

- **Tite Kubo** - Creator of *BLEACH* (manga and anime series)
  - The "Reiatsu" (霊圧, spiritual pressure) status indicator and Quincy pentacle imagery in this project are inspired by themes from BLEACH
  - These elements are used respectfully as playful project aesthetics with full acknowledgment of the original creator
  - All rights to BLEACH and its associated concepts belong to Tite Kubo and respective copyright holders
  - This project is not affiliated with or endorsed by Tite Kubo, Shueisha, or Viz Media

### Development Notes

This project leverages AI-assisted development practices. The build pipeline, testing framework, and automation scripts were developed in collaboration with Claude and GPT Codex, demonstrating modern DevOps workflows enhanced by AI capabilities.

---

**Built with bootc**

*This README was automatically generated on 2025-12-04 15:16:24 UTC*
