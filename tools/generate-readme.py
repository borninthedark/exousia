#!/usr/bin/env python3
"""
Dynamic README generator for Exousia.

Generates the published README from repository metadata and the active
blueprint so docs stay aligned with the current image definition.
"""

import argparse
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

REPO = "borninthedark/exousia"

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
        "docs/modules.md",
        "Module Reference",
        "Build module types, fields, and usage examples",
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
        "Quadlet services, local build, GHCR publication, and local registry mirroring",
    ),
    (
        "docs/fedora-bootc-migration-plan.md",
        "Fedora bootc Migration Plan",
        "Base-image migration plan and package audit checklist",
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
    ("tests/", "Test Suite", "Bats integration tests for built images"),
    ("yaml-definitions/", "YAML Definitions", "Alternative build blueprints"),
    ("docs/", "Documentation", "Full documentation"),
    (".github/workflows/", "Shinigami Pipeline", "GitHub Actions CI/CD"),
]


class Colors:
    """Terminal colors (disabled in CI)."""

    def __init__(self) -> None:
        if os.environ.get("CI") == "true":
            self.GREEN = self.BLUE = self.YELLOW = self.RED = self.NC = ""
        else:
            self.GREEN = "\033[0;32m"
            self.BLUE = "\033[0;34m"
            self.YELLOW = "\033[1;33m"
            self.RED = "\033[0;31m"
            self.NC = "\033[0m"

    def success(self, msg: str) -> None:
        print(f"{self.GREEN}+{self.NC} {msg}")

    def info(self, msg: str) -> None:
        print(f"{self.BLUE}i{self.NC} {msg}")

    def warning(self, msg: str) -> None:
        print(f"{self.YELLOW}!{self.NC} {msg}")

    def error(self, msg: str) -> None:
        print(f"{self.RED}x{self.NC} {msg}", file=sys.stderr)


class Config:
    """Build configuration extracted from repository metadata."""

    def __init__(self) -> None:
        self.os_name = "Linux"
        self.os_logo = "linux"
        self.os_badge_color = "0A74DA"
        self.os_version = ""
        self.image_type = ""
        self.image_type_display = ""
        self.wm_de_label = "Unknown"
        self.github_repo = ""
        self.github_owner = ""
        self.docker_image = ""
        self.build_date = ""
        self.build_badge_text_uri = ""


def get_repo_root() -> Path:
    """Determine repository root reliably."""
    if github_ws := os.environ.get("GITHUB_WORKSPACE"):
        return Path(github_ws)

    script_path = Path(__file__).resolve()
    # tools/generate-readme.py -> repo root
    return script_path.parent.parent


