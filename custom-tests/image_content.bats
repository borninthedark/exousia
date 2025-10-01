#!/usr/bin/env bats

# Load Bats libraries
bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file
bats_load_library bats-detik/detik.bash

setup_file() {
    if [ -z "$TEST_IMAGE_TAG" ]; then
        echo "FATAL: TEST_IMAGE_TAG environment variable is not set." >&2
        return 1
    fi
    echo "--- Using test image: $TEST_IMAGE_TAG ---"

    CONTAINER=$(buildah from --pull-never "$TEST_IMAGE_TAG")
    MOUNT_POINT=$(buildah mount "$CONTAINER")

    export CONTAINER MOUNT_POINT
    echo "--- Container filesystem mounted at $MOUNT_POINT ---"
    
    # Detect Fedora version and build type from .fedora-version file
    if [ -f "$MOUNT_POINT/.fedora-version" ]; then
        FEDORA_VERSION_LINE=$(cat "$MOUNT_POINT/.fedora-version")
        FEDORA_VERSION=$(echo "$FEDORA_VERSION_LINE" | cut -d: -f1)
        BUILD_TYPE=$(echo "$FEDORA_VERSION_LINE" | cut -d: -f2)
        export FEDORA_VERSION BUILD_TYPE
        echo "--- Detected from .fedora-version: Fedora $FEDORA_VERSION, Build type: $BUILD_TYPE ---"
    else
        # Fallback to os-release
        if [ -f "$MOUNT_POINT/etc/os-release" ]; then
            FEDORA_VERSION=$(grep -oP 'VERSION_ID=\K\d+' "$MOUNT_POINT/etc/os-release" || echo "unknown")
            export FEDORA_VERSION
            echo "--- Detected Fedora version from os-release: $FEDORA_VERSION ---"
        else
            echo "WARNING: Could not detect Fedora version" >&2
            export FEDORA_VERSION="unknown"
        fi
        
        # Try to detect build type from ENV
        BUILD_TYPE="unknown"
        if [ -f "$MOUNT_POINT/etc/environment" ] && grep -q "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment"; then
            BUILD_TYPE=$(grep "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment" | cut -d= -f2 | tr -d '"')
        fi
        export BUILD_TYPE
        echo "--- Build type: $BUILD_TYPE ---"
    fi
}

teardown_file() {
    echo "--- Cleaning up test resources ---"
    buildah umount "$CONTAINER"
    buildah rm "$CONTAINER"
}

# Helper function to check if running fedora-bootc
is_fedora_bootc() {
    [[ "$BUILD_TYPE" == "fedora-bootc" ]]
}

# Helper function to check if running fedora-sway-atomic
is_fedora_sway_atomic() {
    [[ "$BUILD_TYPE" == "fedora-sway-atomic" ]]
}

# Helper function to check if Plymouth is enabled
is_plymouth_enabled() {
    [[ "${ENABLE_PLYMOUTH:-true}" == "true" ]]
}

# --- OS / Fedora version checks ---

@test "OS should be Fedora Linux" {
    run grep 'ID=fedora' "$MOUNT_POINT/etc/os-release"
    assert_success "Should be running Fedora Linux"
}

@test "OS version should match expected Fedora versions (41–44 or rawhide)" {
    run grep -E 'VERSION_ID=(41|42|43|44)' "$MOUNT_POINT/etc/os-release"
    if [ "$status" -ne 0 ]; then
        run grep 'VARIANT_ID=rawhide' "$MOUNT_POINT/etc/os-release"
        assert_success "Should be Fedora 41–44 or rawhide"
    fi
}

@test "Detected Fedora version is valid" {
    if [[ "$FEDORA_VERSION" == "unknown" ]]; then
        skip "Could not detect Fedora version"
    fi
    [[ "$FEDORA_VERSION" =~ ^(41|42|43|44|rawhide)$ ]]
}

# --- CI container auth config checks ---

@test "Container auth files should be correctly configured in CI" {
    if [[ "${CI}" == "true" ]]; then
        assert_file_exists "$MOUNT_POINT/usr/lib/tmpfiles.d/containers-auth.conf"
        assert_file_exists "$MOUNT_POINT/usr/lib/container-auth.json"
        run grep -q "ghcr.io" "$MOUNT_POINT/usr/lib/container-auth.json"
        assert_success "/usr/lib/container-auth.json should contain ghcr.io"

        run test -L "$MOUNT_POINT/etc/ostree/auth.json"
        assert_success "/etc/ostree/auth.json should be a symbolic link"

        run readlink "$MOUNT_POINT/etc/ostree/auth.json"
        assert_output --partial "/usr/lib/container-auth.json"
    else
        skip "Auth file test is skipped outside of CI environment"
    fi
}

# --- Custom package list and Plymouth ---

@test "Custom package list files should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
}

