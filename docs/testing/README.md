# Testing Documentation

Comprehensive testing suite for Exousia bootc images with conditional support for multiple base image types.

## Quick Start

```bash
# Run complete test suite
make test

# Run tests only (assumes image exists)
make test-run

# Run with specific image
export TEST_IMAGE_TAG=localhost:5000/exousia:latest
buildah unshare -- bats -r tests/
```

## Documentation

- **[Test Suite Guide](./guide.md)** - Architecture, test categories, and comprehensive reference
- **[Writing Tests](./writing-tests.md)** - Best practices and patterns for adding tests
- **[Troubleshooting](./troubleshooting.md)** - Common issues, debugging, and solutions

## Test Coverage

The test suite includes 52+ tests organized into 12 categories:

### Core Categories
1. OS and Fedora version validation
2. Container authentication configuration (CI only)
3. Package lists and Plymouth boot splash
4. Custom scripts and executables
5. Repository configuration
6. Package installation verification

### System Categories
7. Flatpak configuration
8. Sway desktop environment
9. bootc compliance
10. System components
11. System users and groups
12. Conditional tests (image type specific)

### Conditional Testing

Tests automatically adapt based on base image type:

| Image Type | Behavior |
|------------|----------|
| **fedora-bootc** | Full validation including Sway installation, service enablement, directory structure |
| **fedora-sway-atomic** | Skips pre-configured features, validates customizations only |

**Example output:**
```
✓ Directory structure should be correct for image type
  # Skipping fedora-bootc specific directory checks for fedora-sway-atomic
✓ Services should be enabled based on image type
  # Skipping fedora-bootc specific service checks for fedora-sway-atomic
```

## Requirements

### Software Dependencies

```bash
# Fedora/RHEL
sudo dnf install bats buildah

# Debian/Ubuntu
sudo apt install bats buildah

# From source
git clone https://github.com/bats-core/bats-core.git
cd bats-core
sudo ./install.sh /usr/local
```

### Build Requirements

Tests require a built container image:

```bash
# Build first
make build

# Then test
make test
```

## CI/CD Integration

Tests run automatically in GitHub Actions after each build. See `.github/workflows/build.yaml` for configuration.

**CI Features:**
- Automatic bats library installation
- Proper environment variable setup
- Image type detection
- Clear failure reporting

## Quick Examples

### Test Both Image Types

```bash
# Test fedora-sway-atomic (default)
make build test

# Switch to fedora-bootc
make switch-version VERSION=43 TYPE=fedora-bootc
make build test
```

### Debug Failed Tests

```bash
# Verbose output
buildah unshare -- bats -r tests/ --verbose-run

# Run specific test
buildah unshare -- bats tests/image_content.bats:42

# Filter by name
buildah unshare -- bats tests/image_content.bats --filter "Plymouth"
```

### Manual Container Inspection

```bash
# Mount container for inspection
CONTAINER=$(buildah from localhost:5000/exousia:test)
MOUNT_POINT=$(buildah mount "$CONTAINER")

# Inspect filesystem
ls -la "$MOUNT_POINT/usr/local/bin/"
chroot "$MOUNT_POINT" rpm -qa | grep sway

# Cleanup
buildah umount "$CONTAINER"
buildah rm "$CONTAINER"
```

## Test Statistics

- **Total Tests:** 52+
- **Conditional Tests:** 8 (adapt to image type)
- **Universal Tests:** 44 (run for all images)
- **Categories:** 12
- **Average Runtime:** 30-45 seconds

## What Gets Tested

### Package Installation
- Core system packages (DNF5, bootc, systemd)
- Desktop environment (Sway, waybar)
- User applications (kitty, neovim, htop, btop, ranger)
- Audio/media (mpd, pavucontrol)
- Virtualization (virt-manager, qemu-kvm)
- Security tools (pam-u2f, lynis)

### Configuration Files
- Sway window manager config
- Plymouth boot splash
- Greetd display manager
- System user definitions
- Repository configuration

### System Setup
- Service enablement (conditional)
- Directory structure (conditional)
- User/group creation
- Symlink configuration
- ComposeFS enablement

### Security & Compliance
- bootc container lint
- Package removal verification
- Permission validation
- Authentication configuration

## Common Use Cases

### Adding a New Package

1. Add package to `custom-pkgs/packages.add`
2. Write test in `tests/image_content.bats`:
```bash
@test "New package should be installed" {
    run buildah run "$CONTAINER" -- rpm -q new-package
    assert_success "new-package should be installed"
}
```
3. Build and test: `make build test`

### Testing Configuration Changes

1. Modify config in `custom-configs/`
2. Add validation test
3. Test locally with both image types
4. Verify CI passes

### Debugging Build Failures

1. Check build logs: `podman build . 2>&1 | less`
2. Run tests with verbose output
3. Inspect container manually
4. Review [Troubleshooting](./troubleshooting.md)

## Environment Variables

Tests recognize these environment variables:

- `TEST_IMAGE_TAG` - (Required) Image to test
- `CI` - Set to "true" in CI environments
- `BATS_LIB_PATH` - Path to bats libraries
- `TERM` - Terminal type (set to "xterm" in CI)

## Further Reading

### Internal Documentation
- [Test Suite Guide](./guide.md) - Complete reference
- [Writing Tests](./writing-tests.md) - Developer guide
- [Troubleshooting](./troubleshooting.md) - Debug help

### External Resources
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/)
- [bats-core Testing Framework](https://bats-core.readthedocs.io/)
- [Buildah Documentation](https://buildah.io/)
- [GitHub Actions Workflows](https://docs.github.com/en/actions)

## Contributing

When adding new tests:

1. Follow patterns in [Writing Tests](./writing-tests.md)
2. Use descriptive names and helpful error messages
3. Handle conditional logic for image types
4. Test locally with both base images
5. Verify CI passes
6. Update documentation

## Getting Help

If you encounter issues:

1. Check [Troubleshooting](./troubleshooting.md)
2. Review test output with `--verbose-run`
3. Inspect container manually
4. Check recent Containerfile changes
5. Open an issue with full details

---

**Quick Links:**
- [Main README](../../README.md)
- [Test Files](../../tests/)
- [CI Workflow](../../.github/workflows/build.yaml)
- [Containerfile](../../Containerfile)