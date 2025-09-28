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
}

teardown_file() {
    echo "--- Cleaning up test resources ---"
    buildah umount "$CONTAINER"
    buildah rm "$CONTAINER"
}

@test "OS should be Fedora Linux 43" {
    run grep 'VERSION_ID=43' "$MOUNT_POINT/etc/os-release"
    assert_success
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

@test "Custom Plymouth theme should be copied" {
    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
}

@test "Custom script 'autotiling' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/autotiling"
    assert_success "'autotiling' script should be executable"
}

@test "Custom script 'config-authselect' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/config-authselect"
    assert_success "'config-authselect' script should be executable"
}

@test "RPM Fusion repositories should be configured" {
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "DNF5 should be installed" {
    run buildah run "$CONTAINER" -- rpm -q dnf5
    assert_success
}

@test "Package 'kitty' from 'packages.add' should be installed" {
    run buildah run "$CONTAINER" -- rpm -q kitty
    assert_success "'kitty' should be installed"
}

@test "Package 'dunst' from 'packages.remove' should NOT be installed" {
    run buildah run "$CONTAINER" -- rpm -q dunst
    assert_failure "'dunst' should be removed"
}

@test "Flathub remote should be added" {
    run buildah run "$CONTAINER" -- flatpak remotes --show-details
    assert_output --partial 'flathub'
}
