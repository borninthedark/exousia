# Fedora Bootc Custom Image

[![CI/CD Pipeline](https://github.com/borninthedark/exousia/actions/workflows/build.yaml/badge.svg)](https://github.com/borninthedark/exousia/actions/workflows/build.yaml)
[![Fedora Version](https://img.shields.io/badge/Fedora-43-51A2DA?logo=fedora)](https://fedoraproject.org)
[![bootc](https://img.shields.io/badge/bootc-enabled-success)](https://bootc-dev.github.io/bootc/)

This repository contains the configuration to build a custom, container-based immutable operating system using [**Fedora bootc**](https://docs.fedoraproject.org/en-US/bootc/). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions.

## Philosophy: Exousia

Exousia (ἐξουσία) is Greek for "authority" and "power." It specifically means the right to exercise complete control.

This project embodies that principle: a build pipeline for creating container images exactly as you specify them. No imposed defaults, no locked configurations. Full transparency and control over every package, setting, and behavior in your operating system.

Comprehensive testing ensures what you build actually works. Over 50 automated tests validate packages, configurations, services, and security across multiple base image types.

Build what you need, how you need it, with confidence.


## Current Configuration

- **Base Image:** `Fedora Sway Atomic Desktop`
- **Image Type:** `fedora-sway-atomic`
- **Fedora Version:** 43
- **Last Updated:** 2025-11-29 01:20:32 UTC

## CI/CD Workflow: Fedora Bootc DevSec CI

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire image lifecycle. The workflow is triggered on:
- Pushes and pull requests to the `main` branch
- Nightly schedule (`20 4 * * *` UTC)
- Manual workflow dispatch with version/image type selection

### 1. Build Stage

The first stage assembles the container image and prepares it for subsequent stages.

- **Lint**: The `Containerfile` is linted using **Hadolint** to ensure best practices
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

---

## Known Issues

### GHCR Authentication

Currently experiencing authentication issues with `bootc switch` and `bootc upgrade` when using GHCR. The commands work flawlessly with Docker Hub. While `skopeo inspect` and `podman pull` work with GHCR, bootc operations return "403 Forbidden | Invalid Username/Password" errors.

**Workaround:** Use Docker Hub for bootc operations until this is resolved.

---

## Documentation & Resources

### Official Documentation
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/)
- [bootc Project](https://bootc-dev.github.io/bootc/)
- [Base Images](https://docs.fedoraproject.org/en-US/bootc/base-images/)
- [Building Containers](https://docs.fedoraproject.org/en-US/bootc/building-containers/)

### Community Resources
- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)
- [bootc Issue Tracker](https://gitlab.com/fedora/bootc/tracker)

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

- The Fedora Project and bootc maintainers
- [Universal Blue](https://universal-blue.org/) for pioneering container-native desktop workflows
- [bootcrew](https://github.com/bootcrew) for community-driven bootc projects and examples
- The broader container and immutable OS community
- All contributors to the referenced documentation and guides
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### Development Notes

This project leverages AI-assisted development practices. The build pipeline, testing framework, and automation scripts were developed in collaboration with Claude and GPT Codex, demonstrating modern DevOps workflows enhanced by AI capabilities.

---

**Built with Fedora bootc**

*This README was automatically generated on 2025-11-29 01:20:32 UTC*
