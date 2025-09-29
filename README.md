# Fedora Sway Atomic (`bootc`) Image

[![CI/CD Pipeline](https://github.com/borninthedark/exousia/actions/workflows/build.yaml/badge.svg)](https://github.com/borninthedark/exousia/actions/workflows/build.yaml)
[![Fedora 42](https://img.shields.io/badge/Fedora-42-51A2DA?logo=fedora)](https://fedoraproject.org)
[![bootc](https://img.shields.io/badge/bootc-enabled-success)](https://bootc-dev.github.io/bootc/)

This repository contains the configuration to build a custom, container-based immutable version of **Fedora Sway (Sericea)** using [`bootc`](https://github.com/containers/bootc). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions.

## CI/CD Workflow: `Sericea DevSec CI`

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire image lifecycle. The workflow is triggered on pushes and pull requests to the `main` branch, on a nightly schedule (`20 4 * * *`), or by manual dispatch.

### 1. Build Stage 🏗️

The first stage assembles the container image and prepares it for the subsequent stages.

* **Lint**: The `Containerfile` is first linted using **Hadolint** to ensure it follows best practices.
* **Tagging**: Image tags are dynamically generated for both registries based on the event trigger (e.g., `latest`, `nightly`, branch name, and commit SHA).
* **Build**: The image is built using **Buildah**, a daemonless container image builder well-suited for CI environments.

---

### 2. Test Stage 🧪

After a successful build, the image and repository scripts undergo automated testing to ensure quality and correctness.

* **Integration Tests**: The **Bats (Bash Automated Testing System)** framework runs tests against the built container to verify its configuration and functionality.
* **Script Analysis**: All shell scripts in the repository are linted with **ShellCheck** to catch common scripting errors.

---

### 3. Scan Stage 🛡️

Security is a critical part of the pipeline. The built image and source code are scanned for vulnerabilities and potential security issues.

* **Vulnerability Scan**: **Trivy** scans the container image for `CRITICAL` and `HIGH` severity CVEs. This step is non-blocking (for now) but will issue a warning if vulnerabilities are found.
* **Static Analysis**: **Semgrep** performs static analysis on the repository's code to find potential bugs and security flaws.

---

### 4. Push & Sign Stage 🚀

If the test and scan stages pass, and the event is not a pull request, the image is published and cryptographically signed.

* **Push**: The image is pushed to both **GitHub Container Registry (GHCR)** and **Docker Hub** with all the tags generated during the build stage.
* **Sign**: Both the GHCR and Docker Hub images are signed using **Cosign** and the keyless signing provider **Sigstore**. This creates a verifiable attestation, ensuring each image's integrity and provenance.

---

## Getting Started

To use this project, you can fork the repository and customize the image to your needs. I first installed a Fedora Atomic Spin (Sway), and then rebased to a bootc compatible image. My system has been managed with bootc & with images built from this pipeline. I've tested this with Fedora versions 42 & 43.

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
cd exousia

# Build the image
make build

# Push to local registry (optional)
make push

# Deploy to your system
make deploy
```

---

## Customization

The primary file for customization is the `Containerfile`. The 'custom-*' directories have content that can be modified to create your desired OS image. Currently, it's set for an atomic image, but this will be adapted to directly support and produce a working full custom fedora-bootc image.

### Package Management

Edit the package lists in `custom-pkgs/`:

- **`packages.add`** - Packages to install on top of the base image
- **`packages.remove`** - Packages to remove from the base image

Current customizations include:
- **Added**: kitty, neovim, htop, btop, distrobox, virt-manager, pam-u2f, and more
- **Removed**: foot, dunst, rofi-wayland

### Configuration Files

Place configuration files in the appropriate `custom-configs/` subdirectories:

- `custom-configs/sway/` - Sway window manager configuration
- `custom-configs/greetd/` - Display manager configuration  
- `custom-configs/plymouth/` - Boot splash configuration

### Custom Scripts

Add executable scripts to `custom-scripts/` - they will be copied to `/usr/local/bin/`:

- `autotiling` - Automatic tiling layout for Sway
- `config-authselect` - U2F authentication setup
- `lid` - Laptop lid state handler
- `fedora-version-switcher` - Switch between Fedora versions (fedora-bootc branch)
- `generate-readme` - Dynamic README generator (fedora-bootc branch)

### Custom Repositories

Additional repositories in `custom-repos/`:

- RPM Fusion (free and nonfree)
- nwg-shell COPR
- swaylock-effects COPR

---

## Required Secrets

This workflow requires secrets to push the container image to GHCR and Docker Hub. You must add these to your repository's secrets under `Settings > Secrets and variables > Actions`.

* **For GitHub Container Registry (GHCR):**
    * `GHCR_PAT`: A GitHub Personal Access Token (PAT) with the `write:packages` scope.
* **For Docker Hub:**
    * `DOCKERHUB_USERNAME`: Your Docker Hub username.
    * `DOCKERHUB_TOKEN`: A Docker Hub Access Token with `Read, Write, Delete` permissions.

---

## Known Issues

### GHCR Authentication

I can only get the `sudo bootc switch` & `sudo bootc upgrade` commands to fully work with Docker Hub. Using the first command with the GHCR gives me a "403 Forbidden | Invalid Username/Password" error, even though skopeo inspect, and podman pull work just fine.

So, while this pipeline pushes images to both registries, my system pulls from Docker Hub. This may change once I figure out the source of the token permissions error.

---

## Project Structure

```
exousia/
├── Containerfile              # Main build instructions
├── Makefile                   # Local build automation
├── containers-auth.conf       # Container auth configuration
├── custom-configs/            # System configuration files
│   ├── sway/                 # Sway WM configs
│   ├── greetd/               # Display manager
│   └── plymouth/             # Boot splash themes
├── custom-pkgs/               # Package management
│   ├── packages.add          # Packages to install
│   └── packages.remove       # Packages to remove
├── custom-repos/              # Additional repositories
│   ├── nwg-shell.repo
│   └── swaylock-effects.repo
├── custom-scripts/            # Custom utility scripts
│   ├── autotiling
│   ├── config-authselect
│   ├── lid
│   ├── fedora-version-switcher    # (fedora-bootc branch)
│   └── generate-readme             # (fedora-bootc branch)
├── tests/                     # Bats test suite
│   └── image_content.bats
└── .github/
    └── workflows/
        └── build.yaml        # CI/CD pipeline
```

---

## Testing

The project includes comprehensive Bats tests that verify:

- OS version and base configuration
- Package installation/removal
- Custom scripts are executable
- Repository configuration
- Container authentication setup
- bootc compliance

Run tests locally:
```bash
export TEST_IMAGE_TAG="localhost:5000/exousia:latest"
buildah unshare -- bats tests/image_content.bats
```

---

## Updates & Maintenance

### Automatic Updates

By default, bootc systems perform time-based updates via a systemd timer. Your system will automatically check for new image versions and apply them.

### Manual Updates

```bash
# Check for updates
sudo bootc upgrade

# Apply updates and reboot
sudo systemctl reboot

# Check current status
sudo bootc status
```

### Rollback

If something goes wrong:
```bash
# Rollback to previous image
sudo bootc rollback
sudo systemctl reboot
```

---

## Documentation & Resources

### Official Documentation
- [Official Bootc Docs](https://bootc-dev.github.io/bootc/intro.html)
- [Fedora Docs – Getting Started With Bootc](https://docs.fedoraproject.org/en-US/bootc/getting-started/)
- [Fedora bootc Base Images](https://docs.fedoraproject.org/en-US/bootc/base-images/)
- [Building Containers](https://docs.fedoraproject.org/en-US/bootc/building-containers/)

### Community Resources
- [Fedora Discussion - bootc](https://discussion.fedoraproject.org/tag/bootc)
- [bootc Issue Tracker](https://gitlab.com/fedora/bootc/tracker)

### Articles & Guides
- [Fedora Magazine – How to rebase to Fedora Silverblue 43 Beta](https://fedoramagazine.org/how-to-rebase-to-fedora-silverblue-43-beta/)
- [Fedora Magazine – A Great Journey Towards Fedora CoreOS and Bootc](https://fedoramagazine.org/a-great-journey-towards-fedora-coreos-and-bootc/)
- [Fedora Magazine – Building Your Own Atomic Bootc Desktop](https://fedoramagazine.org/building-your-own-atomic-bootc-desktop/)

### Technical References
- [How to workaround rpm dependency?](https://github.com/coreos/bootupd/issues/468)
- [Unification of boot loader updates, phase 1](https://gitlab.com/fedora/bootc/tracker/-/issues/61)
- [Add Plymouth to Fedora-Bootc](https://www.reddit.com/r/Fedora/comments/1nq636t/comment/ngbgfkh/)

---

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally with `make build`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## Roadmap

- [x] Basic bootc image with Sway
- [x] Comprehensive CI/CD pipeline
- [x] Automated testing with Bats
- [x] Image signing with Cosign
- [ ] Dynamic Fedora version switching (**In Progress - `fedora-bootc` branch**)
- [ ] Dynamic README generation (**In Progress - `fedora-bootc` branch**)
- [ ] Support for multiple base images (bootc, sway-atomic)
- [ ] Cloud deployment templates

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments

- The Fedora Project and bootc maintainers
- The broader container and immutable OS community
- All contributors to the referenced documentation and guides
- nwg-piotr for autotiling script

---

**Built with ❤️ using Fedora bootc & Fedora Atomic**

*Last updated: September 2025*