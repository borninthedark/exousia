# Exousia Documentation

Comprehensive documentation for building, testing, and deploying custom Fedora bootc images.

## Contents

- [CI/CD Workflows](#cicd-workflows)
- [Required Secrets and Variables](#required-secrets-and-variables)
- [Getting Started](#getting-started)
- [Desktop and Session](#desktop-and-session)
- [Configuration](#configuration)
- [Testing](#testing)
- [Infrastructure](#infrastructure)
- [Reference](#reference)

---

## CI/CD Workflows

Exousia uses a Phoenician-pantheon-themed GitHub Actions pipeline:

| Workflow | File | Role |
|----------|------|------|
| **El** | `el.yml` | Orchestrator -- calls Anat + Resheph in parallel, then Kothar, then gate |
| **Anat** | `anat.yml` | CI -- Hadolint, Ruff, Black, isort, pytest + Codecov |
| **Resheph** | `resheph.yml` | Security -- Checkov, Trivy config scan, Bandit |
| **Kothar** | `kothar.yml` | Build -- resolve config, buildah build, DockerHub push, Trivy image scan, Cosign |
| **Eshmun** | `eshmun.yml` | Release -- semver from conventional commits, retag, GitHub Release |

Version bumps are automatic via [conventional commits](https://www.conventionalcommits.org/):
`feat:` minor, `fix:` patch, `feat!:` major.

---

## Required Secrets and Variables

Configure in GitHub repository settings under **Settings > Secrets and variables > Actions**.

**Secrets:**

| Name | Purpose |
|------|---------|
| `DOCKERHUB_TOKEN` | DockerHub access token (used by Kothar and Eshmun) |

**Variables:**

| Name | Purpose | Required |
|------|---------|----------|
| `DOCKERHUB_USERNAME` | DockerHub username | Yes |
| `DOCKERHUB_IMAGE` | Image path (e.g., `user/exousia`) | Yes |
| `REGISTRY_URL` | Registry URL (defaults to `docker.io`) | No |

Secrets are passed to reusable workflows via `secrets: inherit` in El.

---

## Getting Started

- **[BOOTC_UPGRADE.md](BOOTC_UPGRADE.md)** -- Switch images and perform upgrades
- **[BOOTC_IMAGE_BUILDER.md](BOOTC_IMAGE_BUILDER.md)** -- Build bootable disk images (ISO, raw, qcow2)

## Desktop and Session

- **[sway-session-greetd.md](sway-session-greetd.md)** -- Sway session with greetd login manager
- **[FLATPAK_VERIFICATION.md](FLATPAK_VERIFICATION.md)** -- Flatpak application verification

## Configuration

- **[CHEZMOI_INTEGRATION.md](CHEZMOI_INTEGRATION.md)** -- Dotfile management with chezmoi
- **[KERNEL_OPTIONS.md](KERNEL_OPTIONS.md)** -- Kernel boot parameters and overrides
- **[ZFS_BOOTC.md](ZFS_BOOTC.md)** -- ZFS kernel module build process (optional)

## Testing

- **[testing/README.md](testing/README.md)** -- Test suite overview
- **[testing/guide.md](testing/guide.md)** -- Detailed test architecture
- **[testing/test_suite.md](testing/test_suite.md)** -- Test categories and expected output
- **[reference/writing-tests.md](reference/writing-tests.md)** -- How to write new tests

## Infrastructure

- **[ansible.md](ansible.md)** -- Ansible playbooks for post-deployment configuration
- **[WEBHOOK_API.md](WEBHOOK_API.md)** -- Trigger builds programmatically via repository_dispatch
- **[security-boundaries.md](security-boundaries.md)** -- Security model and boundaries

## Reference

- **[reference/troubleshooting.md](reference/troubleshooting.md)** -- Common issues and fixes
- **[reference/plymouth_usage_doc.md](reference/plymouth_usage_doc.md)** -- Plymouth boot splash setup

---

## Directory Structure

```text
docs/
├── README.md                   <- You are here
├── testing/                    # Test documentation
│   ├── README.md
│   ├── guide.md
│   └── test_suite.md
├── reference/                  # Reference materials
│   ├── troubleshooting.md
│   ├── plymouth_usage_doc.md
│   └── writing-tests.md
└── *.md                        # Feature and topic docs
```

---

## External Resources

- [bootc Project](https://github.com/bootc-dev/bootc) | [Docs](https://bootc-dev.github.io/bootc/)
- [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Bats Testing](https://bats-core.readthedocs.io/)

---

**[Back to Main README](../README.md)**
