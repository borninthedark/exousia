#!/usr/bin/env bats

# Additional Plymouth-conditional tests to add to image_content.bats

# Add this near the top with other helper functions:

# Helper function to check if Plymouth is enabled
is_plymouth_enabled() {
    [[ "${ENABLE_PLYMOUTH:-true}" == "true" ]]
}

# Update Plymouth tests to be conditional:

@test "Plymouth scripts should be present" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/setup-plymouth-theme"
    assert_file_executable "$MOUNT_POINT/usr/local/bin/dracut-rebuild"
}

@test "Custom Plymouth theme should be copied" {
    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
    assert_file_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
}

@test "Plymouth should be configured if enabled" {
    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi
    
    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed when enabled"
    
    # Check for dracut configuration
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    
    # Check kernel arguments
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    
    run grep -q 'splash' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Kernel arguments should contain 'splash'"
    
    run grep -q 'quiet' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Kernel arguments should contain 'quiet'"
}

@test "Plymouth should not be configured if disabled" {
    if is_plymouth_enabled; then
        skip "Plymouth is enabled (ENABLE_PLYMOUTH=true)"
    fi
    
    # Plymouth package might still be installed (from base image)
    # but configuration should not be present
    
    run test -f "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_failure "Plymouth kernel arguments should not exist when disabled"
}

@test "Plymouth dracut configuration should be correct if enabled" {
    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi
    
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    
    run grep -q 'add_dracutmodules.*plymouth' "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    assert_success "Dracut config should include Plymouth module"
}

@test "Initramfs should exist if Plymouth was enabled during build" {
    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled, initramfs may not have been rebuilt"
    fi
    
    # Find kernel version
    local kver
    if [[ -d "$MOUNT_POINT/usr/lib/modules" ]]; then
        kver=$(cd "$MOUNT_POINT/usr/lib/modules" && echo * | awk '{print $1}')
        
        if [[ "$kver" != "*" ]] && [[ -d "$MOUNT_POINT/usr/lib/modules/$kver" ]]; then
            assert_file_exists "$MOUNT_POINT/usr/lib/modules/$kver/initramfs.img" \
                "Initramfs should exist for kernel $kver"
        else
            skip "No kernel modules found"
        fi
    else
        skip "No /usr/lib/modules directory found"
    fi
}

@test "Plymouth theme should be set correctly if enabled" {
    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi
    
    run buildah run "$CONTAINER" -- sh -c "plymouth-set-default-theme 2>/dev/null || echo 'not-set'"
    
    if [[ "$output" == "not-set" ]]; then
        skip "plymouth-set-default-theme command not available"
    fi
    
    assert_output --partial "bgrt-better-luks"
}

@test "/var/tmp should be symlinked to /tmp" {
    run test -L "$MOUNT_POINT/var/tmp"
    assert_success "/var/tmp should be a symlink"
    
    run readlink "$MOUNT_POINT/var/tmp"
    assert_output "/tmp"
}

@test "Plymouth management scripts should have correct help output" {
    # Test setup-plymouth-theme help
    run buildah run "$CONTAINER" -- /usr/local/bin/setup-plymouth-theme help
    assert_success
    assert_output --partial "Usage:"
    assert_output --partial "set"
    assert_output --partial "enable"
    assert_output --partial "disable"
    
    # Test dracut-rebuild help
    run buildah run "$CONTAINER" -- /usr/local/bin/dracut-rebuild --help
    assert_success
    assert_output --partial "Usage:"
    assert_output --partial "KERNEL_VERSION"
}

@test "ENABLE_PLYMOUTH environment variable should match expected state" {
    local expected_state="${ENABLE_PLYMOUTH:-true}"
    
    # Check if environment variable is set in container
    run buildah run "$CONTAINER" -- printenv ENABLE_PLYMOUTH
    
    # If not set in container, use default 'true'
    local container_state="${output:-true}"
    
    echo "Expected Plymouth state: $expected_state" >&3
    echo "Container Plymouth state: $container_state" >&3
    
    [[ "$container_state" == "$expected_state" ]]
}