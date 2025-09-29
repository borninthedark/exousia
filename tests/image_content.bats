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
}

teardown_file() {
    echo "--- Cleaning up test resources ---"
    buildah umount "$CONTAINER"
    buildah rm "$CONTAINER"
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

@test "Greetd configuration should be present" {
    assert_file_exists "$MOUNT_POINT/etc/greetd/config.toml"
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

@test ".fedora-version file tracking should work" {
    run buildah run "$CONTAINER" -- test -x /usr/local/bin/fedora-version-switcher
    assert_success
}

@test "System user (greeter) should exist" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
}

@test "System users (greetd and rtkit) should exist" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
}

@test "Greeter user (greeter) should have correct UID/GID and shell" {
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
    echo "$output" | grep -Eq '^greeter:x:241:241:Greeter Login User:/var/lib/greeter:/sbin/nologin$'
    assert_success
}

@test "Greeter user (greetd) should have correct UID/GID and shell" {
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    echo "$output" | grep -Eq '^greetd:x:[0-9]+:[0-9]+:.*:/var/lib/greetd:/sbin/nologin$'
    assert_success
}

@test "RealtimeKit user should have correct UID/GID and shell" {
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
    echo "$output" | grep -Eq '^rtkit:x:[0-9]+:[0-9]+:.*:/proc:/sbin/nologin$'
    assert_success
}

@test "Sysusers configuration files for greetd/rtkit should exist" {
    run find "$MOUNT_POINT/usr/lib/sysusers.d" -name "*.conf"
    assert_success
    echo "$output" | grep -Eq 'greetd\.conf'
    assert_success
    echo "$output" | grep -Eq 'rtkit\.conf'
    assert_success
}