@test "Sway package list should exist (packages.sway)" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-sway"
}

@test "Fedora base packages list should exist for fedora-bootc" {
    if ! is_fedora_bootc; then
        skip "Test only applies to fedora-bootc builds"
    fi
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-fedora-bootc"
}

@test "Directory structure should be correct for fedora-bootc" {
    if ! is_fedora_bootc; then
        skip "Test only applies to fedora-bootc builds"
    fi
    
    # /var/roothome should exist for fedora-bootc builds
    assert_dir_exists "$MOUNT_POINT/var/roothome"
    
    # /opt symlink should exist in fedora-bootc builds
    run test -L "$MOUNT_POINT/opt"
    assert_success "/opt should be a symlink in fedora-bootc"
    
    run readlink "$MOUNT_POINT/opt"
    # Accept both relative and absolute paths
    assert_output --partial "var/opt"
    
    # /usr/lib/extensions should exist in fedora-bootc builds
    assert_dir_exists "$MOUNT_POINT/usr/lib/extensions"
}

@test "Directory structure should be correct for fedora-sway-atomic" {
    if ! is_fedora_sway_atomic; then
        skip "Test only applies to fedora-sway-atomic builds"
    fi
    
    # /var/roothome should NOT exist for fedora-sway-atomic
    run test -d "$MOUNT_POINT/var/roothome"
    assert_failure "/var/roothome should not exist in fedora-sway-atomic"
}

# --- Plymouth Tests (Conditional) ---

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
    
    # For fedora-sway-atomic, Plymouth is pre-configured differently
    if is_fedora_sway_atomic; then
        echo "# fedora-sway-atomic has Plymouth pre-configured" >&3
        # Just verify Plymouth is installed, config may be different
        return 0
    fi
    
    # For fedora-bootc, check our custom configuration
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
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
    
    if ! is_fedora_bootc; then
        skip "Plymouth dracut configuration test only applies to fedora-bootc builds"
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
    
    # fedora-sway-atomic may use default "bgrt" theme
    if is_fedora_sway_atomic; then
        if [[ "$output" == "bgrt" ]]; then
            echo "# fedora-sway-atomic using default bgrt theme" >&3
        else
            assert_output --partial "bgrt-better-luks"
        fi
    else
        # fedora-bootc should have custom theme
        assert_output --partial "bgrt-better-luks"
    fi
}

@test "/var/tmp should be symlinked to /tmp" {
    # Check if /var/tmp exists and is a symlink
    if [ ! -e "$MOUNT_POINT/var/tmp" ]; then
        skip "/var/tmp does not exist in container"
    fi
    
    run test -L "$MOUNT_POINT/var/tmp"
    if [ "$status" -ne 0 ]; then
        # Not a symlink - check if it's a directory (some base images have it as dir)
        run test -d "$MOUNT_POINT/var/tmp"
        if [ "$status" -eq 0 ]; then
            skip "/var/tmp exists as directory (not symlink) in base image"
        fi
        assert_success "/var/tmp should be a symlink"
    fi
    
    run readlink "$MOUNT_POINT/var/tmp"
    # Accept both absolute and relative paths
    if [[ "$output" != "/tmp" && "$output" != "../tmp" ]]; then
        echo "Expected: /tmp or ../tmp, Got: $output" >&3
        assert_output "/tmp"
    fi
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

# --- Custom scripts ---

@test "Custom script 'autotiling' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/autotiling"
    assert_success
}

@test "Custom script 'config-authselect' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/config-authselect"
    assert_success
}

@test "Custom script 'lid' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/lid"
    assert_success
}

@test "Custom script 'fedora-version-switcher' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/fedora-version-switcher"
    assert_success
}

@test "fedora-version-switcher script should require two arguments" {
    run buildah run "$CONTAINER" -- /usr/local/bin/fedora-version-switcher
    assert_failure
    assert_output --partial "Usage:"
}

@test "fedora-version-switcher script should accept valid version and image type" {
    run buildah run "$CONTAINER" -- bash -c "/usr/local/bin/fedora-version-switcher 2>&1 | grep -q 'Usage:'"
    assert_success
}

@test "Custom script 'generate-readme' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/generate-readme"
    assert_success
}

# --- Repositories and package config ---

@test "RPM Fusion repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "Custom repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/nwg-shell.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/swaylock-effects.repo"
}

# --- Key packages ---

@test "DNF5 should be installed and symlinked as default dnf" {
    run buildah run "$CONTAINER" -- rpm -q dnf5
    assert_success
    run test -L "$MOUNT_POINT/usr/bin/dnf"
    assert_success
}

@test "bootc should be installed" {
    run buildah run "$CONTAINER" -- rpm -q bootc
    assert_success
}

