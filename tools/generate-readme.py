#!/usr/bin/env python3
"""Generate README.md from template with dynamic documentation section."""

from __future__ import annotations

from pathlib import Path

REPO = "borninthedark/exousia"

# Documentation entries: (rel_path, title, description)
DOC_ENTRIES: list[tuple[str, str, str]] = [
    (
        "docs/README.md",
        "Documentation Index",
        "Full docs: getting started, architecture, desktop, testing, reference",
    ),
    (
        "docs/bootc-upgrade.md",
        "Upgrade Guide",
        "Switch images and perform bootc upgrades",
    ),
    (
        "docs/bootc-image-builder.md",
        "Image Builder",
        "Build bootable disk images (ISO, raw, qcow2)",
    ),
    (
        "docs/overlay-system.md",
        "Overlay System",
        "Overlay directory structure and how files map into images",
    ),
    (
        "docs/local-build-pipeline.md",
        "Local Build Pipeline",
        "Quadlet services, local build, and promotion to DockerHub",
    ),
    (
        "docs/sway-session-greetd.md",
        "Sway + greetd",
        "Sway session with greetd login manager",
    ),
    (
        "docs/zfs-bootc.md",
        "ZFS Support",
        "Optional ZFS kernel module build process",
    ),
    (
        "docs/testing/README.md",
        "Test Suite",
        "Test architecture, categories, and writing guide",
    ),
    (
        "docs/reference/troubleshooting.md",
        "Troubleshooting",
        "Common issues and fixes",
    ),
    (
        "SECURITY.md",
        "Security Policy",
        "Vulnerability reporting and security model",
    ),
]

# Subdirectory entries: (rel_path, title, description)
SUBDIR_ENTRIES: list[tuple[str, str, str]] = [
    ("tools/", "Build Tools", "Python transpiler, package loader, build tools"),
    ("overlays/", "Overlays", "Static files and configs copied into images"),
    ("overlays/base/", "Base Overlay", "Shared configs: PAM, polkit, sysusers, packages"),
    ("overlays/sway/", "Sway Overlay", "Sway desktop: configs, scripts, session"),
    ("overlays/deploy/", "Deploy Overlay", "Podman Quadlet container definitions"),
    ("custom-tests/", "Test Suite", "Bats integration tests for built images"),
    ("yaml-definitions/", "YAML Definitions", "Alternative build blueprints"),
    ("ansible/", "Ansible", "Post-deployment Ansible playbooks"),
    ("docs/", "Documentation", "Full documentation"),
    (".github/workflows/", "Shinigami Pipeline", "GitHub Actions CI/CD"),
    (".forgejo/workflows/", "Espada Pipeline", "Forgejo Actions CI/CD"),
]


def _docs_table(root: Path) -> str:
    rows = ["| Document | Description |", "|----------|-------------|"]
    for rel_path, title, desc in DOC_ENTRIES:
        if (root / rel_path).exists():
            rows.append(f"| [{title}]({rel_path}) | {desc} |")
    return "\n".join(rows)


def _structure_table(root: Path) -> str:
    rows = [
        "| Directory | Purpose | Docs |",
        "|-----------|---------|------|",
    ]
    for rel_path, _title, desc in SUBDIR_ENTRIES:
        dir_path = root / rel_path
        readme = dir_path / "README.md"
        if dir_path.exists():
            if readme.exists():
                rows.append(
                    f"| [`{rel_path}`]({rel_path}) | {desc} " f"| [README]({rel_path}README.md) |"
                )
            else:
                rows.append(f"| [`{rel_path}`]({rel_path}) | {desc} | -- |")
    return "\n".join(rows)


