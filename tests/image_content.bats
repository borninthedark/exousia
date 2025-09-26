#!/usr/bin/env bats

# --- Tests ---

@test "OS should be Fedora Linux 43" {
  run grep "Fedora Linux 43" "$MOUNT_POINT/etc/os-release"
  assert_success
}

@test "Custom package list files should exist" {
  assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
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
}

@test "DNF5 should be installed" {
  run buildah run "$CONTAINER" -- dnf5 --version
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
  run buildah run "$CONTAINER" -- flatpak remotes --show-details | grep -q 'flathub'
  assert_success
}
