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
    
    # Detect base image type (fedora-bootc or fedora-sway-atomic)
    if buildah run "$CONTAINER" -- rpm -q sway 2>/dev/null; then
        BASE_IMAGE_TYPE="fedora-sway-atomic"
    else
        BASE_IMAGE_TYPE="fedora-bootc"
    fi
    export BASE_IMAGE_TYPE
    echo "--- Detected base image type: $BASE_IMAGE_TYPE ---"
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

@test "Base image type detection is valid" {
    [[ "$BASE_IMAGE_TYPE" =~ ^(fedora-bootc|fedora-sway-atomic)$ ]]
    echo "Base image type: $BASE_IMAGE_TYPE"
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
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-desktop"
}

@test "Fedora base packages list should exist" {
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-fedora-bootc"
}

@test "Custom Plymouth theme should be copied" {
    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
    assert_file_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
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

@test "Sway desktop should be installed" {
    run buildah run "$CONTAINER" -- rpm -q sway
    assert_success "Sway window manager should be installed"
}

@test "Desktop packages should be installed correctly based on base image type" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        # When using fedora-bootc base, desktop packages should be installed
        run buildah run "$CONTAINER" -- rpm -q greetd
        assert_success "greetd should be installed on fedora-bootc base"
        
        run buildah run "$CONTAINER" -- rpm -q greetd-tuigreet
        assert_success "greetd-tuigreet should be installed on fedora-bootc base"
        
        run buildah run "$CONTAINER" -- rpm -q waybar
        assert_success "waybar should be installed on fedora-bootc base"
    else
        echo "Skipping desktop package tests for fedora-sway-atomic (pre-installed)"
    fi
}

@test "Graphical target should be enabled for fedora-bootc base" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        run test -L "$MOUNT_POINT/etc/systemd/system/default.target"
        assert_success "default.target should be a symlink"
        
        run readlink "$MOUNT_POINT/etc/systemd/system/default.target"
        assert_output --partial "graphical.target"
    else
        skip "Graphical target test only applies to fedora-bootc base"
    fi
}

@test "greetd service should be enabled for fedora-bootc base" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        run test -L "$MOUNT_POINT/etc/systemd/system/display-manager.service"
        if [ "$status" -eq 0 ]; then
            assert_success "display-manager.service should be enabled"
        else
            # Check alternative location
            run test -L "$MOUNT_POINT/etc/systemd/system/multi-user.target.wants/greetd.service"
            assert_success "greetd.service should be enabled"
        fi
    else
        skip "greetd enablement test only applies to fedora-bootc base"
    fi
}

@test "libvirtd service should be enabled for fedora-bootc base" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        run test -L "$MOUNT_POINT/etc/systemd/system/multi-user.target.wants/libvirtd.service"
        assert_success "libvirtd.service should be enabled"
    else
        skip "libvirtd enablement test only applies to fedora-bootc base"
    fi
}

@test "systemd-resolved service should be enabled for fedora-bootc base" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        run test -L "$MOUNT_POINT/etc/systemd/system/multi-user.target.wants/systemd-resolved.service"
        if [ "$status" -ne 0 ]; then
            # Check alternative location
            run test -L "$MOUNT_POINT/etc/systemd/system/dbus-org.freedesktop.resolve1.service"
            assert_success "systemd-resolved.service should be enabled"
        else
            assert_success "systemd-resolved.service should be enabled"
        fi
    else
        skip "systemd-resolved enablement test only applies to fedora-bootc base"
    fi
}

@test "NetworkManager service should be enabled for fedora-bootc base" {
    if [[ "$BASE_IMAGE_TYPE" == "fedora-bootc" ]]; then
        run test -L "$MOUNT_POINT/etc/systemd/system/multi-user.target.wants/NetworkManager.service"
        if [ "$status" -ne 0 ]; then
            # Check alternative location
            run test -L "$MOUNT_POINT/etc/systemd/system/dbus-org.freedesktop.nm-dispatcher.service"
            assert_success "NetworkManager.service should be enabled"
        else
            assert_success "NetworkManager.service should be enabled"
        fi
    else
        skip "NetworkManager enablement test only applies to fedora-bootc base"
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

@test "Plymouth should be installed" {
    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed for boot splash"
}

@test "Plymouth dracut configuration should exist" {
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    
    run grep -q "add_dracutmodules.*plymouth" "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    assert_success "Plymouth should be added to dracut modules"
}

@test "Plymouth kernel arguments should be configured" {
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    
    run grep -q "splash" "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Plymouth kargs should include 'splash'"
    
    run grep -q "quiet" "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Plymouth kargs should include 'quiet'"
}

@test "Plymouth default theme should be set to bgrt-better-luks" {
    run buildah run "$CONTAINER" -- plymouth-set-default-theme --list
    assert_output --partial "bgrt-better-luks"
}

@test "Initramfs should exist in kernel modules directory" {
    run sh -c "ls $MOUNT_POINT/usr/lib/modules/*/initramfs.img"
    assert_success "Initramfs should be present after dracut rebuild"
}

@test "/var/tmp should be symlinked to /tmp for dracut" {
    run test -L "$MOUNT_POINT/var/tmp"
    assert_success "/var/tmp should be a symlink to /tmp"
}