def extract_config(repo_root: Path, colors: Colors) -> Config:
    """Extract configuration from repository metadata."""
    config = Config()
    colors.info(f"Repository root: {repo_root}")

    adnyeus_path = repo_root / "adnyeus.yml"
    base_image = ""

    if adnyeus_path.exists():
        colors.info(f"Found image definition blueprint: {adnyeus_path}")

        if yaml:
            blueprint = yaml.safe_load(adnyeus_path.read_text())
            blueprint = blueprint or {}
            base_image = blueprint.get("base-image", "")
            config.os_version = str(blueprint.get("image-version", ""))
            config.image_type = blueprint.get("image-type", "")

            desktop = blueprint.get("desktop", {})
            de = desktop.get("desktop_environment", "")
            wm = desktop.get("window_manager", "")

            if de:
                de_labels = {
                    "gnome": "GNOME",
                }
                config.wm_de_label = de_labels.get(de.lower(), de.capitalize())
            elif wm:
                config.wm_de_label = wm.capitalize()
        else:
            content = adnyeus_path.read_text()
            if match := re.search(r"^base-image:\s*(.+)$", content, re.MULTILINE):
                base_image = match.group(1).strip().strip("\"'")
            if match := re.search(r"^image-version:\s*(.+)$", content, re.MULTILINE):
                config.os_version = match.group(1).strip().strip("\"'")
            if match := re.search(r"window_manager:\s*(.+)$", content, re.MULTILINE):
                config.wm_de_label = match.group(1).strip().strip("\"'").capitalize()
    else:
        colors.warning("adnyeus.yml not found; relying on pipeline inputs")

    if base_image:
        base_lower = base_image.lower()
        os_map = {
            "fedora": ("Fedora", "fedora", "0A74DA"),
        }
        for key, (name, logo, color) in os_map.items():
            if key in base_lower:
                config.os_name, config.os_logo, config.os_badge_color = name, logo, color
                break

        if not config.os_version and ":" in base_image:
            config.os_version = base_image.rsplit(":", 1)[1].split("@")[0]

    version_file = repo_root / ".fedora-version"
    if version_file.exists() and version_file.stat().st_size > 0:
        version_info = version_file.read_text().strip()
        parts = version_info.split(":")
        config.os_version = parts[0]
        if len(parts) > 1:
            config.image_type = parts[1]

    type_displays = {
        "fedora-sway-atomic": "Fedora Sway Atomic Desktop",
        "fedora-bootc": "Fedora bootc Base",
    }
    config.image_type_display = type_displays.get(config.image_type, config.image_type or "Unknown")

    if not config.os_version:
        config.os_version = "unknown"

    if config.os_version:
        colors.info(f"Blueprint version detected: {config.os_name} {config.os_version}")

    if github_repo := os.environ.get("GITHUB_REPOSITORY"):
        config.github_repo = github_repo
    else:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_root), "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=True,
            )
            url = result.stdout.strip()
            match = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
            if match:
                config.github_repo = match.group(1).replace(".git", "")
                if "/git/" in config.github_repo:
                    config.github_repo = config.github_repo.split("/git/")[-1]
                colors.info(f"Detected GitHub repository: {config.github_repo}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            colors.warning("Could not detect GitHub repository, using default")
            config.github_repo = "borninthedark/exousia"

    config.github_owner = config.github_repo.split("/")[0]
    config.docker_image = "ghcr.io/borninthedark/exousia"
    config.build_date = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    badge_text = f"{config.os_name} {config.os_version} / {config.wm_de_label}"
    config.build_badge_text_uri = quote(badge_text)

    return config


def docs_table(root: Path) -> str:
    """Build the documentation table for the previous README layout."""
    rows = ["| Document | Description |", "|----------|-------------|"]
    for rel_path, title, desc in DOC_ENTRIES:
        if (root / rel_path).exists():
            rows.append(f"| [{title}]({rel_path}) | {desc} |")
    return "\n".join(rows)


def structure_table(root: Path) -> str:
    """Build the project structure table for the previous README layout."""
    rows = [
        "| Directory | Purpose | Docs |",
        "|-----------|---------|------|",
    ]
    for rel_path, _title, desc in SUBDIR_ENTRIES:
        dir_path = root / rel_path
        readme = dir_path / "README.md"
        if not dir_path.exists():
            continue
        if readme.exists():
            rows.append(f"| [`{rel_path}`]({rel_path}) | {desc} | [README]({rel_path}README.md) |")
        else:
            rows.append(f"| [`{rel_path}`]({rel_path}) | {desc} | -- |")
    return "\n".join(rows)


def generate_readme(config: Config) -> str:
    """Generate the complete README content."""
    root = get_repo_root()
    docs = docs_table(root)
    structure = structure_table(root)

    return f"""# Exousia - Declarative Bootc Image Builder

> *Can't Fear Your Own OS*
>
> **BLEACH** by **Tite Kubo** -- The Shinigami Pipeline,
> Reiatsu badge, and all captain naming are inspired by the Gotei 13
> from *BLEACH*. All rights belong to Tite Kubo and
> respective copyright holders.

[![Reiatsu](https://img.shields.io/github/actions/workflow/status/{REPO}/urahara.yml?branch=main&style=for-the-badge&logo=zap&logoColor=white&label=Reiatsu&color=00A4EF)](https://github.com/{REPO}/actions/workflows/urahara.yml)
[![Last Build: {config.os_name} {config.os_version} / {config.wm_de_label}](https://img.shields.io/badge/Last%20Build-{config.build_badge_text_uri}-{config.os_badge_color}?style=for-the-badge&logo={config.os_logo}&logoColor=white)](https://github.com/{REPO}/actions/workflows/urahara.yml?query=branch%3Amain+is%3Asuccess)
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
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
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
- **Transpiler** (`tools/yaml-to-containerfile.py`) -- reads the blueprint,
  loads package lists from `overlays/base/packages/`, and emits a valid
  Containerfile.
- **Overlays** -- static files, configs, and scripts organized under
  `overlays/base/` (shared) and `overlays/sway/` (desktop-specific).
- **Tests** -- Bats tests in `custom-tests/` validate the built image.

---

## CI/CD Pipeline

Every workflow is named after a captain from the Gotei 13. Each captain's
division maps to the workflow's role in the pipeline:

```mermaid
%%{{init: {{'theme': 'base', 'themeVariables': {{'primaryColor': '#1a1a2e', 'primaryTextColor': '#e0e0e0', 'primaryBorderColor': '#4fc3f7', 'lineColor': '#4fc3f7', 'secondaryColor': '#16213e', 'tertiaryColor': '#0f3460', 'edgeLabelBackground': '#1a1a2e'}}}}}}%%
graph TD
    A["Aizen<br/>(orchestrator)"] --> B["Kaname<br/>(CI: lint+test)"]
    A --> C["Gin<br/>(security scan)"]
    B --> D["Kyoraku<br/>(build, sign, release)"]
    C --> D
    D --> E["Gate"]
```

Aizen calls Kaname and Gin in parallel. When both pass, Kyoraku builds,
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

Secrets propagate to child workflows via `secrets: inherit` in Aizen.

---

## Documentation

**[Full Documentation Index](docs/README.md)**

{docs}

## Project Structure

{structure}

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
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate dynamic README.md with current build configuration"
    )
    parser.add_argument("--image-type", help="Override image type")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    colors = Colors()
    repo_root = get_repo_root()
    readme_path = repo_root / "README.md"

    colors.info("Extracting configuration from repository metadata...")
    config = extract_config(repo_root, colors)

    if args.image_type:
        config.image_type = args.image_type
        colors.info(f"Using custom image type: {config.image_type}")

    colors.info("Configuration detected:")
    print(f"  - OS: {config.os_name} {config.os_version}")
    print(f"  - Image Type: {config.image_type_display}")
    print(f"  - GitHub Repo: {config.github_repo}")
    print(f"  - Docker Image: {config.docker_image}")
    print()

    readme_content = generate_readme(config)

    if args.dry_run:
        colors.info("Dry run mode - displaying generated content:")
        print("-" * 50)
        print(readme_content)
        print("-" * 50)
        colors.warning("Dry run complete - README.md was not modified")
        return

    colors.info("Generating README.md...")
    readme_path.write_text(readme_content)
    colors.success(f"README.md generated successfully at: {readme_path}")

    if os.environ.get("CI") != "true":
        print()
        colors.info("Next steps:")
        print("  1. Review the generated README: less README.md")
        print("  2. Commit the changes: git add README.md && git commit")


if __name__ == "__main__":
    main()
