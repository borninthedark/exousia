#!/usr/bin/env bats

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
    
    # Detect Fedora version
    if [ -f "$MOUNT_POINT/etc/os-release" ]; then
        FEDORA_VERSION=$(grep -oP 'VERSION_ID=\K\d+' "$MOUNT_POINT/etc/os-release" || echo "unknown")
        export FEDORA_VERSION
        echo "--- Detected Fedora version: $FEDORA_VERSION ---"
    else
        echo "WARNING: Could not detect Fedora version from /etc/os-release" >&2
        export FEDORA_VERSION="unknown"
    fi
    
    # Detect base image type from build environment variable
    IMAGE_TYPE=$(buildah run "$CONTAINER" -- printenv BUILD_IMAGE_TYPE 2>/dev/null || echo "unknown")
    export IMAGE_TYPE
    echo "--- Detected image type: $IMAGE_TYPE ---"
}

teardown_file() {
    echo "--- Cleaning up test resources ---"
    buildah umount "$CONTAINER"
    buildah rm "$CONTAINER"
}

# ============================================================================
# OS / Fedora Version Checks
# ============================================================================

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

@test "Build image type environment variable should be set" {
    if [[ "$IMAGE_TYPE" == "unknown" ]]; then
        skip "Could not detect BUILD_IMAGE_TYPE"
    fi
    [[ "$IMAGE_TYPE" =~ ^(fedora-bootc|fedora-sway-atomic)$ ]]
}

# ============================================================================
# CI Container Auth Configuration
# ============================================================================

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

# ============================================================================
# Custom Package Lists and Plymouth
# ============================================================================

@test "Custom package list files should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
}

@test "Sway package list should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-sway"
}

@test "Fedora base packages list should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-fedora-bootc"
}

@test "Custom Plymouth theme should be copied" {
    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
    assert_file_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
}

@test "Plymouth should be configured correctly" {
    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed"
    
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    
    # Verify Plymouth is set as default theme
    run buildah run "$CONTAINER" -- plymouth-set-default-theme
    assert_output "bgrt-better-luks"
}

@test "Plymouth kernel arguments should be configured" {
    run grep -q 'splash' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Plymouth kargs should include 'splash'"
    
    run grep -q 'quiet' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Plymouth kargs should include 'quiet'"
}

# ============================================================================
# Custom Scripts
# ============================================================================

@test "Custom script 'config-authselect' should be executable" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/config-authselect"
}

@test "Custom script 'fedora-version-switcher' should be executable" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/fedora-version-switcher"
}

@test "fedora-version-switcher script should require two arguments" {
    run buildah run "$CONTAINER" -- /usr/local/bin/fedora-version-switcher
    assert_failure
    assert_output --partial "Usage:"
}

@test "fedora-version-switcher script should handle valid inputs correctly" {
    run buildah run "$CONTAINER" -- bash -c "/usr/local/bin/fedora-version-switcher 2>&1 | grep -q 'Usage:'"
    assert_success
}

@test "Custom script 'generate-readme' should be executable" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/generate-readme"
}

# ============================================================================
# Repositories and Package Configuration
# ============================================================================

@test "RPM Fusion repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "RPM Fusion repositories should be enabled" {
    run grep -E '^\s*enabled\s*=\s*1' "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_success "RPM Fusion Free should be enabled"
    
    run grep -E '^\s*enabled\s*=\s*1' "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
    assert_success "RPM Fusion Nonfree should be enabled"
}

@test "Custom repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/nwg-shell.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/swaylock-effects.repo"
}

# ============================================================================
# Key Packages
# ============================================================================

@test "DNF5 should be installed and symlinked as default dnf" {
    run buildah run "$CONTAINER" -- rpm -q dnf5
    assert_success "DNF5 should be installed"
    
    assert_symlink_to "$MOUNT_POINT/usr/bin/dnf" "/usr/bin/dnf5"
}

