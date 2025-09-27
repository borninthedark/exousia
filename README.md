# Fedora Sway Atomic (`bootc`) Image

[](https://www.google.com/search?q=https://github.com/YOUR_USERNAME/YOUR_REPOSITORY/actions/workflows/main.yml)

This repository contains the configuration to build a custom, container-based immutable version of **Fedora Sway (Sericea)** using [`bootc`](https://www.google.com/search?q=%5Bhttps://github.com/containers/bootc%5D\(https://github.com/containers/bootc\)). The image is built, tested, and published using a comprehensive DevSecOps CI/CD pipeline with GitHub Actions.

## CI/CD Workflow: `Sericea DevSec CI`

The pipeline is defined in a single, unified GitHub Actions workflow that automates the entire lifecycle of the image. The workflow is triggered on pushes and pull requests to the `main` branch, on a nightly schedule, or by manual dispatch. I'm using Fedora Sway Atomic (Sericea) as my base, but this should work for all atomic variants. Tested with Fedora 42/43.

I first installed an atomic spin using the installer, and then rebased into a bootc compatible image. I've continued to manage the image using bootc thereafter. 

### 1\. Build Stage 🏗️

The first stage assembles the container image and prepares it for testing.

  - **Lint**: The `Containerfile` is first linted using **Hadolint** to ensure it follows best practices.
  - **Tagging**: Image tags are dynamically generated based on the event trigger (e.g., `latest`, `nightly`, branch name, and commit SHA).
  - **Build**: The image is built using **Buildah**, a daemonless container image builder well-suited for CI environments.

### 2\. Test Stage 🧪

After a successful build, the image and repository scripts undergo automated testing to ensure quality and correctness.

  - **Integration Tests**: The **Bats (Bash Automated Testing System)** framework runs tests against the built container to verify its configuration and functionality.
  - **Script Analysis**: All shell scripts in the repository are linted with **ShellCheck** to catch common scripting errors.

### 3\. Scan Stage 🛡️

Security is a critical part of the pipeline. The built image and source code are scanned for vulnerabilities and potential security issues.

  - **Vulnerability Scan**: **Trivy** scans the container image for `CRITICAL` and `HIGH` severity CVEs in its packages. This step is non-blocking but will issue a warning if vulnerabilities are found. Eventually, it WILL be blocking.
  - **Static Analysis**: **Semgrep** performs static analysis on the repository's code to find potential bugs and security flaws.

### 4\. Push & Sign Stage 🚀

If the test and scan stages pass, and the event is not a pull request, the image is published and cryptographically signed.

  - **Push**: The image is pushed to **GitHub Container Registry (GHCR)** with all the tags generated during the build stage.
  - **Sign**: The image is signed using **Cosign** and the keyless signing provider **Sigstore**. This creates a verifiable attestation, ensuring the image's integrity and provenance.

## Getting Started

To use this project, you can fork the repository and customize the image to your needs.

### Customization

The primary file for customization is the `Containerfile`. You can add or remove packages and run commands here to create your desired OS image. This repo may be updated to implement Ansible in the future. 

### Required Secrets

This workflow requires a secret to push the container image to GHCR.

  - `GHCR_PAT`: A GitHub Personal Access Token (PAT) with the `write:packages` scope. You must add this to your repository's secrets under `Settings > Secrets and variables > Actions`.