#!/usr/bin/env python3
"""Generate README.md from template with dynamic documentation section."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = "borninthedark/exousia"
_BLUEPRINT = Path(__file__).resolve().parent.parent / "adnyeus.yml"


def _blueprint_version() -> str:
    """Read image-version from the blueprint."""
    if _BLUEPRINT.exists():
        config = yaml.safe_load(_BLUEPRINT.read_text()) or {}
        version = config.get("image-version")
        if version:
            return str(version)
    return "43"


FEDORA_VERSION = _blueprint_version()

# Documentation entries: (rel_path, title, description)
DOC_ENTRIES: list[tuple[str, str, str]] = [
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
        "docs/package-loader-cli.md",
        "Package Loader CLI",
        "Resolve package sets, inspect provenance, and export legacy manifests",
    ),
    (
        "docs/package-management-and-container-builds.md",
        "Package Management Design",
        "Typed package-set model, resolved build plans, and build-pipeline direction",
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
    ("docs/", "Documentation", "Full documentation"),
    (".github/workflows/", "Shinigami Pipeline", "GitHub Actions CI/CD"),
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
>
> **BLEACH** by **Tite Kubo** -- The Shinigami Pipeline,
> Reiatsu badge, and all captain naming are inspired by the Gotei 13
> from *BLEACH*. All rights belong to Tite Kubo and
> respective copyright holders.

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/{REPO}/urahara.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/{REPO}/actions/workflows/urahara.yml)
[![Last Build: Fedora {FEDORA_VERSION} / Sway](https://img.shields.io/badge/Last%20Build-Fedora%20{FEDORA_VERSION}%20%2F%20Sway-0A74DA?style=for-the-badge&logo=fedora&logoColor=white)](https://github.com/{REPO}/actions/workflows/urahara.yml?query=branch%3Amain+is%3Asuccess)
[![Highly Experimental](https://img.shields.io/badge/Highly%20Experimental-DANGER%21-E53935?style=for-the-badge&logo=skull&logoColor=white)](#highly-experimental-disclaimer)

DevSecOps-hardened, container-based immutable operating systems built on
[**bootc**](https://github.com/bootc-dev/bootc). YAML blueprints define OS
images, Python tools transpile them to Containerfiles, Docker Buildx builds them,
and GitHub Actions pushes signed images to DockerHub.

Development follows a **TDD-first, shift-left** methodology — see
[Contributing](#contributing) for details.

## CVE Remediations

Exousia ships patched versions of packages ahead of upstream Fedora when
required. Packages are built from upstream source, hosted as OCI images on
GHCR, and injected at build time via RPM overrides. See
[SECURITY.md](SECURITY.md#rpm-override-process) for the full process.

| Package | Patched Version | Reason |
|---------|----------------|--------|
| flatpak | 1.16.6 | CVE remediation — fixes disclosed 2026-04-12 ([release notes](https://github.com/flatpak/flatpak/releases/tag/1.16.6)) |

## Table of Contents

- [CVE Remediations](#cve-remediations)
- [Highly Experimental Disclaimer](#highly-experimental-disclaimer)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
  - [Build Flow](#build-flow)
  - [The 12th Division Pipeline](#the-12th-division-pipeline)
  - [Versioning](#versioning)
- [Customizing Builds](#customizing-builds)
  - [Package Workflow](#package-workflow)
  - [Configuration](#configuration)
  - [Desktop and boot](#desktop-and-boot)
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
make build
```

### Trigger a remote build

```bash
curl -X POST \\
  -H "Accept: application/vnd.github+json" \\
  -H "Authorization: Bearer $GITHUB_TOKEN" \\
  https://api.github.com/repos/{REPO}/actions/workflows/urahara.yml/dispatches \\
  -d '{{"ref":"main","inputs":{{"image_type":"fedora-bootc","distro_version":"{FEDORA_VERSION}","enable_plymouth":"true"}}}}'
```

Or use the manual **workflow_dispatch** in the [GitHub Actions UI](https://github.com/{REPO}/actions).

## Architecture

### Build Flow

```mermaid
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
graph LR
    subgraph Input
        A["adnyeus.yml"]
        O["overlays/"]
        P["packages/*.yml"]
    end
    subgraph Transpiler
        G["resolve_build_config.py"]
        F["uv run python -m package_loader"]
        B["uv run python -m generator"]
    end
    A --> G --> B
    O --> B
    P --> F --> B
    B --> C["Containerfile"]
    C --> D["Docker Buildx"]
    D --> T["Bats tests"]
    T --> E["Registry"]
```

| Component | Description |
|-----------|-------------|
| **Blueprint** (`adnyeus.yml`) | Declares base image, packages, overlays, scripts, services, and build flags |
| **Transpiler** (`uv run python -m generator`) | Reads the blueprint, resolves package sets, optionally writes `build/resolved-build-plan*.json`, and emits a valid Containerfile |
| **Overlays** | Static files, configs, and scripts under `overlays/base/` (shared) and `overlays/sway/` (desktop) |
| **Tests** | Pytest validates the Python tooling and Bats validates the built image |

### The 12th Division Pipeline

Every CI workflow is named after a member of the **12th Division** — the Shinigami
Research and Development Institute (SRDI). Division flower: **Calendula** — *Despair
in Your Heart*.

```mermaid
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
graph TD
    A["Urahara"] --> B["Hikifune"] & C["Uhin"]
    B & C --> K["Hiyori: build"]
    K --> S["scan"] & SG["sign"]
    S & SG --> R["release"]
    R --> G["Gate"]
    G --> Y["Nemu"]
```

| Member | Role | Key Tools |
|--------|------|-----------|
| **Urahara** | Orchestrator | Calls Hikifune + Uhin in parallel, then Hiyori |
| **Hikifune** | CI | Ruff, Black, isort, pytest |
| **Uhin** | Security | Hadolint, Checkov, Trivy config scan, Bandit |
| **Hiyori** | Build & Release | Docker Buildx, Cosign (OIDC), Trivy image scan, semver |
| **Nemu** | Status Report | Generates STATUS.md |

### Versioning

Versions are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` bumps minor, `fix:` bumps patch, `feat!:` bumps major.

## Customizing Builds

### Package Workflow

| Scope | Location |
|-------|----------|
| RPM overrides | `overlays/base/packages/common/rpm-overrides.yml` |
| Common package sets | `overlays/base/packages/common/base-*.yml` |
| Feature package sets | `overlays/base/packages/common/*.yml` |
| Window-manager package sets | `overlays/base/packages/window-managers/*.yml` |
| Removal list | `overlays/base/packages/common/remove.yml` |

All package selection flows through the package loader. Edit package-set YAML under
`overlays/base/packages/`, then verify the resolved output before building:

```bash
uv run python -m package_loader --wm sway --json
uv run python -m generator \\
  --config adnyeus.yml \\
  --resolved-package-plan build/resolved-build-plan.json \\
  --output Dockerfile.generated
```

The resolved plan records package/group install and removal provenance so CI and
tests can verify what the image is meant to contain. See
[Package Loader CLI](docs/package-loader-cli.md) and
[Package Management Design](docs/package-management-and-container-builds.md).

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

## Local Build Pipeline

Build images locally with Podman Quadlet services before promoting to DockerHub:

```bash
make quadlet-install && make quadlet-start   # start Forgejo + local registry
make local-build                             # generate containerfile, buildah build, push to local registry
make local-test                              # run bats tests against local image
make local-push                              # promote to DockerHub via skopeo
```

See [Local Build Pipeline docs](docs/local-build-pipeline.md) for the full
setup, Forgejo runner registration, and troubleshooting.

---

## YubiKey Authentication

Exousia ships PAM U2F modules for YubiKey hardware authentication. After
deploying, register your key in the shared authfile:

```bash
sudo install -d -m 0755 /etc/Yubico
pamu2fcfg -u "$USER" | sudo tee -a /etc/Yubico/u2f_keys >/dev/null
pamu2fcfg -n -u "$USER" | sudo tee -a /etc/Yubico/u2f_keys >/dev/null
```

New users inherit `~/.config/Yubico -> /etc/Yubico` from `/etc/skel`.
`sudo` and local `login` accept YubiKey as an alternative to password by
default. See
[Fedora YubiKey Quick Docs](https://docs.fedoraproject.org/en-US/quick-docs/using-yubikeys/).

## Required Secrets and Variables

Configure in GitHub **Settings > Secrets and variables > Actions**.

**Secrets:**

| Name | Purpose |
|------|---------|
| `DOCKERHUB_TOKEN` | DockerHub access token |
| `GHCR_PAT` | GHCR personal access token (`packages:read`) |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `DOCKERHUB_USERNAME` | DockerHub username | Yes |
| `REGISTRY_URL` | Registry URL (defaults to `docker.io`) | No |

Secrets propagate to child workflows via `secrets: inherit` in Urahara.

## Documentation

**[Full Documentation Index](docs/README.md)**

{docs}

## Project Structure

{structure}

## Contributing

Contributions welcome. Development rules:

- **TDD mandatory** -- write tests before implementation and keep test intent close to the change
- **Coverage floor** -- `tools/` pytest coverage is enforced at 71% and should keep ratcheting upward
- **[Conventional commits](https://www.conventionalcommits.org/)** -- enforced by pre-commit hook
- **Shift-left** -- `uv run pre-commit install && uv run pre-commit install --hook-type commit-msg`
- Security gates (Bandit, Gitleaks) and quality checks (Ruff, Black, mypy) run locally before push

## License

MIT License -- see LICENSE file.

## Acknowledgments

- [bootc project](https://github.com/bootc-dev/bootc) maintainers and the Fedora community
- [Fedora Sway SIG](https://gitlab.com/fedora/sigs/sway/sway-config-fedora) for Sway configs and QoL improvements
- [openSUSEway](https://github.com/openSUSE/openSUSEway) for Sway enhancements and config references
- [Universal Blue](https://universal-blue.org/) and [BlueBuild](https://blue-build.org/) for container-native workflows
- [Buildah](https://buildah.io/), [Podman](https://podman.io/), [Skopeo](https://github.com/containers/skopeo), [Docker](https://www.docker.com/)

### AI-Assisted Development

This project uses AI-assisted development tools:

- **[Claude Code](https://claude.ai/claude-code)** (Anthropic)
- **[ChatGPT Codex](https://openai.com/index/openai-codex/)** (OpenAI)
- **[GitHub Dependabot](https://docs.github.com/en/code-security/dependabot)**
- **[github-actions[bot]](https://github.com/apps/github-actions)** -- automated releases and tagging

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
