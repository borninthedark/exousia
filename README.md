# Exousia

[![Last Build: Fedora 43 / Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%2F%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](#the-shinigami-pipeline)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Declarative bootc image builder for Fedora Linux. YAML blueprints define OS
images, Python tools transpile them to Containerfiles, Buildah builds them, and
GitHub Actions pushes signed images to DockerHub.

> **Warning** -- This project is highly experimental. There are no guarantees
> about stability, data safety, or fitness for any purpose.

---

## Contents

- [Quick Start](#quick-start)
- [How It Works](#how-it-works)
- [The Shinigami Pipeline](#the-shinigami-pipeline)
- [Customizing Builds](#customizing-builds)
- [YubiKey Authentication](#yubikey-authentication)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)

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

```text
adnyeus.yml          Python transpiler          Buildah           DockerHub
 (blueprint)   --->  (tools/*.py)         --->  (Containerfile)  --->  (signed image)
                          |
                    package_loader.py
                    resolve_build_config.py
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

```text
              Aizen (orchestrator)
             /                    \
      Mayuri                      Byakuya        <-- parallel
   (CI: lint+test)             (security scan)
             \                    /
              Kyoraku
       (build, sign, release)
                 |
               Gate
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

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) and the Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [Buildah](https://buildah.io/), [Podman](https://podman.io/), [Skopeo](https://github.com/containers/skopeo)

### Creative

**Tite Kubo** -- Creator of *BLEACH*. The CI/CD naming scheme and Reiatsu
status indicator are inspired by the Gotei 13 and themes from BLEACH, used
respectfully as a playful aesthetic. All rights belong to Tite Kubo and
respective copyright holders.

---

**Built with [bootc](https://github.com/bootc-dev/bootc)** | [Docs](https://bootc-dev.github.io/bootc/) | [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/) | MIT License
