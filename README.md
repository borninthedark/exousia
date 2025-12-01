# Exousia: Declarative Bootc Builder

[![CI/CD Pipeline](https://github.com/borninthedark/exousia/actions/workflows/build.yaml/badge.svg)](https://github.com/borninthedark/exousia/actions/workflows/build.yaml)
[![GHCR Image](https://img.shields.io/badge/GHCR-ghcr.io/borninthedark/exousia-blue?logo=github)](https://ghcr.io/borninthedark/exousia)
[![Docker Hub Image](https://img.shields.io/docker/pulls/1borninthedark/exousia?logo=docker)](https://hub.docker.com/r/1borninthedark/exousia)
[![Fedora Version](https://img.shields.io/badge/Fedora-43-51A2DA?logo=fedora)](https://fedoraproject.org)
[![bootc](https://img.shields.io/badge/bootc-enabled-success)](https://bootc-dev.github.io/bootc/)

This repository contains the configuration to build a custom, container-based immutable operating system using the upstream [**bootc project**](https://github.com/bootc-dev/bootc). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions. Fedora's [bootc documentation](https://docs.fedoraproject.org/en-US/bootc/) remains an authoritative, distro-specific reference alongside the upstream project docs.

## Philosophy: Exousia

Exousia (ἐξουσία) is Greek for "authority" and "power."

This is a personal project for building my own DevSecOps-hardened laptop OS using the bootc project. Still under development, but the goal is full control and transparency over packages, settings, and behaviors.

The build pipeline supports both bootc and atomic base images, each with their own defaults and configurations. Automated tests help ensure things actually work as development progresses.


## Current Configuration

- **Base Image:** `Fedora Sway Atomic Desktop`
- **Image Type:** `fedora-sway-atomic`
- **Fedora Version:** 43
- **Plymouth Customization:** ✅ Available (custom themes supported on all base images)
- **Greetd Display Manager:** ❌ Not available
- **Last Updated:** 2025-12-01 00:57:47 UTC

> **Note:** Custom Plymouth themes from `custom-configs/plymouth/` are applied for both `fedora-bootc` and `fedora-sway-atomic` base image types.

## CI/CD Workflow: Fedora Bootc DevSec CI

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire image lifecycle. The workflow is triggered on:
- Pushes and pull requests to the `main` branch
- Nightly schedule (`20 4 * * *` UTC)
- Manual workflow dispatch with version/image type selection
- Webhook-triggered `repository_dispatch` events of type `api`

### 1. Build Stage

The first stage assembles the container image and prepares it for subsequent stages.

- **Lint**: Generated container definitions are linted using **Hadolint** to ensure best practices
- **Tagging**: Image tags are dynamically generated based on event triggers (`latest`, `nightly`, branch name, commit SHA)
- **Build**: The image is built using **Buildah**, a daemonless container image builder optimized for CI environments
- **Version Switching**: Supports dynamic Fedora version and base image type switching via workflow dispatch

### 2. Test Stage

After a successful build, the image and repository scripts undergo automated testing.

- **Integration Tests**: **Bats (Bash Automated Testing System)** runs tests against the built container
- **Script Analysis**: All shell scripts are linted with **ShellCheck**
- **Bootc Validation**: Runs `bootc container lint` to verify bootc compliance

### 3. Scan Stage

Security scanning ensures the image meets security standards.

- **Vulnerability Scan**: **Trivy** scans for `CRITICAL` and `HIGH` severity CVEs
- **Static Analysis**: **Semgrep** performs static code analysis

### 4. Push & Sign Stage

If tests pass and the event is not a pull request, the image is published and cryptographically signed.

- **Push**: Image pushed to **GitHub Container Registry (GHCR)** and **Docker Hub**
- **Sign**: Images signed using **Cosign** and **Sigstore** for integrity verification

---

## Getting Started

### Prerequisites

- A system running Fedora (preferably an Atomic variant)
- Access to either Docker Hub or GHCR
- Basic understanding of bootc and container workflows

### Using the Pre-built Image

#### From Docker Hub (Recommended)

```bash
# Switch to the custom bootc image
sudo bootc switch docker.io/borninthedark/exousia:latest

# Apply the update
sudo bootc upgrade
sudo systemctl reboot
```

#### From GitHub Container Registry

```bash
# Switch to the custom bootc image
sudo bootc switch ghcr.io/borninthedark/exousia:latest

# Apply the update
sudo bootc upgrade
sudo systemctl reboot
```

### Building Locally

```bash
# Clone the repository
git clone https://github.com/borninthedark/exousia.git
cd $(basename borninthedark/exousia)

# Build the image
make build

# Push to local registry (optional)
make push
```

---

## Customization

### Switching Fedora Versions

Use the version switcher script to change Fedora versions or base image types:

```bash
# Switch to Fedora 43
./custom-scripts/fedora-version-switcher 43

# Switch to Fedora 42 with standard bootc base
./custom-scripts/fedora-version-switcher 42 fedora-bootc

# Switch to Sway Atomic desktop
./custom-scripts/fedora-version-switcher 42 fedora-sway-atomic

# List available options
./custom-scripts/fedora-version-switcher list
```

Or use GitHub Actions workflow dispatch:

1. Go to **Actions** → **Fedora Bootc DevSec CI**
2. Click **Run workflow**
3. Select desired Fedora version and image type
4. Click **Run workflow**

The README will automatically update to reflect the new configuration.

### Modifying Packages

Edit the package lists in `custom-pkgs/`:

- `packages.add` - Packages to install
- `packages.remove` - Packages to remove from base image

### Adding Custom Configuration

Place configuration files in the appropriate `custom-configs/` subdirectories:

- `custom-configs/sway/` - Sway window manager configuration
- `custom-configs/greetd/` - Display manager configuration
- `custom-configs/plymouth/` - Boot splash configuration

### Plymouth Boot Splash Configuration

The Plymouth boot splash configuration is toggleable on both base image types via the `enable_plymouth` flag:

| Base Image Type | Plymouth Support | Details |
|-----------------|------------------|---------|
| `fedora-bootc` | ✅ Custom themes supported | Uses `custom-configs/plymouth/themes/bgrt-better-luks/` and bootc kargs when enabled |
| `fedora-sway-atomic` | ✅ Custom themes supported | Uses `custom-configs/plymouth/themes/bgrt-better-luks/` when enabled |

**To use custom Plymouth themes:**

1. Set `enable_plymouth: true` in your BlueBuild YAML (default in provided configs).
2. Place your theme in `custom-configs/plymouth/themes/bgrt-better-luks/`.
3. Build either `fedora-bootc` or `fedora-sway-atomic` variants to apply the theme.

### Greetd Display Manager

**⚠️ IMPORTANT: The greetd display manager is only available for `fedora-bootc` base images.**

The greetd display manager availability depends on your base image type:

| Base Image Type | Greetd Support | Details |
|-----------------|----------------|---------|
| `fedora-bootc` | ✅ Available | greetd.service enabled, custom config in `custom-configs/greetd/` |
| `fedora-sway-atomic` | ❌ Not available | Uses SDDM display manager instead |

**Note:** The `fedora-sway-atomic` image uses SDDM (Simple Desktop Display Manager) by default. Switch to `fedora-bootc` if you need greetd.

**To use greetd display manager:**

1. Switch to `fedora-bootc` base image:
   \`\`\`bash
   ./custom-scripts/fedora-version-switcher 43 fedora-bootc
   \`\`\`

2. Customize the greetd configuration in `custom-configs/greetd/config.toml` as needed

### Custom Scripts

Add executable scripts to `custom-scripts/` - they will be copied to `/usr/local/bin/`

---

## Required Secrets

To use the full CI/CD pipeline, configure these secrets in your repository:

**Settings → Secrets and variables → Actions**

### For GitHub Container Registry (GHCR):
- `GHCR_PAT`: Personal Access Token with `write:packages` scope

### For Docker Hub:
- `DOCKERHUB_USERNAME`: Your Docker Hub username
- `DOCKERHUB_TOKEN`: Access token with Read, Write, Delete permissions

### For Code Coverage (Codecov):
- `CODECOV_TOKEN`: Repository upload token from [codecov.io](https://codecov.io)
  1. Sign up at https://codecov.io with your GitHub account
  2. Add your repository to Codecov
  3. Copy the repository upload token
  4. Add as `CODECOV_TOKEN` secret in GitHub Actions

**Benefits:**
- Detailed coverage reports with branch coverage tracking
- PR comments showing coverage changes
- Coverage trend visualization
- Integration with GitHub checks

---

## Known Issues

### GHCR Authentication

Currently experiencing authentication issues with `bootc switch` and `bootc upgrade` when using GHCR. The commands work flawlessly with Docker Hub. While `skopeo inspect` and `podman pull` work with GHCR, bootc operations return "403 Forbidden | Invalid Username/Password" errors.

**Workaround:** Use Docker Hub for bootc operations until this is resolved.

---

## Documentation

Comprehensive documentation organized by use case:

### Getting Started

New to Exousia? Start here:
- **[BOOTC_UPGRADE.md](docs/BOOTC_UPGRADE.md)** - Complete guide to using, upgrading, and switching bootc images
- **[BOOTC_IMAGE_BUILDER.md](docs/BOOTC_IMAGE_BUILDER.md)** - Build bootable disk images for local testing

### API Documentation

Use the REST API and webhooks to manage configurations programmatically:
- **[Webhook API](docs/WEBHOOK_API.md)** - Trigger builds remotely via GitHub webhooks
- **[API Overview](docs/api/README.md)** - FastAPI backend architecture and features
- **[API Endpoints](docs/api/endpoints.md)** - Complete endpoint reference with examples
- **[Development Guide](docs/api/development.md)** - Contributing to the API

The API and webhook system enable:
- YAML configuration validation and storage
- Dynamic Containerfile transpilation
- GitHub Actions build triggering via webhooks
- Remote build automation and integration
- Build status tracking

### Building & Customization

Customize and build your own images:
- **[TESTING.md](docs/TESTING.md)** - Run the 52+ automated test suite before building

### Testing & Quality

For contributors and developers:
- **[Testing Guide](docs/testing/guide.md)** - In-depth testing architecture and best practices
- **[Testing README](docs/testing/README.md)** - Quick start for running tests
- **[Test Suite Details](docs/testing/test_suite.md)** - Detailed test documentation
- **[Writing Tests](docs/reference/writing-tests.md)** - Guide for contributing new tests

### Reference

Detailed guides and troubleshooting:
- **[Plymouth Usage](docs/reference/plymouth_usage_doc.md)** - Configure boot splash screens
- **[Troubleshooting](docs/reference/troubleshooting.md)** - Common issues and solutions

---

## External Resources

### Official Documentation
- [bootc Project](https://github.com/bootc-dev/bootc)
- [bootc Documentation](https://bootc-dev.github.io/bootc/)
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/) _(secondary Fedora-focused guidance)_
- [Base Images](https://docs.fedoraproject.org/en-US/bootc/base-images/)
- [Building Containers](https://docs.fedoraproject.org/en-US/bootc/building-containers/)

### Community Resources
- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)
- [bootc Issue Tracker](https://gitlab.com/fedora/bootc/tracker)
- [BlueBuild](https://blue-build.org/) - Declarative image builder for bootc
- [BlueBuild Module Reference](https://blue-build.org/reference/module/)

### Articles & Guides
- [Getting Started With Bootc](https://docs.fedoraproject.org/en-US/bootc/getting-started/)
- [How to rebase to Fedora Silverblue 43 Beta](https://fedoramagazine.org/how-to-rebase-to-fedora-silverblue-43-beta/)
- [A Great Journey Towards Fedora CoreOS and Bootc](https://fedoramagazine.org/a-great-journey-towards-fedora-coreos-and-bootc/)
- [Building Your Own Atomic Bootc Desktop](https://fedoramagazine.org/building-your-own-atomic-bootc-desktop/)

### Technical References
- [Bootupd RPM dependency workaround](https://github.com/coreos/bootupd/issues/468)
- [Unification of boot loader updates](https://gitlab.com/fedora/bootc/tracker/-/issues/61)
- [Add Plymouth to Fedora-Bootc](https://www.reddit.com/r/Fedora/comments/1nq636t/comment/ngbgfkh/)

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- The bootc project maintainers and the Fedora community
- [Universal Blue](https://universal-blue.org/) for pioneering container-native desktop workflows
- [BlueBuild](https://blue-build.org/) for the declarative YAML specification that inspired my build system
- [bootcrew](https://github.com/bootcrew) for community-driven bootc projects and examples
- [Buildah](https://buildah.io/), [Skopeo](https://github.com/containers/skopeo), and [Podman](https://podman.io/) communities
  for advancing daemonless container tooling
- The broader container and immutable OS community
- All contributors to the referenced documentation and guides
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### Development Notes

This project leverages AI-assisted development practices. The build pipeline, testing framework, and automation scripts were developed in collaboration with Claude and GPT Codex, demonstrating modern DevOps workflows enhanced by AI capabilities.

---

**Built with bootc**

*This README was automatically generated on 2025-12-01 00:57:47 UTC*
