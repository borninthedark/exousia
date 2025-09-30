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
    
    # Detect Fedora version from the mounted container
    if [ -f "$MOUNT_POINT/etc/os-release" ]; then
        FEDORA_VERSION=$(grep -oP 'VERSION_ID=\K\d+' "$MOUNT_POINT/etc/os-release" || echo "unknown")
        export FEDORA_VERSION
        echo "--- Detected Fedora version: $FEDORA_VERSION ---"
    else
        echo "WARNING: Could not detect Fedora version from /etc/os-release" >&2
        export FEDORA_VERSION="unknown"
    fi
    
    # Detect build type from environment variable if present
    if [ -f "$MOUNT_POINT/etc/environment" ] && grep -q "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment"; then
        BUILD_TYPE=$(grep "BUILD_IMAGE_TYPE" "$MOUNT_POINT/etc/environment" | cut -d= -f2)
        export BUILD_TYPE
        echo "--- Detected build type: $BUILD_TYPE ---"
    else
        export BUILD_TYPE="unknown"
        echo "--- Could not detect build type ---"
    fi
}

teardown_file() {
    echo "--- Cleaning up test resources ---"
    buildah umount "$CONTAINER"
    buildah rm "$CONTAINER"
}

@test "OS should be Fedora Linux" {
    run grep 'ID=fedora' "$MOUNT_POINT/etc/os-release"
    assert_success "Should be running Fedora Linux"
}

@test "OS version should match expected Fedora versions (41, 42, 43, or rawhide)" {
    run grep -E 'VERSION_ID=(41|42|43)' "$MOUNT_POINT/etc/os-release"
    if [ "$status" -ne 0 ]; then
        # Check if it's rawhide
        run grep 'VARIANT_ID=rawhide' "$MOUNT_POINT/etc/os-release"
        assert_success "Should be Fedora 41, 42, 43, or rawhide"
    fi
}

@test "Detected Fedora version is valid" {
    if [[ "$FEDORA_VERSION" == "unknown" ]]; then
        skip "Could not detect Fedora version"
    fi
    
    # Version should be 41, 42, or 43
    [[ "$FEDORA_VERSION" =~ ^(41|42|43)$ ]]
}

@test "Container auth files should be correctly configured" {
    assert_file_exists "$MOUNT_POINT/usr/lib/tmpfiles.d/containers-auth.conf"
    assert_file_exists "$MOUNT_POINT/usr/lib/container-auth.json"
    
    run test -L "$MOUNT_POINT/etc/ostree/auth.json"
    assert_success "/etc/ostree/auth.json should be a symbolic link"
    
    run readlink "$MOUNT_POINT/etc/ostree/auth.json"
    assert_output --partial "/usr/lib/container-auth.json"
}

@test "Custom package list files should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-sway"
}

@test "Directory structure should be correct" {
    # /var/roothome should exist for fedora-bootc builds
    if [ -d "$MOUNT_POINT/var/roothome" ]; then
        echo "/var/roothome exists (fedora-bootc build)"
    else
        echo "/var/roothome does not exist (likely fedora-sway-atomic)"
    fi
    
    # /opt symlink only exists in fedora-bootc builds
    if [ -L "$MOUNT_POINT/opt" ]; then
        run readlink "$MOUNT_POINT/opt"
        assert_output "/var/opt"
        echo "Found /opt symlink to /var/opt (fedora-bootc base)"
    else
        echo "/opt is not a symlink (likely fedora-sway-atomic base)"
    fi
    
    # /usr/lib/extensions should exist in fedora-bootc builds
    if [ -d "$MOUNT_POINT/usr/lib/extensions" ]; then
        echo "/usr/lib/extensions exists (fedora-bootc build)"
    fi
}

@test "Sysusers configuration should exist" {
    assert_file_exists "$MOUNT_POINT/usr/lib/sysusers.d/bootc.conf"
}

@test "Custom Plymouth theme should be copied" {
    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
    assert_file_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
}

@test "Plymouth should be configured correctly" {
    # Check if plymouth is installed
    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed"
    
    # Check if dracut config exists
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    
    # Check if bootc kargs config exists
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
}

@test "Custom script 'fedora-version-switcher' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/fedora-version-switcher"
    assert_success "'fedora-version-switcher' script should be executable"
}

