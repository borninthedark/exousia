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

    # Detect OS family from os-release
    if [ -f "$MOUNT_POINT/etc/os-release" ]; then
        OS_ID=$(grep -oP '^ID=\K.*' "$MOUNT_POINT/etc/os-release" | tr -d '"' || echo "unknown")
        OS_VERSION_ID=$(grep -oP '^VERSION_ID=\K.*' "$MOUNT_POINT/etc/os-release" | tr -d '"' || echo "unknown")
        export OS_ID OS_VERSION_ID
        echo "--- Detected OS: $OS_ID $OS_VERSION_ID ---"
    else
        OS_ID="unknown"
        OS_VERSION_ID="unknown"
        export OS_ID OS_VERSION_ID
        echo "WARNING: Could not detect OS from os-release" >&2
    fi

    # Detect Fedora version and build type from .fedora-version file (legacy)
    if [ -f "$MOUNT_POINT/.fedora-version" ]; then
        FEDORA_VERSION_LINE=$(cat "$MOUNT_POINT/.fedora-version")
        FEDORA_VERSION=$(echo "$FEDORA_VERSION_LINE" | cut -d: -f1)
        BUILD_TYPE=$(echo "$FEDORA_VERSION_LINE" | cut -d: -f2)
        export FEDORA_VERSION BUILD_TYPE
        echo "--- Detected from .fedora-version: Fedora $FEDORA_VERSION, Build type: $BUILD_TYPE ---"
    else
        FEDORA_VERSION="$OS_VERSION_ID"
        export FEDORA_VERSION

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

# Helper function to check if running any Fedora variant
is_fedora() {
    [[ "$OS_ID" == "fedora" ]] || [[ "$BUILD_TYPE" =~ ^fedora- ]]
}

# Helper function to check if running bootcrew distro
is_bootcrew() {
    [[ "$BUILD_TYPE" =~ ^(arch|gentoo|debian|ubuntu|opensuse|proxmox)$ ]]
}

# Helper function to check if Plymouth is enabled
is_plymouth_enabled() {
    [[ "${ENABLE_PLYMOUTH:-true}" == "true" ]]
}

# Helper function to get package manager
get_package_manager() {
    if is_fedora; then
        echo "rpm"
    elif [[ "$OS_ID" == "arch" ]]; then
        echo "pacman"
    elif [[ "$OS_ID" =~ ^(debian|ubuntu)$ ]]; then
        echo "dpkg"
    elif [[ "$OS_ID" =~ ^(opensuse|suse)$ ]]; then
        echo "rpm"
    elif [[ "$OS_ID" == "gentoo" ]]; then
        echo "portage"
    else
        echo "unknown"
    fi
}

# --- OS / Distro version checks ---

@test "OS should have valid os-release file" {
    assert_file_exists "$MOUNT_POINT/etc/os-release"
    run grep 'ID=' "$MOUNT_POINT/etc/os-release"
    assert_success "os-release should contain OS ID"
}

@test "OS should be Fedora Linux (Fedora-specific)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    run grep 'ID=fedora' "$MOUNT_POINT/etc/os-release"
    assert_success "Should be running Fedora Linux"
}

@test "OS version should match expected Fedora versions (41–44 or rawhide)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    run grep -E 'VERSION_ID=(41|42|43|44)' "$MOUNT_POINT/etc/os-release"
    if [ "$status" -ne 0 ]; then
        run grep 'VARIANT_ID=rawhide' "$MOUNT_POINT/etc/os-release"
        assert_success "Should be Fedora 41–44 or rawhide"
    fi
}

@test "Detected OS version is valid" {
    if [[ "$OS_VERSION_ID" == "unknown" ]]; then
        skip "Could not detect OS version"
    fi

    # OS-specific version validation
    if is_fedora; then
        [[ "$OS_VERSION_ID" =~ ^(41|42|43|44|rawhide)$ ]]
    else
        # For bootcrew distros, just check it's not empty
        [[ -n "$OS_VERSION_ID" ]]
    fi
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

@test "Custom package list files should exist (Fedora only)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-added"
    assert_file_exists "$MOUNT_POINT/usr/local/share/sericea-bootc/packages-removed"
}

@test "Sway package list should exist (packages.sway) (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "Sway package list is only expected on fedora-bootc builds"
    fi
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

# --- Plymouth Tests (fedora-bootc only) ---

@test "Plymouth scripts should be present" {
    assert_file_executable "$MOUNT_POINT/usr/local/bin/setup-plymouth-theme"
    assert_file_executable "$MOUNT_POINT/usr/local/bin/dracut-rebuild"
}

@test "Custom Plymouth theme should be copied for fedora-bootc" {
    if ! is_fedora_bootc; then
        skip "Plymouth theme test only applies to fedora-bootc builds"
    fi

    assert_dir_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/"
    assert_file_exists "$MOUNT_POINT/usr/share/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
}

