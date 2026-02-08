# Exousia: Declarative Bootc Builder

[![Last Build: Fedora 43 • Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%E2%80%A2%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](#build--release-workflow)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Build custom, container-based immutable operating systems using the [**bootc project**](https://github.com/bootc-dev/bootc). Images are built, tested, and published via GitHub Actions to DockerHub.

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
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Highly Experimental Disclaimer

> **Warning**: This project is highly experimental. There are **no guarantees** about stability, data safety, or fitness for any purpose. Proceed only if you understand the risks.

---

## Project Snapshot

- **Purpose:** Declarative laptop images with a DevSecOps-friendly workflow.
- **Outputs:** bootc Sway images published to DockerHub.
- **Tooling:** Python CLI tools in `tools/`, YAML-based blueprints, and `just` task runner.
- **Security/Quality:** Linting, scanning, and automated tests baked into CI.

---

## Build & Release Workflow

### Semantic Versioning

Version bumps are determined automatically from [conventional commits](https://www.conventionalcommits.org/):

- `feat:` → minor bump
- `fix:` → patch bump
- `feat!:` or `BREAKING CHANGE:` → major bump

### CI/CD Pipeline (Phoenician Pantheon)

All workflows use Phoenician mythology-themed names and run on GitHub Actions.

| Workflow | Role | Trigger |
|----------|------|---------|
| **El** | Orchestrator (king of the gods) | Push to main, PR |
| **Anat** | CI: lint, test, validate (goddess of wisdom) | Called by El |
| **Resheph** | Security: Checkov, Trivy, Bandit (god of protection) | Called by El |
| **Kothar** | Build + push to DockerHub (god of craftsmanship) | Called by El |
| **Eshmun** | Release: semver, retag, GitHub Release (god of renewal) | After gate on main |

### Pipeline Stages

| Stage | What happens |
|-------|--------------|
| **Anat** | Hadolint, file structure, Containerfile gen, Ruff, Black, pytest + Codecov |
| **Resheph** | Checkov (Containerfile), Trivy config scan, Bandit SAST |
| **Kothar** | Buildah image build, DockerHub push, Trivy image scan, Cosign signing |
| **Eshmun** | Semver from commits, retag image, GitHub Release |

**Triggers:** pushes to `main`, pull requests, and manual workflow dispatch.

---

## Getting Started

### Prerequisites

- Fedora system (Atomic variant recommended)
- DockerHub account (or local container registry)
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
# From DockerHub
sudo bootc switch docker.io/1borninthedark/exousia:latest
sudo bootc upgrade && sudo systemctl reboot
```

### Build Locally

```bash
git clone <your-forgejo-url>/exousia.git
cd exousia
just build
```

---

## Triggering Builds Remotely

Trigger builds programmatically via the webhook API.

**Prerequisites:** GitHub API token, Python 3.11+ with `requests`

### Python CLI

```bash
# Set your Forgejo token
export GITHUB_TOKEN="your_token_here"

# Trigger a build using repo defaults
python tools/webhook_trigger.py

# Trigger specific image type and version
python tools/webhook_trigger.py \
  --image-type fedora-sway-atomic \
  --distro-version 43 \
  --enable-plymouth

# Build with specific window manager
python tools/webhook_trigger.py --wm sway --distro-version 43
```

<details>
<summary>More Python examples</summary>

```bash
# Use a YAML definition file
python tools/webhook_trigger.py --yaml sway-bootc.yml --distro-version 44

# Disable Plymouth
python tools/webhook_trigger.py --yaml sway-atomic.yml --disable-plymouth --verbose
```

</details>

### cURL API

```bash
# Trigger a build via GitHub Actions workflow dispatch
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/borninthedark/exousia/actions/workflows/el.yml/dispatches \
  -d '{
    "ref": "main",
    "inputs": {
      "image_type": "fedora-bootc",
      "distro_version": "43",
      "enable_plymouth": "true"
    }
  }'
```

<details>
<summary>More cURL examples</summary>

```bash
# Build Sway Atomic variant
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/borninthedark/exousia/actions/workflows/el.yml/dispatches \
  -d '{"ref": "main", "inputs": {"image_type": "fedora-sway-atomic", "distro_version": "43", "enable_plymouth": "true"}}'
```

</details>

View builds on [GitHub Actions](https://github.com/borninthedark/exousia/actions) | [Webhook API Guide](docs/WEBHOOK_API.md)

---

## Customizing Builds

### Switch Blueprint Versions

```bash
# Via webhook CLI
python tools/webhook_trigger.py --image-type fedora-bootc --distro-version 44
python tools/webhook_trigger.py --image-type fedora-sway-atomic --distro-version 43
```

Or use the manual workflow dispatch in the GitHub Actions UI.

### Adjust Packages

| Scope | Where to edit | What to change |
|-------|---------------|----------------|
| Base packages | `overlays/base/packages/common/*.yml` | Add/remove shared package sets |
| Window managers | `overlays/base/packages/window-managers/*.yml` | Add to the relevant categories |

All package additions are managed from the `overlays/base/packages/` directory via the package loader; avoid editing YAML definitions for package lists.

### Configuration Files

| Directory | Purpose |
|-----------|---------|
| `overlays/sway/configs/sway/` | Sway WM and config.d snippets |
| `overlays/sway/configs/greetd/` | Display manager (greetd) |
| `overlays/sway/configs/plymouth/` | Boot splash themes |
| `overlays/sway/configs/swaylock/` | Swaylock screen lock |
| `overlays/base/configs/pam.d/` | PAM authentication (YubiKey U2F) |
| `overlays/sway/scripts/runtime/` | Runtime scripts (autotiling, lid, volume-helper) |
| `overlays/sway/scripts/setup/` | Build-time setup scripts |
| `overlays/base/tools/` | Shared scripts |

### Desktop & Boot Experience

- **Sway** uses `sway-config-minimal` for headless/container compatibility.
  - `/usr/share/sway/config.d/*.conf` — Packaged configs
  - `/etc/sway/config.d/*.conf` — System overrides
  - `~/.config/sway/config.d/*.conf` — User overrides
  - See [Fedora Sericea Configuration Guide](https://docs.fedoraproject.org/en-US/fedora-sericea/configuration-guide/).
- **Plymouth**: Set `enable_plymouth: true` in YAML; themes live in `overlays/sway/configs/plymouth/themes/`.
- **Display managers**: all images use greetd.

---

## YubiKey Authentication (PAM U2F)

Exousia includes built-in support for YubiKey hardware authentication using PAM U2F. This allows you to use your YubiKey as a second factor or alternative authentication method for `sudo`, login, and other PAM-aware services.

### Configuration

The system includes pre-configured PAM modules in `overlays/base/configs/pam.d/`:

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

Configure in GitHub repository settings under **Settings → Secrets and variables → Actions**:

**Secrets:**

| Secret | Purpose |
|--------|---------|
| `DOCKERHUB_USERNAME` | DockerHub username |
| `DOCKERHUB_TOKEN` | DockerHub access token |

**Variables:**

| Variable | Purpose |
|----------|---------|
| `DOCKERHUB_IMAGE` | Image path (e.g., `1borninthedark/exousia`) |
| `REGISTRY_URL` | Registry URL (e.g., `docker.io`) |

---

## Documentation

**[Full Documentation Index](docs/README.md)**

| Topic | Links |
|-------|-------|
| Getting Started | [Upgrade Guide](docs/BOOTC_UPGRADE.md) &#124; [Image Builder](docs/BOOTC_IMAGE_BUILDER.md) |
| Testing | [Guide](docs/testing/README.md) &#124; [Writing Tests](docs/reference/writing-tests.md) |
| Reference | [Troubleshooting](docs/reference/troubleshooting.md) &#124; [Webhook API](docs/WEBHOOK_API.md) |

---

## Contributing

Contributions welcome! Submit PRs or open issues. Use [conventional commits](https://www.conventionalcommits.org/) for automatic versioning.

---

## AI-Assisted Development

This project was developed with assistance from [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [ChatGPT Codex](https://chatgpt.com/codex), and [GitHub Dependabot](https://docs.github.com/en/code-security/dependabot) for automated dependency security updates.

---

## License

MIT License — see LICENSE file.

---

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [GitHub Actions](https://github.com/features/actions) for CI/CD pipelines
- [Buildah](https://buildah.io/), [Skopeo](https://github.com/containers/skopeo), [Podman](https://podman.io/)
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### Creative Acknowledgments

**Tite Kubo** — Creator of *BLEACH*. The "Reiatsu" status indicator is inspired by themes from BLEACH, used respectfully as a playful aesthetic. All rights belong to Tite Kubo and respective copyright holders.

---

**Built with [bootc](https://github.com/bootc-dev/bootc)** | [Docs](https://bootc-dev.github.io/bootc/) | [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)

*Generated on 2026-02-08 02:01:46 UTC*
