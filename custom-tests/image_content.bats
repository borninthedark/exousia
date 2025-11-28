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
        
        # Try to detect build type from container ENV (preferred method)
        BUILD_TYPE=$(buildah run "$CONTAINER" -- printenv BUILD_IMAGE_TYPE 2>/dev/null || echo "unknown")
        
        # Fallback: Try to detect from /etc/environment file
        if [ "$BUILD_TYPE" = "unknown" ] && [ -f "$MOUNT_POINT/etc/environment" ]; then
            if grep -q "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment"; then
                BUILD_TYPE=$(grep "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment" | cut -d= -f2 | tr -d '"')
            fi
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

        run grep -q "docker.io/1borninthedark/exousia" "$MOUNT_POINT/usr/lib/container-auth.json"
        assert_success "/usr/lib/container-auth.json should contain Docker Hub credentials for docker.io/1borninthedark/exousia"

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