# Fedora Bootc Custom Image

[![CI/CD Pipeline](https://github.com/borninthedark/exousia/actions/workflows/build.yaml/badge.svg)](https://github.com/borninthedark/exousia/actions/workflows/build.yaml)
[![Fedora Version](https://img.shields.io/badge/Fedora-43-51A2DA?logo=fedora)](https://fedoraproject.org)
[![bootc](https://img.shields.io/badge/bootc-enabled-success)](https://bootc-dev.github.io/bootc/)

This repository contains the configuration to build a custom, container-based immutable operating system using [**Fedora bootc**](https://docs.fedoraproject.org/en-US/bootc/). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions.

## Philosophy: Exousia

Exousia (ἐξουσία) is Greek for "authority" and "power."

This is a personal project for building my own DevSecOps-hardened laptop OS using Fedora bootc. Still under development, but the goal is full control and transparency over packages, settings, and behaviors.

The build pipeline supports both bootc and atomic base images, each with their own defaults and configurations. Automated tests help ensure things actually work as development progresses.


## Current Configuration

- **Base Image:** `Fedora Sway Atomic Desktop`
- **Image Type:** `fedora-sway-atomic`
- **Fedora Version:** 43
- **Plymouth Customization:** ⚠️ Not available (atomic base uses built-in Plymouth config)
- **Greetd Display Manager:** ❌ Not available
- **Last Updated:** 2025-11-29 04:48:21 UTC

> **Note:** Custom Plymouth themes from `custom-configs/plymouth/` are only applied when using `fedora-bootc` as the base image type. The `fedora-sway-atomic` base image uses its pre-configured Plymouth setup and ignores custom themes.

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

## YAML-Based Configuration

Exousia uses a **declarative YAML configuration** inspired by [BlueBuild](https://blue-build.org/) to define the entire image build process. This approach provides several advantages over traditional Containerfiles:

- **Declarative** - Define what you want, not how to build it
- **Validation** - Catch errors before build time
- **Type Safety** - Structured configuration with clear schemas
- **Modularity** - Reusable, composable build steps
- **Readability** - YAML is easier to understand than Dockerfile syntax

### How It Works

```
exousia.yml → [yaml-to-containerfile.py] → Containerfile.generated → [buildah] → Image
```

1. **Edit `exousia.yml`** - Define your image configuration
2. **Transpilation** - Python script converts YAML to Containerfile
3. **Build** - CI pipeline builds the generated Containerfile
4. **Publish** - Image is pushed to registries

The transpilation happens automatically in the CI pipeline, so you only need to edit the YAML file.

### Quick Start

#### Adding Packages

Edit `exousia.yml` and add packages to the `rpm-ostree` module:

```yaml
modules:
  - type: rpm-ostree
    install:
      - your-package
      - another-package
```

#### Adding Configuration Files

Add files using the `files` module:

```yaml
modules:
  - type: files
    files:
      - src: custom-configs/your-config
        dst: /etc/your-config
        mode: "0644"
```

#### Running Custom Scripts

Execute shell commands with the `script` module:

```yaml
modules:
  - type: script
    scripts:
      - |
        mkdir -p /var/lib/example
        systemctl enable example.service
```

### Local Testing

Validate your YAML configuration before committing:

```bash
# Validate YAML syntax and structure
python3 tools/yaml-to-containerfile.py --config exousia.yml --validate

# Generate Containerfile to preview
python3 tools/yaml-to-containerfile.py \
  --config exousia.yml \
  --image-type fedora-sway-atomic \
  --output Containerfile.test

# Test build locally
buildah build -f Containerfile.test -t exousia:test .
```

For detailed documentation on the YAML transpiler, see [`tools/README.md`](tools/README.md).

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
- `custom-configs/plymouth/` - Boot splash configuration (**fedora-bootc only**)

### Plymouth Boot Splash Configuration

**⚠️ IMPORTANT: Custom Plymouth themes only work with `fedora-bootc` base images.**

The Plymouth boot splash configuration depends on your base image type:

| Base Image Type | Plymouth Support | Details |
|-----------------|------------------|---------|
| `fedora-bootc` | ✅ Custom themes supported | Uses `custom-configs/plymouth/themes/bgrt-better-luks/` |
| `fedora-sway-atomic` | ⚠️ Built-in only | Uses pre-configured Plymouth from upstream, custom themes ignored |

**To use custom Plymouth themes:**

1. Switch to `fedora-bootc` base image:
   ```bash
   ./custom-scripts/fedora-version-switcher 43 fedora-bootc
   ```

2. Ensure Plymouth is enabled in workflow dispatch (enabled by default for fedora-bootc)

3. Your custom theme in `custom-configs/plymouth/themes/bgrt-better-luks/` will be applied

**Note:** The `enable_plymouth` workflow input only affects `fedora-bootc` builds. It has no effect on `fedora-sway-atomic` builds, which always use the upstream Plymouth configuration.

### Greetd Display Manager

**⚠️ IMPORTANT: The greetd display manager is only available for `fedora-bootc` base images.**

The greetd display manager availability depends on your base image type:

| Base Image Type | Greetd Support | Details |
|-----------------|----------------|---------|
| `fedora-bootc` | ✅ Available | greetd.service enabled, custom config in `custom-configs/greetd/` |
| `fedora-sway-atomic` | ❌ Not available | Uses SDDM display manager instead |

**Note:** The `fedora-sway-atomic` image uses SDDM (Simple Desktop Display Manager) by default. If you need greetd for a custom login screen, switch to the `fedora-bootc` base image using:

```bash
./custom-scripts/fedora-version-switcher 43 fedora-bootc
```

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

## Documentation

This repository includes comprehensive documentation for building, testing, and managing your bootc image:

### Core Documentation

- **[BOOTC_IMAGE_BUILDER.md](docs/BOOTC_IMAGE_BUILDER.md)** - Build bootable disk images for local testing with bootc-image-builder
- **[BOOTC_UPGRADE.md](docs/BOOTC_UPGRADE.md)** - Complete guide to upgrading, switching, and rolling back bootc deployments
- **[TESTING.md](docs/TESTING.md)** - Comprehensive test suite documentation with 52+ automated tests

### Testing Documentation

- **[Testing Guide](docs/testing/guide.md)** - In-depth testing architecture, test categories, and best practices
- **[Testing README](docs/testing/README.md)** - Quick start guide for running the test suite
- **[Test Suite Details](docs/testing/test_suite.md)** - Detailed test suite information

### API Documentation

- **[API Overview](docs/api/README.md)** - FastAPI backend architecture, features, and quick start
- **[API Endpoints](docs/api/endpoints.md)** - Complete REST API reference with examples
- **[API Development](docs/api/development.md)** - Contributing guide for API development

### Reference Documentation

- **[Plymouth Usage](docs/reference/plymouth_usage_doc.md)** - Configure and customize the boot splash screen
- **[Troubleshooting](docs/reference/troubleshooting.md)** - Common issues and solutions
- **[Writing Tests](docs/reference/writing-tests.md)** - Guide for contributing new tests

---

## External Resources

### Official Documentation
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/)
- [bootc Project](https://bootc-dev.github.io/bootc/)
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

- The Fedora Project and bootc maintainers
- [Universal Blue](https://universal-blue.org/) for pioneering container-native desktop workflows
- [BlueBuild](https://blue-build.org/) for the declarative YAML specification that inspired our build system
- [bootcrew](https://github.com/bootcrew) for community-driven bootc projects and examples
- The broader container and immutable OS community
- All contributors to the referenced documentation and guides
- **Claude** (Anthropic) and **GPT Codex** (OpenAI) for AI-assisted development

### Development Notes

This project leverages AI-assisted development practices. The build pipeline, testing framework, and automation scripts were developed in collaboration with Claude and GPT Codex, demonstrating modern DevOps workflows enhanced by AI capabilities.

---

**Built with Fedora bootc**

*This README was automatically generated on 2025-11-29 04:48:21 UTC*
