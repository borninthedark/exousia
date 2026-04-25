# Exousia - Declarative Bootc Image Builder

> *Can't Fear Your Own OS*
>
> **BLEACH** by **Tite Kubo** -- The Shinigami Pipeline,
> Reiatsu badge, and all captain naming are inspired by the Gotei 13
> from *BLEACH*. All rights belong to Tite Kubo and
> respective copyright holders.

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/urahara.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/borninthedark/exousia/actions/workflows/urahara.yml)
[![Last Build: Fedora 43 / Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20/%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/borninthedark/exousia/actions/workflows/urahara.yml?query=branch%3Amain+is%3Asuccess)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#contents)

Declarative bootc image builder for Fedora Linux. YAML blueprints define OS
images, Python tools transpile them to Containerfiles, Docker Buildx builds them,
and GitHub Actions pushes signed images to GHCR.

> **Warning** -- This project is highly experimental. There are no guarantees
> about stability, data safety, or fitness for any purpose.

---

## Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [CI/CD Pipeline](#cicd-pipeline)
- [Customizing Builds](#customizing-builds)
- [Official Dotfiles](#official-dotfiles)
- [YubiKey Authentication](#yubikey-authentication)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

---

## Quick Start

### Use a published image

```bash
make local-mirror
sudo bootc switch localhost:5000/exousia:latest
sudo bootc upgrade && sudo systemctl reboot
```

> Exousia delivers desktop apps via Flatpak. Set up Flathub before switching:
>
> ```bash
> flatpak remote-add --if-not-exists --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo
> ```

### Build locally

```bash
git clone https://github.com/borninthedark/exousia.git && cd exousia
make build
```

---

## How It Works

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}%%
graph LR
    A["adnyeus.yml<br/>(blueprint)"] --> B["Python transpiler<br/>(tools/*.py)"]
    B --> C["Containerfile"]
    C --> D["Docker Buildx"]
    D --> E["GHCR<br/>(signed image)"]
    B -.-> F["package_loader.py"]
    B -.-> G["resolve_build_config.py"]
```

- **Blueprint** (`adnyeus.yml`) -- declares base image, packages, overlays,
  scripts, services, and build flags.
- **Transpiler** (`uv run python -m generator`) -- reads the blueprint,
  loads package lists from `overlays/base/packages/`, and emits a valid
  Containerfile.
- **Overlays** -- static files, configs, and scripts organized under
  `overlays/base/` (shared) and `overlays/sway/` (desktop-specific).
- **Tests** -- pytest + Bats tests in `tests/` validate the built image.

---

## CI/CD Pipeline

Every workflow is named after a member of the **12th Division** -- the Shinigami
Research and Development Institute (SRDI). Division flower: **Calendula** --
*Despair in Your Heart*.

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}%%
graph TD
    A["Urahara<br/>(orchestrator)"] --> B["Hikifune<br/>(CI: lint+test)"]
    A --> C["Uhin<br/>(security scan)"]
    B & C --> D["Hiyori<br/>(build, sign, release)"]
    D --> E["Gate"]
    E --> F["Nemu<br/>(status report)"]
```

| Workflow | File | Role |
|----------|------|------|
| **Urahara** | `urahara.yml` | Orchestrator: calls Hikifune + Uhin in parallel, then Hiyori |
| **Hikifune** | `hikifune.yml` | CI: Ruff, Black, isort, pytest |
| **Uhin** | `uhin.yml` | Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Hiyori** | `hiyori.yml` | Build, Cosign, Trivy image scan, semver release |
| **Nemu** | `nemu.yml` | Post-CI: generates STATUS.md |
| **Mayuri** | `mayuri.yml` | Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Urahara |

Urahara calls Hikifune and Uhin in parallel. When both pass, Hiyori builds,
signs, scans, and cuts a semver release on `main`.

---

## Customizing Builds

### Packages

| Scope | Location |
|-------|----------|
| Base packages | `overlays/base/packages/common/*.yml` |
| Window managers | `overlays/base/packages/window-managers/*.yml` |
| Removals | `overlays/base/packages/common/remove.yml` |

All packages are managed through the package loader. Edit the YAML lists, not
the blueprint directly.

### Configuration

| Directory | Purpose |
|-----------|---------|
| `overlays/sway/configs/sway/` | Sway WM config, config.d snippets, environment |
| `overlays/sway/configs/xdg/waybar/` | Waybar config and Kripton theme CSS |
| `overlays/sway/configs/swaylock/` | Swaylock config (Kripton theme) |
| `overlays/sway/configs/greetd/` | greetd display manager |
| `overlays/sway/configs/plymouth/` | Boot splash themes |
| `overlays/base/configs/pam.d/` | PAM authentication (YubiKey U2F) |
| `overlays/sway/scripts/runtime/` | Runtime scripts (autotiling, lid, volume) |
| `overlays/sway/scripts/setup/` | Build-time setup scripts |

### Desktop and boot

- **Sway** uses a custom config with layered config.d overrides and the Kripton
  color scheme. System-level configs apply to all users; `/etc/skel/.config/`
  seeds new accounts.
- **Plymouth** is toggled via `enable_plymouth: true` in the blueprint.
- **greetd** is the login manager for all image types.

---

## Official Dotfiles

This project is designed to be used with the official **[borninthedark/dotfiles](https://github.com/borninthedark/dotfiles)** repository.

The image uses the `chezmoi` module to automatically initialize these dotfiles
on first login for all users, providing a consistent development environment
"out of the box".

---

## YubiKey Authentication

Exousia ships PAM U2F modules for YubiKey hardware authentication. After
deploying, register your key:

```bash
mkdir -p ~/.config/Yubico
pamu2fcfg > ~/.config/Yubico/u2f_keys       # primary key
pamu2fcfg -n >> ~/.config/Yubico/u2f_keys    # backup key (recommended)
```

`sudo` accepts YubiKey as an alternative to password by default. See
[Fedora YubiKey Quick Docs](https://docs.fedoraproject.org/en-US/quick-docs/using-yubikeys/).

---

## Required Secrets and Variables

Configure in GitHub **Settings > Secrets and variables > Actions**.

**Secrets:**

| Name | Purpose |
|------|---------|
| `GHCR_PAT` | GHCR personal access token for CI RPM override pulls and local/manual registry access |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `REGISTRY_URL` | Registry URL (defaults to `ghcr.io`) | No |

Secrets propagate to child workflows via `secrets: inherit` in Urahara.

---

## Documentation

**[Full Documentation Index](docs/README.md)**

| Document | Description |
|----------|-------------|
| [Upgrade Guide](docs/bootc-upgrade.md) | Switch images and perform bootc upgrades |
| [Image Builder](docs/bootc-image-builder.md) | Build bootable disk images (ISO, raw, qcow2) |
| [Module Reference](docs/modules.md) | Build module types, fields, and usage examples |
| [Package Loader CLI](docs/package-loader-cli.md) | Resolve package sets, inspect provenance, and export legacy manifests |
| [Package Management Design](docs/package-management-and-container-builds.md) | Typed package-set model, resolved build plans, and build-pipeline direction |
| [Overlay System](docs/overlay-system.md) | Overlay directory structure and how files map into images |
| [Local Build Pipeline](docs/local-build-pipeline.md) | Quadlet services, local build, GHCR publication, and local registry mirroring |
| [Sway + greetd](docs/sway-session-greetd.md) | Sway session with greetd login manager |
| [Test Suite](docs/testing/README.md) | Test architecture, categories, and writing guide |
| [Troubleshooting](docs/reference/troubleshooting.md) | Common issues and fixes |
| [Security Policy](SECURITY.md) | Vulnerability reporting and security model |

## Project Structure

| Directory | Purpose | Docs |
|-----------|---------|------|
| [`tools/`](tools/) | Python transpiler, package loader, build tools | [README](tools/README.md) |
| [`overlays/`](overlays/) | Static files and configs copied into images | [README](overlays/README.md) |
| [`overlays/base/`](overlays/base/) | Shared configs: PAM, polkit, sysusers, packages | [README](overlays/base/README.md) |
| [`overlays/sway/`](overlays/sway/) | Sway desktop: configs, scripts, session | [README](overlays/sway/README.md) |
| [`overlays/deploy/`](overlays/deploy/) | Podman Quadlet container definitions | [README](overlays/deploy/README.md) |
| [`tests/`](tests/) | Bats integration tests for built images | [README](tests/README.md) |
| [`yaml-definitions/`](yaml-definitions/) | Alternative build blueprints | [README](yaml-definitions/README.md) |
| [`docs/`](docs/) | Full documentation | [README](docs/README.md) |
| [`.github/workflows/`](.github/workflows/) | GitHub Actions CI/CD | [README](.github/workflows/README.md) |

---

## Contributing

Contributions welcome. Submit PRs or open issues. Use
[conventional commits](https://www.conventionalcommits.org/) for automatic
versioning.

---

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and the Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements and config references
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [Buildah](https://buildah.io/), [Podman](https://podman.io/), [Skopeo](https://github.com/containers/skopeo), [Docker](https://www.docker.com/)
- [Maple Mono](https://github.com/subframe7536/maple-font) by subframe7536 for the terminal and UI font
- [Kripton GTK Theme](https://github.com/EliverLara/Kripton) by EliverLara for the desktop color scheme
- [Cyberpunk Technotronic](https://github.com/dreifacherspass/cyberpunk-technotronic-icon-theme) by dreifacherspass for the icon theme
- [Bibata Cursor](https://github.com/ful1e5/Bibata_Cursor) by ful1e5 for the cursor theme

### AI-Assisted Development

This project uses AI-assisted development tools:

- **[Claude Code](https://claude.ai/claude-code)** (Anthropic)
- **[Gemini CLI](https://github.com/google-gemini/gemini-cli)** (Google)
- **[ChatGPT Codex](https://openai.com/index/openai-codex/)** (OpenAI)
- **[GitHub Dependabot](https://docs.github.com/en/code-security/dependabot)**
- **[github-actions[bot]](https://github.com/apps/github-actions)** -- automated releases and tagging

### Creative

**Tite Kubo** -- Creator of *BLEACH*. The CI/CD naming scheme (Shinigami Pipeline)
and Reiatsu status indicator are inspired by the Gotei 13 and themes from BLEACH,
used respectfully as a playful aesthetic. All rights belong to Tite Kubo and
respective copyright holders.

---

**Built with [bootc](https://github.com/bootc-dev/bootc)** | [Docs](https://bootc-dev.github.io/bootc/) | [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/) | MIT License