def generate_readme(root: Path) -> str:
    docs = _docs_table(root)
    structure = _structure_table(root)

    return f"""\
# Exousia - Declarative Bootc Image Builder

> *Can't Fear Your Own OS*

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/{REPO}/aizen.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/{REPO}/actions/workflows/aizen.yml)
[![Last Build: Fedora 43 / Sway](https://img.shields.io/badge/Last%20Build-Fedora%2043%20%2F%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/{REPO}/actions/workflows/aizen.yml?query=branch%3Amain+is%3Asuccess)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)

Declarative, container-based immutable operating systems built on
[**bootc**](https://github.com/bootc-dev/bootc). YAML blueprints define OS
images, Python tools transpile them to Containerfiles, Buildah builds them, and
GitHub Actions pushes signed images to DockerHub.

**Note:** The "Reiatsu" badge is inspired by *BLEACH* by **Tite Kubo** --
used as a playful status indicator with full acknowledgment.

## Table of Contents

- [Highly Experimental Disclaimer](#highly-experimental-disclaimer)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
  - [Build Flow](#build-flow)
  - [The Shinigami Pipeline](#the-shinigami-pipeline)
  - [Versioning](#versioning)
- [Customizing Builds](#customizing-builds)
- [Local Build Pipeline](#local-build-pipeline)
- [YubiKey Authentication](#yubikey-authentication)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Highly Experimental Disclaimer

> **Warning**: This project is highly experimental. There are **no guarantees**
> about stability, data safety, or fitness for any purpose. Proceed only if you
> understand the risks.

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
git clone https://github.com/{REPO}.git && cd exousia
just build
```

### Trigger a remote build

```bash
curl -X POST \\
  -H "Accept: application/vnd.github+json" \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  https://api.github.com/repos/{REPO}/actions/workflows/aizen.yml/dispatches \\
  -d '{{"ref":"main","inputs":{{"image_type":"fedora-bootc","distro_version":"43","enable_plymouth":"true"}}}}'
```

Or use the manual **workflow_dispatch** in the [GitHub Actions UI](https://github.com/{REPO}/actions).

## Architecture

### Build Flow

```mermaid
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
graph LR
    A["adnyeus.yml<br/>(blueprint)"] --> B["Python transpiler<br/>(tools/*.py)"]
    B --> C["Containerfile"]
    C --> D["Buildah build"]
    D --> E["DockerHub<br/>(signed image)"]
    B -.-> F["package_loader.py"]
    B -.-> G["resolve_build_config.py"]
```

| Component | Description |
|-----------|-------------|
| **Blueprint** (`adnyeus.yml`) | Declares base image, packages, overlays, scripts, services, and build flags |
| **Transpiler** (`tools/yaml-to-containerfile.py`) | Reads the blueprint, loads package lists from `overlays/base/packages/`, emits a valid Containerfile |
| **Overlays** | Static files, configs, and scripts under `overlays/base/` (shared) and `overlays/sway/` (desktop) |
| **Tests** | Bats tests in `custom-tests/` validate the built image |

### The Shinigami Pipeline

Every CI workflow is named after a captain from the Gotei 13. Each captain's
division maps to the workflow's role:

```mermaid
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
graph TD
    A["Aizen<br/>(orchestrator)"] --> B["Mayuri<br/>(CI: lint+test)"]
    A --> C["Byakuya<br/>(security scan)"]
    B --> D["Kyoraku<br/>(build, sign, release)"]
    C --> D
    D --> E["Gate"]
    E --> F["Yoruichi<br/>(status report)"]
```

| Captain | Division | Role | Key Tools |
|---------|----------|------|-----------|
| **Aizen** | -- | Orchestrator | Calls Mayuri + Byakuya in parallel, then Kyoraku |
| **Mayuri** | 12th (R&D) | CI | Ruff, Black, isort, pytest |
| **Byakuya** | 6th (Law) | Security | Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | Captain-Commander | Build & Release | Docker Buildx, Cosign (OIDC), Trivy image scan, semver |
| **Yoruichi** | 2nd (Stealth) | Status Report | Generates STATUS.md, updates badges |

### Versioning

Versions are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` bumps minor, `fix:` bumps patch, `feat!:` bumps major.

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
- **ZFS** is optional -- enable via `build.enable_zfs: true`. See [ZFS docs](docs/zfs-bootc.md).

## Local Build Pipeline

Build images locally with Podman Quadlet services before promoting to DockerHub:

```bash
just quadlet-install && just quadlet-start   # start Forgejo + local registry
just local-build                             # generate containerfile, buildah build, push to local registry
just local-test                              # run bats tests against local image
just local-push                              # promote to DockerHub via skopeo
```

See [Local Build Pipeline docs](docs/local-build-pipeline.md) for the full
setup, Forgejo runner registration, and troubleshooting.

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

## Documentation

**[Full Documentation Index](docs/README.md)**

{docs}

## Project Structure

{structure}

## Contributing

Contributions welcome. Submit PRs or open issues. Use
[conventional commits](https://www.conventionalcommits.org/) for automatic
versioning.

## License

MIT License -- see LICENSE file.

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and the Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements and config references
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [Buildah](https://buildah.io/), [Podman](https://podman.io/), [Skopeo](https://github.com/containers/skopeo)

### AI-Assisted Development

This project uses AI-assisted development tools:

- **[Claude Code](https://claude.ai/claude-code)** (Anthropic)
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
"""


def update_readme() -> bool:
    root = Path(__file__).resolve().parent.parent
    readme = root / "README.md"
    content = generate_readme(root)
    if readme.exists() and readme.read_text(encoding="utf-8") == content:
        print("README.md is up to date")
        return True
    readme.write_text(content, encoding="utf-8")
    print("Generated README.md")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if update_readme() else 1)
