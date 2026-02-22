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
- [Infrastructure](#infrastructure)
- [Reference](#reference)

---

## CI/CD Workflows

Exousia uses a Shinigami-themed GitHub Actions pipeline (Gotei 13 captains):

| Workflow | File | Role |
|----------|------|------|
| **Aizen** | `aizen.yml` | Orchestrator -- calls Kaname + Gin in parallel, then Kyoraku, then gate |
| **Kaname** | `kaname.yml` | CI -- Ruff, Black, isort, pytest |
| **Gin** | `gin.yml` | Security -- Hadolint, Checkov, Trivy config scan, Bandit |
| **Kyoraku** | `kyoraku.yml` | Docker Buildx, Cosign, Trivy scan, semver release |
| **Yoruichi** | `yoruichi.yml` | Post-CI -- STATUS.md, badge updates |

Version bumps are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` minor, `fix:` patch, `feat!:` major.

---

## Required Secrets and Variables

Configure in GitHub repository settings under **Settings > Secrets and variables > Actions**.

**Secrets:**

| Name | Purpose |
|------|---------|
| `DOCKERHUB_TOKEN` | DockerHub access token |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `DOCKERHUB_USERNAME` | DockerHub username | Yes |
| `REGISTRY_URL` | Registry URL (defaults to `docker.io`) | No |

Secrets are passed to reusable workflows via `secrets: inherit` in Aizen.

---

## Getting Started

- **[bootc-upgrade.md](bootc-upgrade.md)** -- Switch images and perform upgrades
- **[bootc-image-builder.md](bootc-image-builder.md)** -- Build bootable disk images (ISO, raw, qcow2)
- **[distros.md](distros.md)** -- Supported distributions and image variants

## Desktop and Session

- **[sway-session-greetd.md](sway-session-greetd.md)** -- Sway session with greetd login manager
- **[flatpak-verification.md](flatpak-verification.md)** -- Flatpak application verification

## Configuration

- **[chezmoi-integration.md](chezmoi-integration.md)** -- Dotfile management with chezmoi
- **[kernel-options.md](kernel-options.md)** -- Kernel boot parameters and overrides

## Testing

- **[testing/README.md](testing/README.md)** -- Test suite overview
- **[testing/guide.md](testing/guide.md)** -- Detailed test architecture
- **[testing/test-suite.md](testing/test-suite.md)** -- Test categories and expected output
- **[reference/writing-tests.md](reference/writing-tests.md)** -- How to write new tests

## Architecture

- **[overlay-system.md](overlay-system.md)** -- Overlay directory structure and how files map into images
- **[local-build-pipeline.md](local-build-pipeline.md)** -- Quadlet services, local build, and promotion to DockerHub

## Infrastructure

- **[ansible.md](ansible.md)** -- Ansible playbooks for post-deployment configuration
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