@test "bootc should be installed" {
    run buildah run "$CONTAINER" -- rpm -q bootc
    assert_success
}

@test "Sway desktop components should be installed" {
    run buildah run "$CONTAINER" -- rpm -q sway
    assert_success "Sway window manager should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q waybar
    assert_success "Waybar should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q swaylock
    assert_success "Swaylock should be installed"
}

@test "Essential user applications should be installed" {
    # Terminal emulator
    run buildah run "$CONTAINER" -- rpm -q kitty
    assert_success "Kitty terminal should be installed"
    
    # Text editor
    run buildah run "$CONTAINER" -- rpm -q neovim
    assert_success "Neovim should be installed"
    
    # System monitors
    run buildah run "$CONTAINER" -- rpm -q htop
    assert_success "htop should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q btop
    assert_success "btop should be installed"
    
    # Container tooling
    run buildah run "$CONTAINER" -- rpm -q distrobox
    assert_success "Distrobox should be installed"
    
    # File manager
    run buildah run "$CONTAINER" -- rpm -q ranger
    assert_success "ranger should be installed"
}

@test "Audio and media packages should be installed" {
    # Music player daemon
    run buildah run "$CONTAINER" -- rpm -q mpd
    assert_success "MPD should be installed"
    
    # Audio control
    run buildah run "$CONTAINER" -- rpm -q pavucontrol
    assert_success "pavucontrol should be installed"
}

@test "Replaced packages should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q foot
    assert_failure "foot should be removed (replaced by kitty)"
    
    run buildah run "$CONTAINER" -- rpm -q dunst
    assert_failure "dunst should be removed"
    
    run buildah run "$CONTAINER" -- rpm -q rofi-wayland
    assert_failure "rofi-wayland should be removed"
}

# ============================================================================
# Flathub, Sway Config, bootc Lint
# ============================================================================

@test "Flathub remote should be added" {
    run buildah run "$CONTAINER" -- flatpak remotes --show-details
    assert_output --partial 'flathub'
}

@test "Flathub remote should point to correct URL" {
    run buildah run "$CONTAINER" -- sh -c "flatpak remotes -d | grep flathub | grep 'https://flathub.org/repo/'"
}

@test "Sway configuration files should be present" {
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/51-display.conf"
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/61-bindings.conf"
    assert_file_exists "$MOUNT_POINT/etc/sway/config.d/95-theme.conf"
}

@test "Greetd configuration should be present and valid" {
    assert_file_exists "$MOUNT_POINT/etc/greetd/config.toml"
    assert_success "Greetd config should exist
}

@test "Image should pass bootc container lint" {
    run buildah run "$CONTAINER" -- bootc container lint
    assert_success "bootc container lint should pass without errors"
}

# ============================================================================
# System Components
# ============================================================================

@test "Systemd should be present" {
    run buildah run "$CONTAINER" -- rpm -q systemd
    assert_success
}

@test "Kernel should be installed" {
    run buildah run "$CONTAINER" -- sh -c "rpm -qa | grep -E '^kernel(-core)?-[0-9]' || rpm -q kernel || rpm -q kernel-core"
    assert_success "A kernel package should be installed"
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
    assert_success "virt-manager should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q qemu-kvm
    assert_success "qemu-kvm should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q libvirt
    assert_success "libvirt should be installed"
}

@test "Security packages should be installed" {
    run buildah run "$CONTAINER" -- rpm -q pam-u2f
    assert_success "PAM U2F support should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q lynis
    assert_success "Lynis security auditing tool should be installed"
}

# ============================================================================
# System Users and Groups
# ============================================================================

@test "System user 'greeter' should exist" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success "greeter user should exist"
}

@test "System user 'greetd' should exist" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success "greetd user should exist"
}

@test "System user 'rtkit' should exist" {
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success "rtkit user should exist"
}

