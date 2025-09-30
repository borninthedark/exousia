# Writing Tests

Guide for adding new tests to the suite.

## Table of Contents

1. [Test Structure](#test-structure)
2. [Best Practices](#best-practices)
3. [Common Patterns](#common-patterns)
4. [Examples](#examples)
5. [Debugging](#debugging)
6. [Testing Checklist](#testing-checklist)

## Test Structure

```bash
@test "Descriptive test name that explains what is being validated" {
    # Arrange: Setup test data or conditions (if needed)
    
    # Act: Perform the action or check
    run command_to_test
    
    # Assert: Verify the results
    assert_success "Helpful error message explaining what failed"
    assert_output "expected output"
}
```

## Best Practices

### 1. Use Descriptive Names

```bash
# Good
@test "MPD music player daemon should be installed for audio playback"

# Bad
@test "check mpd"
```

Test names should:
- Explain what is being tested
- Describe expected behavior
- Be readable as documentation

### 2. Provide Helpful Error Messages

```bash
# Good
assert_success "pavucontrol should be installed for audio volume control"

# Bad
assert_success
```

Error messages should:
- Explain what should have happened
- Provide context for debugging
- Be specific about the failure

### 3. Use Appropriate Helpers

```bash
# File existence
assert_file_exists "$MOUNT_POINT/path/to/file"

# File executable
assert_file_executable "$MOUNT_POINT/usr/local/bin/script"

# Symlink validation
assert_symlink_to "$MOUNT_POINT/opt" "/var/opt"

# Directory existence
assert_dir_exists "$MOUNT_POINT/var/lib/greeter"
```

Available helpers from bats-file:
- `assert_file_exists`
- `assert_file_not_exists`
- `assert_file_executable`
- `assert_file_not_executable`
- `assert_dir_exists`
- `assert_dir_not_exists`
- `assert_symlink_to`
- `assert_link_exists`

### 4. Handle Conditional Logic

```bash
@test "Feature X should work for specific image type" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        # Test fedora-bootc specific feature
        assert_file_exists "$MOUNT_POINT/specific/file"
    else
        # Inform that test was skipped
        echo "# Skipping test for $IMAGE_TYPE" >&3
    fi
}
```

**When to use conditionals:**
- Feature exists only in one image type
- Configuration differs by type
- Different packages installed per type

**Echo to `>&3`** to show skip messages in test output.

### 5. Test Both Presence and Absence

```bash
@test "Replaced packages should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q foot
    assert_failure "foot should be removed (replaced by kitty)"
}
```

Test what should NOT be present to catch regressions.

### 6. Keep Tests Independent

Each test should:
- Not depend on other tests running first
- Not modify shared state
- Clean up after itself (if needed)

### 7. Use `run` for Commands

```bash
# Always use 'run' to capture output and status
run buildah run "$CONTAINER" -- rpm -q package-name
assert_success

# Access output with $output
run grep "pattern" "$MOUNT_POINT/file"
assert_output --partial "expected text"
```

## Common Patterns

### Package Installation

```bash
@test "Package X should be installed" {
    run buildah run "$CONTAINER" -- rpm -q package-name
    assert_success "package-name should be installed"
}
```

### File Permissions

```bash
@test "Script should be executable" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/script"
}
```

### File Content Validation

```bash
@test "Configuration file should contain required setting" {
    assert_file_exists "$MOUNT_POINT/etc/example/config.conf"
    
    run grep -q 'setting=value' "$MOUNT_POINT/etc/example/config.conf"
    assert_success "Configuration should contain 'setting=value'"
}
```

### Symlink Verification

```bash
@test "Symlink should point to correct target" {
    run test -L "$MOUNT_POINT/path/to/link"
    assert_success "Should be a symlink"
    
    run readlink "$MOUNT_POINT/path/to/link"
    assert_output "/target/path"
}
```

### Service Validation

```bash
@test "Service should be enabled" {
    run buildah run "$CONTAINER" -- systemctl is-enabled example.service
    assert_success "example.service should be enabled"
}
```

### User Validation

```bash
@test "System user should exist with correct configuration" {
    run chroot "$MOUNT_POINT" getent passwd username
    assert_success "username should exist"
    
    echo "$output" | grep -Eq '^username:x:[0-9]+:[0-9]+:.*'
    assert_success "username should have correct format"
}
```

### Multiple Assertions

```bash
@test "Package should be installed and configured" {
    # Check installation
    run buildah run "$CONTAINER" -- rpm -q package-name
    assert_success "package-name should be installed"
    
    # Check configuration exists
    assert_file_exists "$MOUNT_POINT/etc/package/config.conf"
    
    # Check configuration content
    run grep -q 'enabled=true' "$MOUNT_POINT/etc/package/config.conf"
    assert_success "Package should be enabled"
}
```

## Examples

### Adding a New Package Test

```bash
@test "ranger file manager should be installed" {
    run buildah run "$CONTAINER" -- rpm -q ranger
    assert_success "ranger should be installed for terminal file management"
}
```

### Testing Configuration Files

```bash
@test "Sway environment file should exist and contain Java compatibility" {
    assert_file_exists "$MOUNT_POINT/etc/sway/environment"
    
    run grep -q '_JAVA_AWT_WM_NONREPARENTING=1' "$MOUNT_POINT/etc/sway/environment"
    assert_success "Sway environment should contain Java compatibility variable"
}
```

### Testing Executable Scripts

```bash
@test "Custom script should be executable and have correct shebang" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/custom-script"
    
    run head -n1 "$MOUNT_POINT/usr/local/bin/custom-script"
    assert_output '#!/usr/bin/env bash'
}
```

### Conditional Tests by Image Type

```bash
@test "Directory structure should be correct for fedora-bootc" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        assert_dir_exists "$MOUNT_POINT/var/roothome"
        assert_dir_exists "$MOUNT_POINT/var/opt"
        
        run test -L "$MOUNT_POINT/opt"
        assert_success "/opt should be a symlink"
        
        run readlink "$MOUNT_POINT/opt"
        assert_output "/var/opt"
    else
        echo "# Skipping fedora-bootc directory structure check for $IMAGE_TYPE" >&3
    fi
}
```

### Testing Services (Conditional)

```bash
@test "Greetd service should be enabled for fedora-bootc" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        run buildah run "$CONTAINER" -- systemctl is-enabled greetd.service
        assert_success "greetd should be enabled for fedora-bootc"
        
        run buildah run "$CONTAINER" -- systemctl get-default
        assert_output "graphical.target"
    else
        echo "# Skipping greetd service check for $IMAGE_TYPE" >&3
    fi
}
```

### Testing Package Removal

```bash
@test "Foot terminal should be removed (replaced by kitty)" {
    run buildah run "$CONTAINER" -- rpm -q foot
    assert_failure "foot should not be installed (replaced by kitty)"
}
```

### Testing Repository Configuration

```bash
@test "RPM Fusion Free repository should be configured and enabled" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    
    run grep -E '^\s*enabled\s*=\s*1' "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_success "RPM Fusion Free should be enabled"
}
```

## Debugging

### Running Single Tests

```bash
# By line number
buildah unshare -- bats tests/image_content.bats:LINE_NUMBER

# By filter/pattern
buildah unshare -- bats tests/image_content.bats --filter "package"
```

### Verbose Output

```bash
# Show all output
buildah unshare -- bats tests/image_content.bats:LINE_NUMBER --verbose-run

# Show passing test output
buildah unshare -- bats -r tests/ --show-output-of-passing-tests
```

### Add Debug Output

```bash
@test "debug test" {
    echo "IMAGE_TYPE=$IMAGE_TYPE" >&3
    echo "MOUNT_POINT=$MOUNT_POINT" >&3
    ls -la "$MOUNT_POINT/usr/local/bin/" >&3
    
    # Your test logic here
}
```

### Manual Container Inspection

```bash
# Mount container for inspection
CONTAINER=$(buildah from localhost:5000/exousia:test)
MOUNT_POINT=$(buildah mount "$CONTAINER")

# Inspect manually
ls -la "$MOUNT_POINT/path/to/inspect"
chroot "$MOUNT_POINT" rpm -qa | grep package

# Interactive shell
chroot "$MOUNT_POINT" /bin/bash

# Cleanup
exit
buildah umount "$CONTAINER"
buildah rm "$CONTAINER"
```

## Testing Checklist

Before submitting new tests:

- [ ] Test name is descriptive and explains what is validated
- [ ] Error messages are helpful and provide context
- [ ] Appropriate bats helpers used (assert_file_exists, etc.)
- [ ] Conditional logic handled correctly for image types
- [ ] Tests pass locally with fedora-sway-atomic
- [ ] Tests pass locally with fedora-bootc
- [ ] Tests pass in CI environment
- [ ] No dependencies on other tests
- [ ] Documentation updated if needed

## Common Mistakes to Avoid

### 1. Not Using `run`

```bash
# Wrong
buildah run "$CONTAINER" -- rpm -q package
assert_success

# Right
run buildah run "$CONTAINER" -- rpm -q package
assert_success
```

### 2. Missing Error Messages

```bash
# Wrong
assert_success

# Right
assert_success "Package should be installed"
```

### 3. Hardcoded Paths

```bash
# Wrong
assert_file_exists "/path/in/container"

# Right
assert_file_exists "$MOUNT_POINT/path/in/container"
```

### 4. Forgetting Conditional Skip Messages

```bash
# Wrong
if [[ "$IMAGE_TYPE" != "fedora-bootc" ]]; then
    return 0
fi

# Right
if [[ "$IMAGE_TYPE" != "fedora-bootc" ]]; then
    echo "# Skipping for $IMAGE_TYPE" >&3
    return 0
fi
```

### 5. Testing Multiple Things Without Clear Assertions

```bash
# Wrong
@test "package works" {
    run buildah run "$CONTAINER" -- rpm -q package
    run grep config "$MOUNT_POINT/etc/config"
    assert_success
}

# Right
@test "package should be installed and configured" {
    run buildah run "$CONTAINER" -- rpm -q package
    assert_success "Package should be installed"
    
    run grep config "$MOUNT_POINT/etc/config"
    assert_success "Configuration should exist"
}
```

## Resources

- [bats-core Documentation](https://bats-core.readthedocs.io/)
- [bats-support Helpers](https://github.com/bats-core/bats-support)
- [bats-assert Assertions](https://github.com/bats-core/bats-assert)
- [bats-file File Helpers](https://github.com/bats-core/bats-file)
- [Test Suite Guide](./guide.md)
- [Troubleshooting](./troubleshooting.md)