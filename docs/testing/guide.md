# Test Suite Guide

Comprehensive documentation for the Exousia bootc image test suite.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Test Categories](#test-categories)
4. [Conditional Testing](#conditional-testing)
5. [Running Tests](#running-tests)
6. [CI/CD Integration](#cicd-integration)

## Overview

The test suite validates bootc container images using bats-core with
conditional testing that adapts to different base image types
(`fedora-bootc` vs `fedora-sway-atomic`).

### Key Features

- **Broad image and overlay coverage** across the current validation categories
- **Conditional execution** based on detected image type
- **Workflow-aware** with clear separation between local Bats validation and CI Python/security gates
- **Developer friendly** with clear assertions and error messages
- **Flexible** supports multiple Fedora versions and base images

## Architecture

### Test Framework Stack

```text
┌─────────────────────────────────────┐
│   bats-core (Test Runner)           │
├─────────────────────────────────────┤
│   bats-support (Assertions)         │
│   bats-assert (Enhanced Assertions) │
│   bats-file (File System Helpers)   │
├─────────────────────────────────────┤
│   Buildah (Container Inspection)    │
├─────────────────────────────────────┤
│   Container Image Under Test        │
└─────────────────────────────────────┘
```

### Test Lifecycle

1. **setup_file()** - Mount container, detect image type, export variables
2. **Test execution** - Run individual tests
3. **teardown_file()** - Unmount and cleanup container

### File Structure

```text
tests/
└── image_content.bats    # Main test suite
    ├── setup_file()      # One-time setup
    ├── teardown_file()   # Cleanup
    └── @test blocks      # Individual tests
```

## Test Categories

### 1. OS and Version Validation

Validates operating system and Fedora version.

**Tests:**

- Confirms OS is Fedora Linux
- Validates version (41-44 or rawhide)
- Checks BUILD_IMAGE_TYPE environment variable

**Example:**

```bash
@test "OS should be Fedora Linux" {
    run grep 'ID=fedora' "$MOUNT_POINT/etc/os-release"
    assert_success "Should be running Fedora Linux"
}
```

### 2. Container Authentication

Validates that runtime auth is not baked into the image and that the
container-auth path wiring exists where expected.

**Tests:**

- auth.json absence from the image payload
- ostree symlink configuration
- tmpfiles.d configuration

### 3. Packages and Plymouth

Verifies custom package management and boot splash configuration.

**Tests:**

- Plymouth theme installation
- Plymouth configuration files
- Kernel arguments when enabled
- package and repo expectations from the built image

### 4. Custom Scripts

Ensures shipped helper scripts are executable and staged correctly.

**Scripts tested:**

- Plymouth/setup helpers
- runtime helper scripts under `overlays/sway/scripts/runtime/`

### 5. Repository Configuration

Validates package repository setup.

**Tests:**

- RPM Fusion repositories present and enabled
- Custom repositories configured (nwg-shell)

### 6. Package Installation

Verifies all required packages are installed.

**Package Groups:**

- **Core System:** DNF5, bootc, systemd, NetworkManager, Podman
- **Desktop:** Sway, waybar, swaylock
- **Applications:** kitty, neovim, htop, btop, ranger
- **Audio:** mpd, pavucontrol
- **Virtualization:** virt-manager, qemu-kvm, libvirt
- **Security:** pam-u2f, lynis

### 7. Package Removal Verification

Confirms replaced packages are not present.

**Tests:**

- foot (replaced by kitty)
- dunst (replaced by swaync)
- rofi-wayland (replaced by fuzzel)

### 8. Flatpak Configuration

Validates Flatpak repository setup.

**Tests:**

- Flathub remote added
- Correct repository URL

### 9. Sway Configuration

Validates Sway window manager setup.

**Tests:**

- Configuration files present
- Greetd configuration valid
- Session files (conditional on fedora-bootc)

### 10. PAM U2F Configuration

Validates YubiKey hardware authentication setup.

**Tests:**

- PAM U2F configuration files present (u2f-required, u2f-sufficient)
- sudo configured with U2F support
- login configured with U2F support
- shared `/etc/Yubico/u2f_keys` authfile configured
- `/etc/skel/.config/Yubico` symlink present
- pam-u2f package installed

### 11. bootc Compliance

Ensures image meets bootc requirements.

**Tests:**

- bootc container lint passes
- ComposeFS enabled

### 12. System Components

Validates core system packages.

**Tests:**

- Systemd, kernel, NetworkManager, Podman present

### 13. System Users and Groups

Validates system user creation.

**Tests:**

- greeter, greetd, rtkit users exist
- Correct UID/GID assignments
- Proper home directories and shells
- sysusers configuration valid

### 14. Conditional Tests (Image Type Specific)

**fedora-bootc only:**

- Directory structure (/var/roothome, /var/opt, /opt symlink)
- Service enablement (greetd, libvirtd, graphical.target)
- Sway package installation

## Conditional Testing

### Detection Mechanism

```bash
setup_file() {
    # Detect image type from container environment
    BUILD_TYPE=$(buildah run "$CONTAINER" -- printenv BUILD_IMAGE_TYPE 2>/dev/null || echo "unknown")
    export BUILD_TYPE
}
```

### Test Patterns

**Pattern 1: Skip for non-applicable types**

```bash
@test "fedora-bootc specific feature" {
    if [[ "$BUILD_TYPE" != "fedora-bootc" ]]; then
        skip "Only applicable to fedora-bootc base"
    fi

    # Test logic
}
```

**Pattern 2: Informative skip messages**

```bash
@test "directory structure" {
    if [[ "$BUILD_TYPE" == "fedora-bootc" ]]; then
        assert_dir_exists "$MOUNT_POINT/var/roothome"
    else
        echo "# Skipping fedora-bootc specific checks for $BUILD_TYPE" >&3
    fi
}
```

**Pattern 3: Different assertions per type**

```bash
@test "services configured based on type" {
    if [[ "$BUILD_TYPE" == "fedora-bootc" ]]; then
        run buildah run "$CONTAINER" -- systemctl is-enabled greetd.service
        assert_success
    else
        echo "# Using fedora-sway-atomic defaults" >&3
    fi
}
```

### When to Use Conditional Tests

**Use conditionals when:**

- Feature only exists in one base image
- Configuration differs significantly between types
- Installation location varies by base

**Avoid conditionals when:**

- Same test applies to both types
- Behavior should be identical
- Testing custom additions (not base image features)

## Running Tests

### Prerequisites

```bash
# Install bats-core
sudo dnf install bats

# Install buildah
sudo dnf install buildah
```

### Local Execution

#### Using Make (Recommended)

```bash
# Pytest (tools/)
make test

# Pre-build overlay validation
make overlay-test

# Bats against built image
make local-test

# With specific image tag
make local-test TAG=custom
```

#### Direct Execution

```bash
# Build image first
podman build -t localhost:5000/exousia:test .

# Run tests
export TEST_IMAGE_TAG=localhost:5000/exousia:test
buildah unshare -- bats -r tests/

# Verbose output
buildah unshare -- bats -r tests/ --verbose-run
```

### Test Specific Scenarios

#### Test fedora-bootc Build

```bash
make build-bootc
make local-test
```

#### Test fedora-sway-atomic Build

```bash
make build-atomic
make local-test
```

### Debugging Failed Tests

```bash
# Verbose output
buildah unshare -- bats -r tests/ --verbose-run

# Single test by line number
buildah unshare -- bats tests/image_content.bats:42

# Filter by name
buildah unshare -- bats tests/image_content.bats --filter "Plymouth"
```

## CI/CD Integration

The current GitHub Actions workflows run only the overlay-side Bats coverage.
Today the split is:

- `Hikifune`: Python linting and pytest
- `Uhin`: static/security checks plus `tests/overlay_content.bats`
- local/manual image Bats: `make local-test`

The built-image Bats suite still remains local/manual because it depends on a
prebuilt image and rootless `buildah unshare` execution.

### Test Results

**Success:**

```text
✓ OS should be Fedora Linux
✓ Package installation verified
...
All listed categories should pass with zero failures on a healthy branch.
```

**Failure:**

```text
✗ Package 'example' should be installed
  (in test file tests/image_content.bats, line 234)
  `assert_success "example should be installed"' failed
```

## Performance

- **Average runtime:** 30-45 seconds
- **With slow RPM queries:** up to 2 minutes
- **Parallelization:** Not currently supported (shared mount)

## Test Coverage Matrix

| Test Category | fedora-bootc | fedora-sway-atomic |
|--------------|--------------|-------------------|
| OS/Version Check | ✓ | ✓ |
| Package Installation | ✓ | ✓ |
| Config Files | ✓ | ✓ |
| System Users | ✓ | ✓ |
| Directory Structure | ✓ | ⊘ (skipped) |
| Service Enablement | ✓ | ⊘ (skipped) |
| Sway Package Install | ✓ | ⊘ (pre-installed) |
| Security Config | ✓ | ✓ |
| bootc Compliance | ✓ | ✓ |

## References

- [bats-core Documentation](https://bats-core.readthedocs.io/)
- [Buildah Documentation](https://buildah.io/)
- [bootc Documentation](https://bootc-dev.github.io/bootc/)
- [Writing Tests](../reference/writing-tests.md)
- [Troubleshooting](../reference/troubleshooting.md)
