#!/usr/bin/env bats

#
# Bats tests for the custom fedora-bootc image.
# These tests mount the container filesystem to verify its contents based on the Containerfile.
#

# -- Test Setup & Teardown -----------------------------------------------------
# This function runs once before all tests. It builds the image,
# creates a temporary container, and mounts its filesystem for inspection.
setup_file() {
 # Define a unique name for the test image to avoid conflicts.
TEST_IMAGE="localhost/custom-bootc-bats-test:latest"
echo "--- Building test image: $TEST_IMAGE ---"
 
# Build the container image from the Containerfile in the repo root.
buildah bud --quiet --tag "$TEST_IMAGE" .

# Create a container from the new image.
CONTAINER=$(buildah from "$TEST_IMAGE")

# Use the image tag passed from the CI workflow environment variable.
echo "--- Using test image: $TEST_IMAGE_TAG ---"
 
# Create a container directly from the image already built by the workflow.
# The --pull-never flag ensures it uses the local image.
CONTAINER=$(buildah from --pull-never "$TEST_IMAGE_TAG")

}

# This function runs once after all tests. It cleans up the
# mount point, container, and test image.
teardown_file() {
  echo "--- Cleaning up test resources ---"
  buildah umount "$CONTAINER"
  buildah rm "$CONTAINER"
}

# -- OS & File Content Tests ----------------------------------------------------

@test "OS should be Fedora Linux 43" {
  # Validates the 'FROM' line in the Containerfile.
  run grep 'VERSION_ID=43' "$MOUNT_POINT/etc/os-release"
  assert_success
}

@test "Custom package list files should exist" {
  # Validates the COPY commands for package lists.
  assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
  assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
}

@test "Custom Plymouth theme should be copied" {
  # Validates the COPY command for the plymouth theme.
  assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
}

@test "Custom script 'autotiling' should be executable" {
  # Validates 'COPY --chmod=0755 custom-scripts/'.
  run test -x "$MOUNT_POINT/usr/local/bin/autotiling"
  assert_success "'autotiling' script should be executable"
}

@test "Custom script 'config-authselect' should be executable" {
  # Validates 'COPY --chmod=0755 custom-scripts/'.
  run test -x "$MOUNT_POINT/usr/local/bin/config-authselect"
  assert_success "'config-authselect' script should be executable"
}

# -- Repository & Package Tests -----------------------------------------------

@test "RPM Fusion repositories should be configured" {
  # Validates the installation of rpmfusion releases.
  assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
  assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "DNF5 should be installed" {
  # Validates the 'dnf install -y dnf5' command.
  run buildah run "$CONTAINER" -- rpm -q dnf5
  assert_success
}

@test "Package 'kitty' from 'packages.add' should be installed" {
  # Validates that 'kitty' from the custom list is installed.
  run buildah run "$CONTAINER" -- rpm -q kitty
  assert_success "'kitty' should be installed"
}

@test "Package 'dunst' from 'packages.remove' should NOT be installed" {
  # Validates that 'dunst' from the custom list is removed.
  run buildah run "$CONTAINER" -- rpm -q dunst
  assert_failure "'dunst' should be removed"
}

# -- Flatpak Configuration Tests ----------------------------------------------

@test "Flathub remote should be added" {
  # Validates the 'flatpak remote-add' command.
  run buildah run "$CONTAINER" -- flatpak remotes --show-details | grep -q 'flathub'
  assert_success
}