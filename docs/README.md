# Exousia Documentation

Comprehensive documentation for building, testing, and deploying custom bootc images.

## Quick Links

| Topic | Description |
|-------|-------------|
| [Getting Started](BOOTC_UPGRADE.md) | Switch to and upgrade Exousia images |
| [Webhook API](WEBHOOK_API.md) | Trigger builds programmatically |
| [Testing Guide](testing/README.md) | Run and write tests |
| [API Reference](api/README.md) | FastAPI backend documentation |

---

## Build & Release

### Multi-Environment Strategy

Exousia uses three environments with semantic versioning:

| Branch | Environment | Version | Purpose |
|--------|-------------|---------|---------|
| `develop` | DEV | `vX.Y.Z-dev.N` | Active development |
| `uat` | UAT | `vX.Y.Z-rc.N` | User acceptance testing |
| `main` | PROD | `vX.Y.Z` | Production releases |

**Promotion:** `develop` → `uat` → `main`

Version bumps are automatic via [conventional commits](https://www.conventionalcommits.org/):
- `feat:` → minor
- `fix:` → patch
- `feat!:` → major

### Workflows

| Workflow | File | Purpose |
|----------|------|---------|
| Build Pipeline | `build.yml` | Lint, build, test, scan, push, sign |
| Release | `release.yml` | Create GitHub releases with changelogs |
| Manual Release | `release-manual.yml` | Emergency/manual version releases |

---

## Core Documentation

### Getting Started
- **[BOOTC_UPGRADE.md](BOOTC_UPGRADE.md)** — Switch images and perform upgrades
- **[BOOTC_IMAGE_BUILDER.md](BOOTC_IMAGE_BUILDER.md)** — Build bootable disk images (ISO, raw, qcow2)

### API & Automation
- **[api/README.md](api/README.md)** — FastAPI overview and architecture
- **[api/endpoints.md](api/endpoints.md)** — Endpoint reference
- **[api/development.md](api/development.md)** — Local development setup
- **[WEBHOOK_API.md](WEBHOOK_API.md)** — GitHub webhook triggers

### Testing
- **[testing/README.md](testing/README.md)** — Test suite overview
- **[testing/guide.md](testing/guide.md)** — Detailed test architecture
- **[reference/writing-tests.md](reference/writing-tests.md)** — How to write new tests

### Reference
- **[reference/troubleshooting.md](reference/troubleshooting.md)** — Common issues and fixes
- **[reference/plymouth_usage_doc.md](reference/plymouth_usage_doc.md)** — Plymouth boot splash

---

## Feature Documentation

### Desktop & Display
- **[sway-session-greetd.md](sway-session-greetd.md)** — Sway session with greetd

### Kubernetes
- **[RKE2_INTEGRATION.md](RKE2_INTEGRATION.md)** — RKE2 Kubernetes integration
- **[RKE2_BOOTC_SETUP.md](RKE2_BOOTC_SETUP.md)** — Full RKE2 setup guide
- **[../k8s/rke2/QUICKSTART.md](../k8s/rke2/QUICKSTART.md)** — RKE2 quickstart

### Configuration
- **[CHEZMOI_INTEGRATION.md](CHEZMOI_INTEGRATION.md)** — Dotfile management with chezmoi
- **[KERNEL_OPTIONS.md](KERNEL_OPTIONS.md)** — Kernel boot parameters
- **[FLATPAK_VERIFICATION.md](FLATPAK_VERIFICATION.md)** — Flatpak app verification

### Architecture
- **[security-boundaries.md](security-boundaries.md)** — Security model and boundaries
- **[IMMUTABILITY_IDEMPOTENCY.md](IMMUTABILITY_IDEMPOTENCY.md)** — Immutable OS concepts

---

## Directory Structure

```
docs/
├── README.md              ← You are here
├── api/                   # API documentation
│   ├── README.md          # API overview
│   ├── endpoints.md       # Endpoint reference
│   └── development.md     # Development guide
├── testing/               # Testing documentation
│   ├── README.md          # Test suite overview
│   ├── guide.md           # Detailed guide
│   └── test_suite.md      # Test categories
├── reference/             # Reference materials
│   ├── troubleshooting.md
│   ├── plymouth_usage_doc.md
│   └── writing-tests.md
└── *.md                   # Feature-specific docs
```

---

## External Resources

- [bootc Project](https://github.com/bootc-dev/bootc) | [Docs](https://bootc-dev.github.io/bootc/)
- [Fedora bootc](https://docs.fedoraproject.org/en-US/bootc/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Bats Testing](https://bats-core.readthedocs.io/)

---

**[← Back to Main README](../README.md)**