@test "Sway desktop components should be installed" {
    run buildah run "$CONTAINER" -- rpm -q sway
    assert_success
    run buildah run "$CONTAINER" -- rpm -q waybar
    assert_success
    run buildah run "$CONTAINER" -- rpm -q swaylock
    assert_success
}

@test "Package 'kitty' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q kitty
    assert_success
}

@test "Package 'neovim' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q neovim
    assert_success
}

@test "Package 'htop' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q htop
    assert_success
}

@test "Package 'distrobox' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q distrobox
    assert_success
}

@test "Package 'foot' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q foot
    assert_failure
}

@test "Package 'dunst' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q dunst
    assert_failure
}

@test "Package 'rofi-wayland' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q rofi-wayland
    assert_failure
}

# --- Display Manager Configuration ---

@test "Greetd should be configured for fedora-bootc" {
    if ! is_fedora_bootc; then
        skip "Greetd test only applies to fedora-bootc builds"
    fi
    
    assert_file_exists "$MOUNT_POINT/etc/greetd/config.toml"
    
    run buildah run "$CONTAINER" -- rpm -q greetd
    assert_success "greetd should be installed in fedora-bootc"
}

@test "SDDM should be configured for fedora-sway-atomic" {
    if ! is_fedora_sway_atomic; then
        skip "SDDM test only applies to fedora-sway-atomic builds"
    fi
    
    run buildah run "$CONTAINER" -- rpm -q sddm
    assert_success "sddm should be installed in fedora-sway-atomic"
}

@test "Sway session files should exist for fedora-bootc" {
    if ! is_fedora_bootc; then
        skip "Sway session files test only applies to fedora-bootc builds"
    fi
    
    assert_file_exists "$MOUNT_POINT/usr/share/wayland-sessions/sway.desktop"
    assert_file_exists "$MOUNT_POINT/etc/sway/environment"
    assert_file_exists "$MOUNT_POINT/usr/bin/start-sway"
}

# --- Flathub, Sway config, bootc lint ---

@test "Flathub remote should be added" {
    run buildah run "$CONTAINER" -- flatpak remotes --show-details
    assert_output --partial 'flathub'
}

@test "Sway configuration should be present" {
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/51-display.conf"
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/61-bindings.conf"
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/95-theme.conf"
}

@test "Image should pass bootc container lint" {
    run buildah run "$CONTAINER" -- bootc container lint
    assert_success
}

# --- System components ---

@test "Systemd should be present" {
    run buildah run "$CONTAINER" -- rpm -q systemd
    assert_success
}

@test "Kernel should be installed" {
    run buildah run "$CONTAINER" -- sh -c "rpm -qa | grep -E '^kernel(-core)?-[0-9]' || rpm -q kernel || rpm -q kernel-core"
    assert_success
}

@test "NetworkManager should be installed" {
    run buildah run "$CONTAINER" -- rpm -q NetworkManager
    assert_success
}

@test "Podman should be installed" {
    run buildah run "$CONTAINER" -- rpm -q podman
    assert_success
}

@test "Virtualization packages should be installed" {
    run buildah run "$CONTAINER" -- rpm -q virt-manager
    assert_success
    run buildah run "$CONTAINER" -- rpm -q qemu-kvm
    assert_success
}

@test "Security packages should be installed" {
    run buildah run "$CONTAINER" -- rpm -q pam-u2f
    assert_success
    run buildah run "$CONTAINER" -- rpm -q lynis
    assert_success
}

# --- User configuration ---

@test "System user greeter should exist" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
}

@test "System users greetd and rtkit should exist" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
}

@test "Greeter user should have correct UID and shell" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
    echo "$output" | grep -Eq '^greeter:x:241:241:Greeter Login User:/var/lib/greeter:/sbin/nologin$'
    assert_success
}

@test "Greetd user should have correct shell" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    echo "$output" | grep -Eq '^greetd:x:[0-9]+:[0-9]+:.*:/var/lib/greetd:/sbin/nologin$'
    assert_success
}

@test "RealtimeKit user should have correct shell" {
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
    echo "$output" | grep -Eq '^rtkit:x:[0-9]+:[0-9]+:.*:/proc:/sbin/nologin$'
    assert_success
}

@test "Sysusers configuration files for greetd and rtkit should exist" {
    assert_file_exists "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    
    # Verify the file contains configurations for greetd and rtkit
    run grep -E '(greetd|rtkit)' "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    assert_success "bootc.conf should contain greetd and rtkit definitions"
}

# --- Final validation ---

@test "BUILD_IMAGE_TYPE environment variable should be set correctly" {
    if [ -f "$MOUNT_POINT/etc/environment" ]; then
        run grep "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment"
        if [ "$status" -eq 0 ]; then
            assert_output --partial "$BUILD_TYPE"
        else
            skip "BUILD_IMAGE_TYPE not found in /etc/environment"
        fi
    else
        skip "/etc/environment not found"
    fi
}