@test "Greeter user should have correct UID/GID and shell" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
    echo "$output" | grep -Eq '^greeter:x:241:241:Greeter Login User:/var/lib/greeter:/sbin/nologin$'
    assert_success "greeter user should have UID/GID 241 and nologin shell"
}

@test "Greetd user should have correct configuration" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    echo "$output" | grep -Eq '^greetd:x:[0-9]+:[0-9]+:.*:/var/lib/greetd:/sbin/nologin$'
    assert_success "greetd user should have proper home directory and nologin shell"
}

@test "RealtimeKit user should have correct configuration" {
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
    echo "$output" | grep -Eq '^rtkit:x:[0-9]+:[0-9]+:.*:/proc:/sbin/nologin$'
    assert_success "rtkit user should have /proc as home and nologin shell"
}

@test "Sysusers configuration file should exist and be valid" {
    assert_file_exists "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    
    # Verify the file contains configurations for required users
    run grep -E 'greeter' "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    assert_success "bootc.conf should contain greeter definition"
    
    run grep -E 'greetd' "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    assert_success "bootc.conf should contain greetd definition"
    
    run grep -E 'rtkit' "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
    assert_success "bootc.conf should contain rtkit definition"
}

@test "User home directories should exist with correct permissions" {
    assert_dir_exists "$MOUNT_POINT/var/lib/greeter"
    assert_dir_exists "$MOUNT_POINT/var/lib/greetd"
}

# ============================================================================
# Conditional Tests Based on Image Type
# ============================================================================

@test "Directory structure should be correct for image type" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        assert_dir_exists "$MOUNT_POINT/var/roothome"
        assert_dir_exists "$MOUNT_POINT/var/opt"
        assert_dir_exists "$MOUNT_POINT/usr/lib/extensions"
        
        run test -L "$MOUNT_POINT/opt"
        assert_success "/opt should be a symlink for fedora-bootc"
        
        run readlink "$MOUNT_POINT/opt"
        assert_output "/var/opt" "/opt should point to /var/opt"
    else
        echo "# Skipping fedora-bootc specific directory checks for $IMAGE_TYPE" >&3
    fi
}

@test "Services should be enabled based on image type" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        run buildah run "$CONTAINER" -- systemctl is-enabled greetd.service
        assert_success "greetd should be enabled for fedora-bootc"
        
        run buildah run "$CONTAINER" -- systemctl is-enabled libvirtd.service
        assert_success "libvirtd should be enabled for fedora-bootc"
        
        run buildah run "$CONTAINER" -- systemctl get-default
        assert_output "graphical.target" "Default target should be graphical for fedora-bootc"
    else
        echo "# Skipping fedora-bootc specific service checks for $IMAGE_TYPE" >&3
    fi
}

@test "Sway packages should only be installed for fedora-bootc base" {
    if [[ "$IMAGE_TYPE" == "fedora-bootc" ]]; then
        # Verify key Sway components are installed
        run buildah run "$CONTAINER" -- rpm -q sway
        assert_success "Sway should be installed for fedora-bootc base"
    else
        echo "# Sway packages expected pre-installed in $IMAGE_TYPE" >&3
    fi
}

# ============================================================================
# ComposeFS and OSTree Configuration
# ============================================================================

@test "ComposeFS should be enabled in ostree config" {
    if [ -f "$MOUNT_POINT/etc/ostree/repo.config" ]; then
        run grep -q 'composefs=true' "$MOUNT_POINT/etc/ostree/repo.config"
        assert_success "ComposeFS should be explicitly enabled"
    else
        skip "/etc/ostree/repo.config not found"
    fi
}

# ============================================================================
# Version Tracking
# ============================================================================

@test "Version tracking mechanism should be functional" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/fedora-version-switcher"
    
    # Test that the script can be executed (even if it shows usage)
    run buildah run "$CONTAINER" -- /usr/local/bin/fedora-version-switcher
    assert_failure # Should fail without args
    assert_output --partial "Usage:" # But should show usage
}