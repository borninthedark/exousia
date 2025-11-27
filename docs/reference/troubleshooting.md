# Troubleshooting

Common issues and solutions for the test suite.

## Table of Contents

1. [Common Issues](#common-issues)
2. [Debug Strategies](#debug-strategies)
3. [Package-Related Issues](#package-related-issues)
4. [File-Related Issues](#file-related-issues)
5. [Service-Related Issues](#service-related-issues)
6. [Performance Issues](#performance-issues)
7. [Getting Help](#getting-help)

## Common Issues

### TEST_IMAGE_TAG not set

**Error:**
```
FATAL: TEST_IMAGE_TAG environment variable is not set.
```

**Cause:** Required environment variable not exported

**Solution:**
```bash
export TEST_IMAGE_TAG=localhost:5000/exousia:latest
buildah unshare -- bats -r custom-tests/
```

**Using Make:**
```bash
# Make sets this automatically
make test-run
```

---

### Permission Denied

**Error:**
```
Permission denied when accessing container
```

**Cause:** Tests need rootless container access via buildah

**Solution:**
Always use `buildah unshare`:
```bash
buildah unshare -- bats -r custom-tests/
```

**Never run:**
```bash
# Wrong - will fail
bats -r custom-tests/
```

---

### Tests Pass Locally but Fail in CI

**Possible causes:**
- Environment variable differences
- File permission issues in build
- CI-specific conditionals not working

**Debug steps:**

1. Check CI environment variables:
```bash
# Run locally with CI flag
CI=true TEST_IMAGE_TAG=localhost:5000/exousia:latest buildah unshare -- bats -r custom-tests/
```

2. Verify file permissions in Containerfile:
```dockerfile
# Ensure --chmod is correct
COPY --chmod=0755 custom-scripts/ /usr/local/bin/
COPY --chmod=0644 custom-configs/ /etc/
```

3. Review CI logs for specific failures:
- Check GitHub Actions workflow output
- Look for environment-specific errors
- Verify image built correctly

---

### Could Not Detect BUILD_IMAGE_TYPE

**Error:**
```
Detected image type: unknown
```

**Cause:** Environment variable not set in container

**Solution:**

1. Verify Containerfile sets the variable:
```dockerfile
ARG IMAGE_TYPE
ENV BUILD_IMAGE_TYPE=${IMAGE_TYPE}
```

2. Rebuild with proper build args:
```bash
podman build \
  --build-arg FEDORA_VERSION=43 \
  --build-arg IMAGE_TYPE=fedora-sway-atomic \
  -t localhost:5000/exousia:test .
```

3. Check the variable in container:
```bash
buildah run localhost:5000/exousia:test -- printenv BUILD_IMAGE_TYPE
```

---

### Conditional Tests Not Skipping

**Problem:** Tests for fedora-bootc run on fedora-sway-atomic

**Debug:**

1. Check image type detection:
```bash
CONTAINER=$(buildah from localhost:5000/exousia:test)
buildah run "$CONTAINER" -- printenv BUILD_IMAGE_TYPE
buildah rm "$CONTAINER"
```

2. Add debug output in test:
```bash
@test "debug image type detection" {
    echo "Detected IMAGE_TYPE: $IMAGE_TYPE" >&3
}
```

3. Verify conditional logic:
```bash
@test "example conditional test" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        # fedora-bootc specific test
    else
        echo "# Skipping for $IMAGE_TYPE" >&3
    fi
}
```

---

### Bats Libraries Not Found

**Error:**
```
bats: cannot load library 'bats-support'
```

**Solution:**

1. Install bats libraries:
```bash
# Using package manager
sudo dnf install bats

# Or clone manually
git clone https://github.com/bats-core/bats-support test/test_helper/bats-support
git clone https://github.com/bats-core/bats-assert test/test_helper/bats-assert
git clone https://github.com/bats-core/bats-file test/test_helper/bats-file
```

2. In CI, libraries are installed via `bats-core/bats-action@3.0.0`

---

## Debug Strategies

### 1. Enable Verbose Output

```bash
# Show all output including passing tests
buildah unshare -- bats -r custom-tests/ --verbose-run --show-output-of-passing-tests

# TAP format (useful for parsing)
buildah unshare -- bats -r custom-tests/ --formatter tap
```

### 2. Run Single Test

```bash
# By line number
buildah unshare -- bats custom-tests/image_content.bats:85

# By name filter
buildah unshare -- bats tests/image_content.bats --filter "Plymouth"

# Multiple filters
buildah unshare -- bats tests/image_content.bats --filter "package" --filter "install"
```

### 3. Add Debug Output

```bash
@test "debug test" {
    # Print environment variables
    echo "IMAGE_TYPE=$IMAGE_TYPE" >&3
    echo "MOUNT_POINT=$MOUNT_POINT" >&3
    echo "FEDORA_VERSION=$FEDORA_VERSION" >&3
    
    # List files
    ls -la "$MOUNT_POINT/usr/local/bin/" >&3
    
    # Check specific file
    cat "$MOUNT_POINT/path/to/file" >&3
}
```

### 4. Manual Container Inspection

```bash
# Start and mount container
CONTAINER=$(buildah from localhost:5000/exousia:test)
MOUNT_POINT=$(buildah mount "$CONTAINER")

# Inspect filesystem
ls -la "$MOUNT_POINT/usr/local/bin/"
cat "$MOUNT_POINT/etc/os-release"

# Check packages
chroot "$MOUNT_POINT" rpm -qa | grep sway

# Interactive shell
chroot "$MOUNT_POINT" /bin/bash

# Cleanup when done
exit
buildah umount "$CONTAINER"
buildah rm "$CONTAINER"
```

### 5. Check Build Logs

```bash
# Build with verbose output
podman build . --log-level=debug

# Check for errors during package installation
podman build . 2>&1 | grep -i "error\|fail\|warning"
```

---

## Package-Related Issues

### Package Not Found

**Error:**
```
package example is not installed
```

**Debug steps:**

1. Check package is in correct list:
```bash
grep "example" custom-pkgs/packages.add
grep "example" custom-pkgs/packages.sway
```

2. Verify package name spelling:
```bash
# Search in container
buildah run "$CONTAINER" -- dnf search example-package
```

3. Check if package exists in repositories:
```bash
# List available packages
buildah run "$CONTAINER" -- dnf list available | grep example
```

4. Review build logs for installation errors:
```bash
# Look for DNF failures during build
podman build . 2>&1 | grep "example"
```

---

### Package Installation Failed During Build

**Error during build:**
```
Error: Unable to find a match: package-name
```

**Solutions:**

1. Check repository configuration:
```bash
# Verify repos are added
cat custom-repos/*.repo
```

2. Verify package availability for Fedora version:
```bash
# Some packages may not be available in all versions
dnf search package-name --releasever=43
```

3. Check for typos in package name

4. Check if package requires specific repository:
```bash
# Example: Some packages need RPM Fusion
dnf info package-name --enablerepo=rpmfusion-free
```

---

## File-Related Issues

### File Not Found

**Error:**
```
File does not exist: /path/to/file
```

**Debug steps:**

1. Verify file exists in source:
```bash
ls -la custom-configs/path/to/file
```

2. Check Containerfile COPY directive:
```dockerfile
COPY --chmod=0644 custom-configs/ /etc/
```

3. Inspect container filesystem:
```bash
ls -la "$MOUNT_POINT/etc/path/to/file"
```

4. Check for typos in path

---

### Permission Issues

**Error:**
```
Script is not executable
```

**Solution:**

Use `--chmod` in COPY directive:
```dockerfile
# For scripts
COPY --chmod=0755 custom-scripts/ /usr/local/bin/

# For configs
COPY --chmod=0644 custom-configs/ /etc/
```

**Verify permissions:**
```bash
ls -la "$MOUNT_POINT/usr/local/bin/script"
# Should show: -rwxr-xr-x
```

---

### Symlink Issues

**Error:**
```
Symlink does not point to expected target
```

**Debug:**
```bash
# Check if it's a symlink
test -L "$MOUNT_POINT/path/to/link" && echo "Is symlink" || echo "Not symlink"

# Check target
readlink "$MOUNT_POINT/path/to/link"

# Check with ls
ls -la "$MOUNT_POINT/path/to/link"
```

---

## Service-Related Issues

### Service Not Enabled

**Error:**
```
greetd.service should be enabled
```

**Debug steps:**

1. Check if service package is installed:
```bash
buildah run "$CONTAINER" -- rpm -q greetd
```

2. Check image type (services only enabled for fedora-bootc):
```bash
buildah run "$CONTAINER" -- printenv BUILD_IMAGE_TYPE
```

3. Verify systemctl command in Containerfile:
```dockerfile
RUN if [ "$BUILD_IMAGE_TYPE" = "fedora-bootc" ]; then \
        systemctl enable greetd.service; \
    fi
```

4. List enabled services:
```bash
buildah run "$CONTAINER" -- systemctl list-unit-files --state=enabled
```

---

### Service File Not Found

**Error:**
```
Failed to enable unit: Unit file does not exist
```

**Solutions:**

1. Ensure package providing service is installed first
2. Check service file name (may differ from package name)
3. Verify service is available:
```bash
buildah run "$CONTAINER" -- systemctl list-unit-files | grep greetd
```

---

## Performance Issues

### Tests Running Slowly

**Causes:**
- Many RPM queries
- Large container image
- Slow disk I/O
- Network latency (if pulling images)

**Solutions:**

1. Use local image (avoid pulling):
```bash
# Build locally first
make build

# Then test
make test-run
```

2. Use SSD for build/test operations

3. Keep container mounted for multiple runs:
```bash
CONTAINER=$(buildah from localhost:5000/exousia:test)
MOUNT_POINT=$(buildah mount "$CONTAINER")

# Run tests multiple times
TEST_IMAGE_TAG=localhost:5000/exousia:test buildah unshare -- bats -r custom-tests/

# Cleanup when done
buildah umount "$CONTAINER"
buildah rm "$CONTAINER"
```

4. Run specific test categories instead of all tests

---

### Container Build Timeout

**Error:**
```
Build timeout exceeded
```

**Solutions:**

1. Increase timeout in Makefile or CI:
```yaml
# GitHub Actions
timeout-minutes: 60
```

2. Optimize Containerfile:
- Combine RUN commands
- Clean up in same layer
- Use dnf clean all

3. Use faster mirror:
```bash
# Add fastest mirror plugin
RUN dnf install -y dnf-plugins-core && \
    dnf config-manager --setopt=fastestmirror=True --save
```

---

## Getting Help

If you're still stuck after trying the above solutions:

### 1. Gather Information

```bash
# Get full test output
buildah unshare -- bats -r custom-tests/ --verbose-run 2>&1 | tee test-output.log

# Get build output
podman build . 2>&1 | tee build-output.log

# Get system info
uname -a
podman version
buildah version
bats --version
```

### 2. Check Documentation

- [Test Suite Guide](./guide.md)
- [Writing Tests](./writing-tests.md)
- [bats-core Documentation](https://bats-core.readthedocs.io/)

### 3. Review Recent Changes

```bash
# Check what changed in Containerfile
git diff HEAD~1 Containerfile

# Check what changed in tests
git diff HEAD~1 custom-tests/
```

### 4. Test with Defaults

```bash
# Reset to known-good configuration
make switch-version VERSION=43 TYPE=fedora-sway-atomic

# Clean build
make clean
make build test
```

### 5. Open an Issue

Include:
- Full test output (use `--verbose-run`)
- Build command used
- Image configuration (Fedora version, image type)
- Environment (OS, Podman/Buildah versions)
- Steps to reproduce

---

## Quick Reference

### Essential Commands

```bash
# Full verbose test run
buildah unshare -- bats -r custom-tests/ --verbose-run

# Test specific line
buildah unshare -- bats custom-tests/image_content.bats:85

# Inspect container
CONTAINER=$(buildah from IMAGE_TAG)
MOUNT_POINT=$(buildah mount "$CONTAINER")
ls -la "$MOUNT_POINT"
buildah umount "$CONTAINER" && buildah rm "$CONTAINER"

# Check environment
buildah run IMAGE_TAG -- printenv BUILD_IMAGE_TYPE

# View build logs
podman build . 2>&1 | less
```

---

## References

- [Test Suite Guide](./guide.md)
- [Writing Tests](./writing-tests.md)
- [Fedora bootc Documentation](https://docs.fedoraproject.org/en-US/bootc/)
- [bats-core Documentation](https://bats-core.readthedocs.io/)
- [Buildah Troubleshooting](https://github.com/containers/buildah/blob/main/troubleshooting.md)