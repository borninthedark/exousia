# Exousia Documentation

Comprehensive documentation for building, testing, and deploying custom Fedora bootc images.

## Contents

- [CI/CD Workflows](#cicd-workflows)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Getting Started](#getting-started)
- [Desktop and Session](#desktop-and-session)
- [Configuration](#configuration)
- [Testing](#testing)
- [Architecture](#architecture)
- [Reference](#reference)

---

## CI/CD Workflows

Exousia uses a 12th Division-themed GitHub Actions pipeline (Shinigami Research and Development Institute):

| Workflow | File | Role |
|----------|------|------|
| **Urahara** | `urahara.yml` | 12th -- Orchestrator: calls Hikifune + Uhin in parallel, then Hiyori, then gate |
| **Hikifune** | `hikifune.yml` | 12th -- CI: Ruff, Black, isort, pytest |
| **Uhin** | `uhin.yml` | 12th -- Security: Hadolint, Checkov, Trivy config scan, Bandit |
| **Hiyori** | `hiyori.yml` | 12th -- Build, Trivy scan, SBOM submission, Cosign, semver release |
| **Nemu** | `nemu.yml` | 12th -- Post-CI: STATUS.md |
| **Mayuri** | `mayuri.yml` | 12th -- Dotfiles watcher: polls `borninthedark/dotfiles`, triggers Urahara on change |

Version bumps are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` minor, `fix:` patch, `feat!:` major.

---

## Required Secrets and Variables

Configure in GitHub repository settings under **Settings > Secrets and variables > Actions**.

**Secrets:**

| Name | Purpose |
|------|---------|
| `GHCR_PAT` | GHCR personal access token for CI RPM override pulls and local/manual registry access |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `REGISTRY_URL` | Registry URL (defaults to `ghcr.io`) | No |

Secrets are passed to reusable workflows via `secrets: inherit` in Urahara.

---

## Getting Started

- **[bootc-upgrade.md](bootc-upgrade.md)** -- Switch images and perform upgrades
- **[bootc-image-builder.md](bootc-image-builder.md)** -- Build bootable disk images (ISO, raw, qcow2)
- **[distros.md](distros.md)** -- Supported distributions and image variants

## Desktop and Session

- **[sway-session-greetd.md](sway-session-greetd.md)** -- Sway session with greetd login manager
- **[flatpak-verification.md](flatpak-verification.md)** -- Flatpak application verification

## Configuration

- **[modules.md](modules.md)** -- Build module types, fields, and usage reference
- **[chezmoi-integration.md](chezmoi-integration.md)** -- Dotfile management with chezmoi
- **[package-loader-cli.md](package-loader-cli.md)** -- Resolve package sets, inspect provenance, and export legacy manifests
- **[cve-remediation.md](cve-remediation.md)** -- Trivy findings, active remediations, and RPM override workflow

## Testing

- **[testing/README.md](testing/README.md)** -- Test suite overview
- **[testing/guide.md](testing/guide.md)** -- Canonical test architecture and workflow guide
- **[testing/test-suite.md](testing/test-suite.md)** -- Compact test category and command reference
- **[reference/writing-tests.md](reference/writing-tests.md)** -- How to write new tests

## Architecture

- **[overlay-system.md](overlay-system.md)** -- Overlay directory structure and how files map into images
- **[package-management-and-container-builds.md](package-management-and-container-builds.md)** -- Typed package-set model and resolved build-plan direction
- **[local-build-pipeline.md](local-build-pipeline.md)** -- Quadlet services, local build, GHCR publication, and local registry mirroring

- **[security-boundaries.md](security-boundaries.md)** -- Security model and boundaries

## Reference

- **[reference/troubleshooting.md](reference/troubleshooting.md)** -- Common issues and fixes
- **[reference/plymouth-usage.md](reference/plymouth-usage.md)** -- Plymouth boot splash setup

---

## Directory Structure

```text
docs/
├── README.md                       <- You are here
├── local-build-pipeline.md         # Quadlet services and local build workflow
├── overlay-system.md               # Overlay directory structure
├── testing/                        # Test documentation
│   ├── README.md
│   ├── guide.md
│   └── test-suite.md
├── reference/                      # Reference materials
│   ├── troubleshooting.md
│   ├── plymouth-usage.md
│   └── writing-tests.md
└── *.md                            # Feature and topic docs
```

---

## External Resources

- [bootc Project](https://github.com/bootc-dev/bootc) | [Docs](https://bootc-dev.github.io/bootc/)
- [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Bats Testing](https://bats-core.readthedocs.io/)

---

**[Back to Main README](../README.md)**
