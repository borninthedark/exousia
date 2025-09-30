# Test Suite

Bats-based integration tests for bootc container images.

## Running Tests

### Using Make (Recommended)
```bash
# Build and test
make build test

# Test only
make test-run

# Setup check
make test-setup

# Set image tag
export TEST_IMAGE_TAG=localhost:5000/exousia:latest

# Run all tests
buildah unshare -- bats -r tests/

# Verbose mode
buildah unshare -- bats -r tests/ --verbose-run

# TAP format
buildah unshare -- bats -r tests/ --formatter tap

tests/
├── README.md              # This file
└── image_content.bats     # Main test suite (52+ tests)

# Run specific test by line number
buildah unshare -- bats tests/image_content.bats:85

# Filter tests by pattern
buildah unshare -- bats tests/image_content.bats --filter "package"

# Show all output
buildah unshare -- bats -r tests/ --show-output-of-passing-tests

# Fedora/RHEL
sudo dnf install bats buildah

# Or from source
git clone https://github.com/bats-core/bats-core.git
cd bats-core
sudo ./install.sh /usr/local

# Or use the github action #

# Always use buildah unshare
buildah unshare -- bats -r tests/