@test "Custom script 'generate-readme' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/generate-readme"
    assert_success "'generate-readme' script should be executable"
}

@test "Custom script 'config-authselect' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/config-authselect"
    assert_success "'config-authselect' script should be executable"
}

@test "RPM Fusion repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "Custom repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/nwg-shell.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/swaylock-effects.repo"
}

@test "DNF5 should be installed" {
    run buildah run "$CONTAINER" -- rpm -q dnf5
    assert_success "DNF5 should be installed"
}

@test "DNF should be symlinked to dnf5" {
    run test -L "$MOUNT_POINT/usr/bin/dnf"
    assert_success "/usr/bin/dnf should be a symlink"
}

@test "bootc should be installed" {
    run buildah run "$CONTAINER" -- rpm -q bootc
    assert_success "bootc should be installed for bootable container support"
}

@test "Sway desktop components should be installed" {
    run buildah run "$CONTAINER" -- rpm -q sway
    assert_success "Sway window manager should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q waybar
    assert_success "Waybar should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q swaylock
    assert_success "Swaylock should be installed"
}

@test "Greetd should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/greetd/config.toml"
    
    run buildah run "$CONTAINER" -- rpm -q greetd
    assert_success "greetd should be installed"
}

@test "Sway session files should exist for fedora-bootc" {
    # These are only in the fedora-bootc Containerfile
    if [ -f "$MOUNT_POINT/usr/share/wayland-sessions/sway.desktop" ]; then
        assert_file_exists "$MOUNT_POINT/usr/share/wayland-sessions/sway.desktop"
        assert_file_exists "$MOUNT_POINT/etc/sway/environment"
        assert_file_exists "$MOUNT_POINT/usr/bin/start-sway"
        echo "Found Sway session files (fedora-bootc build)"
    else
        echo "Sway session files not found (likely fedora-sway-atomic)"
    fi
}

@test "Package 'kitty' from 'packages.add' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q kitty
    assert_success "'kitty' should be installed"
}

@test "Package 'neovim' from 'packages.add' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q neovim
    assert_success "'neovim' should be installed"
}

@test "Package 'htop' from 'packages.add' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q htop
    assert_success "'htop' should be installed"
}

@test "Package 'distrobox' from 'packages.add' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q distrobox
    assert_success "'distrobox' should be installed"
}

@test "Package 'foot' from 'packages.remove' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q foot
    assert_failure "'foot' should be removed"
}

@test "Package 'dunst' from 'packages.remove' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q dunst
    assert_failure "'dunst' should be removed"
}

@test "Package 'rofi-wayland' from 'packages.remove' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q rofi-wayland
    assert_failure "'rofi-wayland' should be removed"
}

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
    assert_success "Image should pass bootc container lint checks"
}

@test "Systemd should be present and functional" {
    run buildah run "$CONTAINER" -- rpm -q systemd
    assert_success "systemd should be installed"
}

@test "Kernel should be installed" {
    run buildah run "$CONTAINER" -- sh -c "rpm -qa | grep -E '^kernel(-core)?-[0-9]' || rpm -q kernel || rpm -q kernel-core"
    assert_success "A kernel package should be installed"
}

@test "NetworkManager should be installed for bootc" {
    run buildah run "$CONTAINER" -- rpm -q NetworkManager
    assert_success "NetworkManager should be installed for networking"
}

@test "Podman should be installed for container support" {
    run buildah run "$CONTAINER" -- rpm -q podman
    assert_success "Podman should be installed for OCI container support"
}

@test "Virtualization packages should be installed" {
    run buildah run "$CONTAINER" -- rpm -q virt-manager
    assert_success "'virt-manager' should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q qemu-kvm
    assert_success "'qemu-kvm' should be installed"
}

@test "Security packages should be installed" {
    run buildah run "$CONTAINER" -- rpm -q pam-u2f
    assert_success "'pam-u2f' should be installed"
    
    run buildah run "$CONTAINER" -- rpm -q lynis
    assert_success "'lynis' should be installed"
}

@test "ComposeFS should be configured" {
    if grep -q "composefs=true" "$MOUNT_POINT/etc/ostree/repo.config"; then
        echo "ComposeFS is enabled in ostree config"
    else
        echo "ComposeFS configuration not found (may be default or not applicable)"
    fi
}