# Test Suite

Bats-based integration tests for bootc container images.

## Running Tests

```bash
# Build and test via Makefile
make build
make test

# Or run directly
export TEST_IMAGE_TAG=localhost:5000/exousia:latest
buildah unshare -- bats -r custom-tests/

# Verbose mode
buildah unshare -- bats -r custom-tests/ --verbose-run
```

## Structure

```text
custom-tests/
├── overlay_content.bats   # Pre-build: validates overlay source files before the image is built
└── image_content.bats     # Post-build: validates the built container image
```

`overlay_content.bats` runs against the local source tree (no container needed) and
catches missing files, bad placeholders, or misconfigured unit files before a build starts.

`image_content.bats` mounts the built container image with `buildah` and asserts on
filesystem contents, installed packages, enabled services, and configuration files.

## Filtering

```bash
# Run specific test by line number
buildah unshare -- bats custom-tests/image_content.bats:85

# Filter tests by pattern
buildah unshare -- bats custom-tests/image_content.bats --filter "package"
```

## Prerequisites

```bash
# Fedora
sudo dnf install bats buildah
```

## Why Bats?

The integration suite mounts the produced container image with `buildah` and
asserts on its filesystem contents. Using Bats keeps the runner dependency
footprint minimal (only shell, buildah, and the bats libraries are required)
and avoids having to vendor Python tooling into the host or the image under
test.

## See Also

- [Testing Docs](../docs/testing/) -- Test architecture and writing guide
- [Build Tools](../tools/) -- Transpiler that generates the Containerfile