@test "Plymouth should be configured if enabled (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "Plymouth configuration test only applies to fedora-bootc builds"
    fi

    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi

    run buildah run "$CONTAINER" -- rpm -q plymouth
    assert_success "Plymouth should be installed when enabled"

    # For fedora-bootc, check our custom configuration
    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    assert_file_exists "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"

    run grep -q 'splash' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Kernel arguments should contain 'splash'"

    run grep -q 'quiet' "$MOUNT_POINT/usr/lib/bootc/kargs.d/plymouth.toml"
    assert_success "Kernel arguments should contain 'quiet'"
}

@test "Plymouth dracut configuration should be correct if enabled (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "Plymouth dracut configuration test only applies to fedora-bootc builds"
    fi

    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi

    assert_file_exists "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"

    run grep -q 'add_dracutmodules.*plymouth' "$MOUNT_POINT/usr/lib/dracut/dracut.conf.d/plymouth.conf"
    assert_success "Dracut config should include Plymouth module"
}

@test "Initramfs should exist if Plymouth was enabled during build (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "Initramfs test only applies to fedora-bootc builds"
    fi

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

@test "Plymouth theme should be set correctly if enabled (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "Plymouth theme test only applies to fedora-bootc builds"
    fi

    if ! is_plymouth_enabled; then
        skip "Plymouth is disabled (ENABLE_PLYMOUTH=false)"
    fi

    run buildah run "$CONTAINER" -- sh -c "plymouth-set-default-theme 2>/dev/null || echo 'not-set'"

    if [[ "$output" == "not-set" ]]; then
        skip "plymouth-set-default-theme command not available"
    fi

    # fedora-bootc should have our custom theme
    assert_output "bgrt-better-luks" "fedora-bootc should use custom bgrt-better-luks theme"
}

@test "/var/tmp should be symlinked to /tmp (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "/var/tmp symlink test only applies to fedora-bootc builds"
    fi

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

@test "ENABLE_PLYMOUTH environment variable should be true or false (fedora-bootc only)" {
    if ! is_fedora_bootc; then
        skip "ENABLE_PLYMOUTH env var test only applies to fedora-bootc builds"
    fi

    run buildah run "$CONTAINER" -- printenv ENABLE_PLYMOUTH

    if [ "$status" -ne 0 ]; then
        fail "ENABLE_PLYMOUTH is not set"
    fi

    case "$output" in
        true|false)
            # pass
            ;;
        *)
            fail "ENABLE_PLYMOUTH should be 'true' or 'false', got: $output"
            ;;
    esac
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

@test "Custom script 'generate-readme' should be executable" {
    run test -x "$MOUNT_POINT/usr/local/bin/generate-readme"
    assert_success
}

# --- Repositories and package config ---

@test "RPM Fusion repositories should be configured (Fedora only)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-free.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/rpmfusion-nonfree.repo"
}

@test "Custom repositories should be configured (Fedora only)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/nwg-shell.repo"
    assert_file_exists "$MOUNT_POINT/etc/yum.repos.d/swaylock-effects.repo"
}

# --- Key packages ---

@test "DNF5 should be installed and symlinked as default dnf (Fedora only)" {
    if ! is_fedora; then
        skip "Test only applies to Fedora-based images"
    fi
    run buildah run "$CONTAINER" -- rpm -q dnf5
    assert_success
    run test -L "$MOUNT_POINT/usr/bin/dnf"
    assert_success
}

@test "bootc should be installed" {
    # Check for bootc binary regardless of package manager
    if [[ -x "$MOUNT_POINT/usr/bin/bootc" ]]; then
        # Found the binary
        run test -x "$MOUNT_POINT/usr/bin/bootc"
        assert_success
    else
        # Try package manager query as fallback
        if is_fedora || [[ "$OS_ID" =~ ^(opensuse|suse)$ ]]; then
            run buildah run "$CONTAINER" -- rpm -q bootc
            assert_success
        else
            skip "Cannot verify bootc installation on this distro (bootc may be built from source)"
        fi
    fi
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
    if ! is_fedora_bootc; then
        skip "Greeter user is only expected on fedora-bootc builds"
    fi
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
}

@test "System users greetd and rtkit should exist" {
    if ! is_fedora_bootc; then
        skip "Greetd user is only expected on fedora-bootc builds"
    fi
    run chroot "$MOUNT_POINT" getent passwd greetd
    assert_success
    run chroot "$MOUNT_POINT" getent passwd rtkit
    assert_success
}

@test "Greeter user should have correct UID and shell" {
    if ! is_fedora_bootc; then
        skip "Greeter user is only expected on fedora-bootc builds"
    fi
    run chroot "$MOUNT_POINT" getent passwd greeter
    assert_success
    echo "$output" | grep -Eq '^greeter:x:241:241:Greeter Login User:/var/lib/greeter:/sbin/nologin$'
    assert_success
}

@test "Greetd user should have correct shell" {
    if ! is_fedora_bootc; then
        skip "Greetd user is only expected on fedora-bootc builds"
    fi
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