# Fedora Sway Atomic (`bootc`) Image

[](https://www.google.com/search?q=https://github.com/YOUR_USERNAME/YOUR_REPOSITORY/actions/workflows/main.yml)

This repository contains the configuration to build a custom, container-based immutable version of **Fedora Sway (Sericea)** using [`bootc`](https://www.google.com/search?q=%5Bhttps://github.com/containers/bootc%5D\(https://github.com/containers/bootc\)). The image is built, tested, scanned, and published to multiple container registries using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions.

## CI/CD Workflow: `Sericea DevSec CI`

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire image lifecycle. The workflow is triggered on pushes and pull requests to the `main` branch, on a nightly schedule (`20 4 * * *`), or by manual dispatch.

### 1\. Build Stage 🏗️

The first stage assembles the container image and prepares it for the subsequent stages.

* **Lint**: The `Containerfile` is first linted using **Hadolint** to ensure it follows best practices.
* **Tagging**: Image tags are dynamically generated for both registries based on the event trigger (e.g., `latest`, `nightly`, branch name, and commit SHA).
* **Build**: The image is built using **Buildah**, a daemonless container image builder well-suited for CI environments.

---

### 2\. Test Stage 🧪

After a successful build, the image and repository scripts undergo automated testing to ensure quality and correctness.

* **Integration Tests**: The **Bats (Bash Automated Testing System)** framework runs tests against the built container to verify its configuration and functionality.
* **Script Analysis**: All shell scripts in the repository are linted with **ShellCheck** to catch common scripting errors.

---

### 3\. Scan Stage 🛡️

Security is a critical part of the pipeline. The built image and source code are scanned for vulnerabilities and potential security issues.

* **Vulnerability Scan**: **Trivy** scans the container image for `CRITICAL` and `HIGH` severity CVEs. This step is non-blocking (for now) but will issue a warning if vulnerabilities are found.
* **Static Analysis**: **Semgrep** performs static analysis on the repository's code to find potential bugs and security flaws.

---

### 4\. Push & Sign Stage 🚀

If the test and scan stages pass, and the event is not a pull request, the image is published and cryptographically signed.

* **Push**: The image is pushed to both **GitHub Container Registry (GHCR)** and **Docker Hub** with all the tags generated during the build stage.
* **Sign**: Both the GHCR and Docker Hub images are signed using **Cosign** and the keyless signing provider **Sigstore**. This creates a verifiable attestation, ensuring each image's integrity and provenance.

---

## Getting Started

To use this project, you can fork the repository and customize the image to your needs. I first installed a Fedora Atomic Spin (Sway), and then rebased to a bootc compatible image. My system has been managed with bootc & with images built from this pipeline. I've tested this with Fedora versions 42 & 43.

### Issues

I can only get the ```sudo bootc switch```, & ```sudo bootc upgrade``` commands to fully work with Docker Hub. Using the first command with the GHCR gives me a "403 Forbidden | Invalid Username/Password" error, even though skopeo inspect, and podman pull work just fine.

So, while this pipeline pushes images to both registries, my system pulls from Docker Hub. This may change once I figure out the source of the token permissions error.

### Customization

The primary file for customization is the `Containerfile`. The 'custom-*' directories have content that can capriciously be modified to create your desired OS image. Currently, it's set for an atomic image, but this will be adapted to directly support and produce a working full custom fedora-bootc image.

### Required Secrets

This workflow requires secrets to push the container image to GHCR and Docker Hub. You must add these to your repository's secrets under `Settings > Secrets and variables > Actions`.

* **For GitHub Container Registry (GHCR):**
    * `GHCR_PAT`: A GitHub Personal Access Token (PAT) with the `write:packages` scope.
* **For Docker Hub:**
    * `DOCKERHUB_USERNAME`: Your Docker Hub username.
    * `DOCKERHUB_TOKEN`: A Docker Hub Access Token with `Read, Write, Delete` permissions.

---

## Citations

This ever-expanding section acknowledges the helpful articles, documentation, and other resources used in creating this project.

* *How to workaround rpm dependency?:* `https://github.com/coreos/bootupd/issues/468`  
* *Unification of boot loader updates, phase 1:* `https://gitlab.com/fedora/bootc/tracker/-/issues/61`  
* *Add Plymouth to Fedora-Bootc:* `https://www.reddit.com/r/Fedora/comments/1nq636t/comment/ngbgfkh/`  
* *Official Bootc Docs:* `https://bootc-dev.github.io/bootc/intro.html`  
* *Fedora Docs – Getting Started With Bootc:* `https://docs.fedoraproject.org/en-US/bootc/getting-started/`  
* *Fedora Magazine – How to rebase to Fedora Silverblue 43 Beta:* `https://fedoramagazine.org/how-to-rebase-to-fedora-silverblue-43-beta/`  
* *Fedora Magazine – A Great Journey Towards Fedora CoreOS and Bootc:* `https://fedoramagazine.org/a-great-journey-towards-fedora-coreos-and-bootc/`  
* *Fedora Magazine – Building Your Own Atomic Bootc Desktop:* `https://fedoramagazine.org/building-your-own-atomic-bootc-desktop/`  
