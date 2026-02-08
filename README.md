# Exousia: Declarative Bootc Builder

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/borninthedark/exousia/aizen.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/borninthedark/exousia/actions/workflows/aizen.yml)
[![Last Build: Fedora 43 / Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%2F%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/borninthedark/exousia/actions/workflows/aizen.yml?query=branch%3Amain+is%3Asuccess)
[![Code Coverage](https://img.shields.io/codecov/c/github/borninthedark/exousia?style=for-the-badge&logo=codecov&logoColor=white&label=Coverage&token=G8NS9O5HZB)](https://codecov.io/gh/borninthedark/exousia)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)
<img src=".github/blue-sparrow.svg" alt="Blue Sparrow" width="28" />

Build custom, container-based immutable operating systems using the
[**bootc project**](https://github.com/bootc-dev/bootc). YAML blueprints define
OS images, Python tools transpile them to Containerfiles, Buildah builds them,
and GitHub Actions pushes signed images to DockerHub.

**Note:** The "Reiatsu" badge is inspired by *BLEACH* by **Tite Kubo** --
used as a playful status indicator with full acknowledgment.

## Table of Contents

- [Highly Experimental Disclaimer](#highly-experimental-disclaimer)
- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [The Shinigami Pipeline](#the-shinigami-pipeline)
- [Customizing Builds](#customizing-builds)
- [YubiKey Authentication](#yubikey-authentication)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

---

## Highly Experimental Disclaimer

> **Warning**: This project is highly experimental. There are **no guarantees**
> about stability, data safety, or fitness for any purpose. Proceed only if you
> understand the risks.

---

## Quick Start

### Use a published image

```bash
sudo bootc switch docker.io/1borninthedark/exousia:latest
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
just build
```

### Trigger a remote build

```bash
curl -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/borninthedark/exousia/actions/workflows/aizen.yml/dispatches \
  -d '{"ref":"main","inputs":{"image_type":"fedora-bootc","distro_version":"43","enable_plymouth":"true"}}'
```

Or use the manual **workflow_dispatch** in the [GitHub Actions UI](https://github.com/borninthedark/exousia/actions).

---

## How It Works

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}%%
graph LR
    A["adnyeus.yml<br/>(blueprint)"] --> B["Python transpiler<br/>(tools/*.py)"]
    B --> C["Containerfile"]
    C --> D["Buildah build"]
    D --> E["DockerHub<br/>(signed image)"]
    B -.-> F["package_loader.py"]
    B -.-> G["resolve_build_config.py"]
```

- **Blueprint** (`adnyeus.yml`) -- declares base image, packages, overlays,
  scripts, services, and build flags.
- **Transpiler** (`tools/yaml-to-containerfile.py`) -- reads the blueprint,
  loads package lists from `overlays/base/packages/`, and emits a valid
  Containerfile.
- **Overlays** -- static files, configs, and scripts organized under
  `overlays/base/` (shared) and `overlays/sway/` (desktop-specific).
- **Tests** -- Bats tests in `custom-tests/` validate the built image.

---

## The Shinigami Pipeline

Every workflow is named after a captain from the Gotei 13. Each captain's
division maps to the workflow's role in the pipeline:

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}%%
graph TD
    A["Aizen<br/>(orchestrator)"] --> B["Mayuri<br/>(CI: lint+test)"]
    A --> C["Byakuya<br/>(security scan)"]
    B --> D["Kyoraku<br/>(build, sign, release)"]
    C --> D
    D --> E["Gate"]
```

| Workflow | Captain | Division | Pipeline Role |
|----------|---------|----------|---------------|
| **Aizen** | Sosuke Aizen | The mastermind | Orchestrates the entire pipeline |
| **Mayuri** | Mayuri Kurotsuchi | 12th -- Research & Development | Ruff, Black, isort, pytest, Codecov |
| **Byakuya** | Byakuya Kuchiki | 6th -- Law & Order | Hadolint, Checkov, Trivy, Bandit, file structure |
| **Kyoraku** | Shunsui Kyoraku | Captain-Commander | Build, Cosign, Trivy scan, semver release |

Aizen calls Mayuri and Byakuya in parallel. When both pass, Kyoraku builds,
signs, scans, and cuts a semver release on `main`.

### Versioning

Versions are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` bumps minor, `fix:` bumps patch, `feat!:` bumps major.

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
| `overlays/sway/configs/sway/` | Sway WM and config.d snippets |
| `overlays/sway/configs/greetd/` | greetd display manager |
| `overlays/sway/configs/plymouth/` | Boot splash themes |
| `overlays/base/configs/pam.d/` | PAM authentication (YubiKey U2F) |
| `overlays/sway/scripts/runtime/` | Runtime scripts (autotiling, lid, volume) |
| `overlays/sway/scripts/setup/` | Build-time setup scripts |

### Desktop and boot

- **Sway** uses `sway-config-minimal` with layered config.d overrides.
  Configuration references drawn from [openSUSEway](https://github.com/openSUSE/openSUSEway).
- **Plymouth** is toggled via `enable_plymouth: true` in the blueprint.
- **greetd** is the login manager for all image types.
- **ZFS** is optional -- enable via `build.enable_zfs: true`. See [ZFS docs](docs/ZFS_BOOTC.md).

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
| `DOCKERHUB_TOKEN` | DockerHub access token |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `DOCKERHUB_USERNAME` | DockerHub username | Yes |
| `REGISTRY_URL` | Registry URL (defaults to `docker.io`) | No |

Secrets propagate to child workflows via `secrets: inherit` in Aizen.

---

## Documentation

**[Full Documentation Index](docs/README.md)**

| Topic | Links |
|-------|-------|
| Getting Started | [Upgrade Guide](docs/BOOTC_UPGRADE.md) &#124; [Image Builder](docs/BOOTC_IMAGE_BUILDER.md) |
| Desktop | [Sway + greetd](docs/sway-session-greetd.md) &#124; [Plymouth](docs/reference/plymouth_usage_doc.md) |
| Testing | [Test Suite](docs/testing/README.md) &#124; [Writing Tests](docs/reference/writing-tests.md) |
| Reference | [Troubleshooting](docs/reference/troubleshooting.md) &#124; [Security](SECURITY.md) |

---

## Contributing

Contributions welcome. Submit PRs or open issues. Use
[conventional commits](https://www.conventionalcommits.org/) for automatic
versioning.

---

## License

MIT License -- see LICENSE file.

---

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and the Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements and config references
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [Buildah](https://buildah.io/), [Podman](https://podman.io/), [Skopeo](https://github.com/containers/skopeo)

### AI-Assisted Development

This project uses AI-assisted development tools:

- **[Claude Code](https://claude.ai/claude-code)** (Anthropic) -- code generation, refactoring, and CI/CD pipeline design
- **[ChatGPT Codex](https://openai.com/index/openai-codex/)** (OpenAI) -- code generation and documentation
- **[GitHub Dependabot](https://docs.github.com/en/code-security/dependabot)** -- automated dependency updates for Actions and pip

### Creative

**Tite Kubo** -- Creator of *BLEACH*. The CI/CD naming scheme (Shinigami Pipeline)
and Reiatsu status indicator are inspired by the Gotei 13 and themes from BLEACH,
used respectfully as a playful aesthetic. All rights belong to Tite Kubo and
respective copyright holders.

---

**Built with [bootc](https://github.com/bootc-dev/bootc)** | [Docs](https://bootc-dev.github.io/bootc/) | [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/) | MIT License
