# Exousia: Declarative Bootc Builder

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/build.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/borninthedark/exousia/actions/workflows/build.yml)
[![Last Build: Fedora 43 • Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%E2%80%A2%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/borninthedark/exousia/actions/workflows/build.yml?query=branch%3Amain+is%3Asuccess)
[![Code Quality](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/build.yml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=Code%20Quality)](https://github.com/borninthedark/exousia/actions/workflows/build.yml)
[![Code Coverage](https://img.shields.io/codecov/c/github/borninthedark/exousia?style=for-the-badge&logo=codecov&logoColor=white&label=Coverage&token=G8NS9O5HZB)](https://codecov.io/gh/borninthedark/exousia)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)
<img src=".github/blue-sparrow.svg" alt="Blue Sparrow" width="28" />

Build custom, container-based immutable operating systems using the [**bootc project**](https://github.com/bootc-dev/bootc). Images are built, tested, scanned, and published via GitHub Actions.

**Note:** The "Reiatsu" badge is inspired by *BLEACH* by **Tite Kubo** — used as a playful status indicator with full acknowledgment.

Exousia builds custom, container-based immutable operating systems using [bootc](https://github.com/bootc-dev/bootc) and GitHub Actions. It focuses on reproducible, security-conscious laptop images with fast iteration cycles.

## Table of Contents

- [Highly Experimental Disclaimer](#highly-experimental-disclaimer)
- [Project Snapshot](#project-snapshot)
- [Build & Release Workflow](#build--release-workflow)
- [Getting Started](#getting-started)
- [Triggering Builds Remotely](#triggering-builds-remotely)
- [Customizing Builds](#customizing-builds)
- [YubiKey Authentication (PAM U2F)](#yubikey-authentication-pam-u2f)
- [Package Validation & Dependency Tooling](#package-validation--dependency-tooling)
- [Required Secrets](#required-secrets)
- [Documentation](#documentation)
- [External Resources](#external-resources)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Highly Experimental Disclaimer

> **Warning**: This project is highly experimental. There are **no guarantees** about stability, data safety, or fitness for any purpose. Proceed only if you understand the risks.

---

## Project Snapshot

- **Purpose:** Declarative laptop images with a DevSecOps-friendly workflow.
- **Outputs:** bootc base images and atomic desktops (e.g., Sway, KDE) published to GHCR and Docker Hub.
- **Tooling:** FastAPI webhook entrypoint, Python helpers in `tools/`, and YAML-based blueprints.
- **Security/Quality:** Linting, scanning, signing, and automated tests baked into CI.

---

## Build & Release Workflow

**Triggers:** pushes to `main`, pull requests, nightly schedule (`10 3 * * *` UTC), manual dispatch, and `repository_dispatch` events.

| Stage | What happens |
|-------|--------------|
| **Build** | Hadolint linting, dynamic tagging, Buildah image build |
| **Test** | Bats integration tests, ShellCheck, `bootc container lint` |
| **Scan** | Trivy vulnerability scan, Semgrep static analysis |
| **Push & Sign** | Push to GHCR/Docker Hub and sign with Cosign |

---

## Getting Started

### Prerequisites

- Fedora system (Atomic variant recommended)
- Access to Docker Hub or GHCR
- Basic familiarity with bootc/container workflows

### Use a Published Image

> **Flathub Setup**
>
> Exousia installs applications like Firefox and VS Code via Flatpak. To use Flathub apps, set up the remote before switching images:
>
> ```bash
> flatpak remote-add --if-not-exists --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo
> ```

```bash
# From Docker Hub (recommended)
sudo bootc switch docker.io/borninthedark/exousia:latest
sudo bootc upgrade && sudo systemctl reboot

# From GHCR
sudo bootc switch ghcr.io/borninthedark/exousia:latest
sudo bootc upgrade && sudo systemctl reboot
```

### Build Locally

```bash
git clone https://github.com/borninthedark/exousia.git
cd exousia
make build
```

---

## Triggering Builds Remotely

Trigger builds programmatically via the webhook API.

**Prerequisites:** GitHub PAT with `repo` scope, Python 3.7+ with `requests`

### Python CLI

```bash
# Set your GitHub token
export GITHUB_TOKEN="ghp_your_token_here"

# Trigger a build using repo defaults
python api/webhook_trigger.py

# Trigger specific image type and version
python api/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43 \
  --enable-plymouth

# Build with specific window manager
python api/webhook_trigger.py --wm sway --distro-version 43

# Build with specific desktop environment
python api/webhook_trigger.py --de kde --distro-version 44
```

<details>
<summary>More Python examples</summary>

```bash
# Use a YAML definition file
python api/webhook_trigger.py --yaml sway-bootc.yml --distro-version 44

# Build with combined DE+WM (e.g., LXQt with Sway)
python api/webhook_trigger.py --de lxqt --wm sway --distro-version 43

# Build with Debian
python api/webhook_trigger.py --os fedora --image-type fedora-lxqt --de lxqt --distro-version 44

# Disable Plymouth
python api/webhook_trigger.py --yaml sway-atomic.yml --disable-plymouth --verbose
```
</details>

### cURL API

```bash
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
```

<details>
<summary>More cURL examples</summary>

```bash
# With specific YAML definition
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{"event_type": "api", "client_payload": {"image_type": "fedora-bootc", "distro_version": "44", "yaml_config": "sway-bootc.yml"}}'

# With window manager
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{"event_type": "api", "client_payload": {"image_type": "fedora-bootc", "distro_version": "43", "window_manager": "sway"}}'

# With desktop environment
curl -X POST -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/borninthedark/exousia/dispatches \
  -d '{"event_type": "api", "client_payload": {"image_type": "fedora-bootc", "distro_version": "44", "desktop_environment": "kde"}}'
```
</details>

View builds: **https://github.com/borninthedark/exousia/actions** | 📚 [Webhook API Guide](docs/WEBHOOK_API.md)

---

## Customizing Builds

### Switch Blueprint Versions

```bash
# Via webhook API
python api/webhook_trigger.py --image-type fedora-bootc --distro-version 44
python api/webhook_trigger.py --image-type fedora-sway-atomic --distro-version 43
```

Or use **Actions → Fedora Bootc DevSec CI → Run workflow** in the GitHub UI.

### Adjust Packages

| Scope | Where to edit | What to change |
|-------|---------------|----------------|
| Base packages | `packages/common/*.yml` | Add/remove shared package sets |
| Window managers | `packages/window-managers/*.yml` | Add to the relevant categories |
| Desktop environments | `packages/desktop-environments/*.yml` | Add to the relevant categories |

All package additions are managed from the `packages/` directory via the package loader; avoid editing YAML definitions for package lists.

### Configuration Files

| Directory | Purpose |
|-----------|---------|
| `custom-configs/sway/` | Sway WM and config.d snippets |
| `custom-configs/waybar/` | Waybar status bar |
| `custom-configs/greetd/` | Display manager (bootc) |
| `custom-configs/plymouth/` | Boot splash themes |
| `custom-configs/rancher/rke2/` | RKE2 Kubernetes config |
| `custom-configs/pam.d/` | PAM authentication (YubiKey U2F) |
| `custom-scripts/` | Scripts copied to `/usr/local/bin/` |

### Desktop & Boot Experience

- **Sway** uses `sway-config-minimal` for headless/container compatibility.
  - `/usr/share/sway/config.d/*.conf` — Packaged configs
  - `/etc/sway/config.d/*.conf` — System overrides
  - `~/.config/sway/config.d/*.conf` — User overrides
  - See [Fedora Sericea Configuration Guide](https://docs.fedoraproject.org/en-US/fedora-sericea/configuration-guide/).
- **Plymouth**: Set `enable_plymouth: true` in YAML; themes live in `custom-configs/plymouth/themes/`.
- **Display managers**: all images use greetd; SDDM is deprecated.

---

## YubiKey Authentication (PAM U2F)

Exousia includes built-in support for YubiKey hardware authentication using PAM U2F. This allows you to use your YubiKey as a second factor or alternative authentication method for `sudo`, login, and other PAM-aware services.

### Configuration

The system includes pre-configured PAM modules in `custom-configs/pam.d/`:
- `u2f-required` — YubiKey authentication is mandatory
- `u2f-sufficient` — YubiKey OR password authentication (default for sudo)

By default, `sudo` is configured to accept YubiKey authentication as an alternative to password authentication. If your YubiKey is present and registered, you can use it instead of entering your password.

### Setup

After deploying an Exousia image, register your YubiKey(s):

```bash
# Create credential directory
mkdir -p ~/.config/Yubico

# Register your primary YubiKey
pamu2fcfg > ~/.config/Yubico/u2f_keys

# Register backup YubiKey (recommended)
pamu2fcfg -n >> ~/.config/Yubico/u2f_keys
```

### Usage

Once registered, touch your YubiKey when prompted during `sudo` authentication. If the YubiKey is not present or registration fails, standard password authentication is used as a fallback.

For more details, see the [Fedora YubiKey Quick Docs](https://docs.fedoraproject.org/en-US/quick-docs/using-yubikeys/).

---

## Package Validation & Dependency Tooling

### Package Dependency Checker

Cross-distro package dependency translation and verification.

```bash
python3 tools/package_dependency_checker.py --packages python3-requests neovim
python3 tools/package_dependency_checker.py --verify-only --json
```

<details>
<summary>Distro-specific examples</summary>

```bash
# Fedora
python3 tools/package_dependency_checker.py --packages python3-requests neovim

# Arch Linux
python3 tools/package_dependency_checker.py --distro arch --packages python-requests sway

# Debian/Ubuntu
python3 tools/package_dependency_checker.py --distro debian --packages python3-requests sway

# OpenSUSE
python3 tools/package_dependency_checker.py --distro opensuse --packages python3-requests waybar

# Gentoo
python3 tools/package_dependency_checker.py --distro gentoo --packages dev-python/requests greetd

# FreeBSD
python3 tools/package_dependency_checker.py --distro freebsd --packages py311-requests sway
```
</details>

### Validation CLI

```bash
python3 tools/validate_installed_packages.py --yaml adnyeus.yml --image-type fedora-bootc
python3 tools/validate_installed_packages.py --wm sway --distro arch
```

**Package naming equivalents:**

| Distro | Example |
|--------|---------|
| Fedora/Debian | `python3-requests` |
| Arch | `python-requests` |
| Gentoo | `dev-python/requests` |
| FreeBSD | `py311-requests` |

---

## Required Secrets

Configure in **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|--------|---------|
| `GHCR_PAT` | GHCR with `write:packages` scope |
| `DOCKERHUB_USERNAME` | Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token |
| `CODECOV_TOKEN` | Code coverage from [codecov.io](https://codecov.io) |

---

## Documentation

### Getting Started
- [BOOTC_UPGRADE.md](docs/BOOTC_UPGRADE.md) — Upgrade and switch images
- [BOOTC_IMAGE_BUILDER.md](docs/BOOTC_IMAGE_BUILDER.md) — Build disk images

### API
- [API Overview](docs/api/README.md) | [Endpoints](docs/api/endpoints.md) | [Development](docs/api/development.md)

### Testing
- [Testing Guide](docs/testing/guide.md) | [Test Suite](docs/testing/test_suite.md) | [Writing Tests](docs/reference/writing-tests.md)

### Reference
- [Plymouth Usage](docs/reference/plymouth_usage_doc.md) | [Troubleshooting](docs/reference/troubleshooting.md)

---

## External Resources

**Official:** [bootc Project](https://github.com/bootc-dev/bootc) | [bootc Docs](https://bootc-dev.github.io/bootc/) | [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)

**Community:** [Fedora Discussion](https://discussion.fedoraproject.org/tag/bootc) | [BlueBuild](https://blue-build.org/) | [Universal Blue](https://universal-blue.org/)

---

## Contributing

Contributions welcome! Submit PRs or open issues.

---

## License

MIT License — see LICENSE file.

---

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [RKE2](https://docs.rke2.io/) / [Rancher by SUSE](https://www.rancher.com/) for Kubernetes
- [Buildah](https://buildah.io/), [Skopeo](https://github.com/containers/skopeo), [Podman](https://podman.io/)
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### ZFS Feature Planning

- [Building ZFS — OpenZFS Documentation](https://openzfs.github.io/openzfs-docs/Developer%20Resources/Building%20ZFS.html)
- [Fedora — OpenZFS Documentation](https://openzfs.github.io/openzfs-docs/Getting%20Started/Fedora/index.html)
- [ZFS Kernel Compatibility Issues](https://github.com/openzfs/zfs/issues/17265)
- [ZFS Autobuild for CoreOS](https://github.com/kainzilla/zfs-autobuild)

### Creative Acknowledgments

**Tite Kubo** — Creator of *BLEACH*. The "Reiatsu" status indicator is inspired by themes from BLEACH, used respectfully as a playful aesthetic. All rights belong to Tite Kubo and respective copyright holders.

---

**Built with bootc**

*Generated on 2026-01-10 22:44:36 UTC*
