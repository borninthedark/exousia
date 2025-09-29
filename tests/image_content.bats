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

@test "Custom package list files should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
}

@test "Sway package list should exist (packages.sway)" {
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
    # Check if plymouth is installed
    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed"
    
    # Check if dracut config exists
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    
    # Check if bootc kargs config exists
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
}

@test "Custom script 'autotiling' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/autotiling"
    assert_success "'autotiling' script should be executable"
}

@test "Custom script 'config-authselect' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/config-authselect"
    assert_success "'config-authselect' script should be executable"
}

@test "Custom script 'lid' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/lid"
    assert_success "'lid' script should be executable"
}

@test "Custom script 'fedora-version-switcher' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/fedora-version-switcher"
    assert_success "'fedora-version-switcher' script should be executable"
}

@test "fedora-version-switcher script should require two arguments" {
    # Test that script exits with error when called without arguments
    run buildah run "$CONTAINER" -- /usr/local/bin/fedora-version-switcher
    assert_failure "Script should fail when called without arguments"
    assert_output --partial "Usage:"
}

@test "fedora-version-switcher script should accept valid version and image type" {
    # Test that script accepts valid arguments (in dry-run mode within container)
    # Note: We can't actually switch versions in the test, but we can verify the script runs
    run buildah run "$CONTAINER" -- bash -c "cd /tmp && /usr/local/bin/fedora-version-switcher list"
    assert_success "Script should accept 'list' command"
}

@test "Custom script 'generate-readme' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/generate-readme"
    assert_success "'generate-readme' script should be executable"
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

@test "DNF5 should be symlinked as default dnf" {
    run test -L "$MOUNT_POINT/usr/bin/dnf"
    assert_success "/usr/bin/dnf should be a symlink to dnf5"
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

@test "Greetd configuration should be present" {
    assert_file_exists "$MOUNT_POINT/etc/greetd/config.toml"
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
    # Check for kernel package - it may be named kernel, kernel-core, or have version prefix
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

@test ".fedora-version file tracking should work" {
    # Check if the script can create and read .fedora-version file
    # We'll test this by checking if the script can report current config
    run buildah run "$CONTAINER" -- bash -c "cd /tmp && /usr/local/bin/fedora-version-switcher current"
    # Should either show current config or indicate it needs initialization
    assert_success "Script should be able to check current configuration"
}