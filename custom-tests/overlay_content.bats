#!/usr/bin/env bats

# Pre-build tests that validate overlay files and static content
# without requiring a built container image.
#
# These tests run against the source tree directly and catch
# misconfigurations before an expensive image build.

bats_load_library bats-support
bats_load_library bats-assert
bats_load_library bats-file

# Project root relative to the test file
OVERLAY_ROOT="${BATS_TEST_DIRNAME}/../overlays"
CONFIG_FILE="${BATS_TEST_DIRNAME}/../adnyeus.yml"

# --- Helper functions ---

# Check if a build flag is set in adnyeus.yml
is_build_flag_set() {
    local flag="$1"
    grep -qE "^\s+${flag}:\s+true" "$CONFIG_FILE"
}

# Assert a file has a valid shebang line
assert_has_shebang() {
    local file="$1"
    run head -1 "$file"
    assert_output --regexp '^#!'
}

# ============================================================
# Directory structure
# ============================================================

@test "Base overlay directory should exist" {
    assert_dir_exists "$OVERLAY_ROOT/base"
}

@test "Sway overlay directory should exist" {
    assert_dir_exists "$OVERLAY_ROOT/sway"
}

@test "Deploy overlay directory should exist" {
    assert_dir_exists "$OVERLAY_ROOT/deploy"
}

# ============================================================
# Base configs (PAM, polkit, tmpfiles)
# ============================================================

@test "Base configs directory should contain expected subdirectories" {
    assert_dir_exists "$OVERLAY_ROOT/base/configs/pam.d"
    assert_dir_exists "$OVERLAY_ROOT/base/configs/tmpfiles.d"
    assert_dir_exists "$OVERLAY_ROOT/base/configs/polkit-1"
}

@test "PAM sudo config should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/configs/pam.d/sudo"
}

@test "PAM U2F config files should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/configs/pam.d/u2f-required"
    assert_file_exists "$OVERLAY_ROOT/base/configs/pam.d/u2f-sufficient"
}

@test "PAM sudo should reference U2F" {
    run grep -q "u2f-sufficient" "$OVERLAY_ROOT/base/configs/pam.d/sudo"
    assert_success "sudo PAM config should include u2f-sufficient"
}

@test "Libvirt polkit rule should exist and reference org.libvirt.unix.manage" {
    assert_file_exists "$OVERLAY_ROOT/base/configs/polkit-1/rules.d/50-libvirt.rules"
    run grep -q "org.libvirt.unix.manage" "$OVERLAY_ROOT/base/configs/polkit-1/rules.d/50-libvirt.rules"
    assert_success "polkit rule should reference org.libvirt.unix.manage"
}

@test "Libvirt tmpfiles.d config should exist and reference /var/lib/libvirt" {
    assert_file_exists "$OVERLAY_ROOT/base/configs/tmpfiles.d/libvirt.conf"
    run grep -q "/var/lib/libvirt" "$OVERLAY_ROOT/base/configs/tmpfiles.d/libvirt.conf"
    assert_success "tmpfiles config should reference /var/lib/libvirt"
}

# ============================================================
# Sysusers
# ============================================================

@test "Bootc sysusers config should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/sysusers/bootc.conf"
}

@test "Bootc sysusers config should define greetd user" {
    run grep -q "greetd" "$OVERLAY_ROOT/base/sysusers/bootc.conf"
    assert_success "bootc.conf should define greetd user"
}

@test "Bootc sysusers config should define rtkit user" {
    run grep -q "rtkit" "$OVERLAY_ROOT/base/sysusers/bootc.conf"
    assert_success "bootc.conf should define rtkit user"
}

@test "Bootc sysusers config should define greeter user" {
    run grep -q "greeter" "$OVERLAY_ROOT/base/sysusers/bootc.conf"
    assert_success "bootc.conf should define greeter user"
}

# ============================================================
# Package definitions
# ============================================================

@test "Base package definition should exist and have metadata" {
    assert_file_exists "$OVERLAY_ROOT/base/packages/common/base.yml"
    run grep -q "^metadata:" "$OVERLAY_ROOT/base/packages/common/base.yml"
    assert_success "base.yml should have metadata section"
}

@test "Sway package definition should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/packages/window-managers/sway.yml"
}

@test "Remove package definition should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/packages/common/remove.yml"
}

@test "Flatpaks definition should exist and be type default-flatpaks" {
    assert_file_exists "$OVERLAY_ROOT/base/packages/common/flatpaks.yml"
    run grep -q "^type: default-flatpaks" "$OVERLAY_ROOT/base/packages/common/flatpaks.yml"
    assert_success "flatpaks.yml should declare type: default-flatpaks"
}

@test "Package YAML files should be valid YAML (no tabs)" {
    local files=(
        "$OVERLAY_ROOT/base/packages/common/base.yml"
        "$OVERLAY_ROOT/base/packages/common/remove.yml"
        "$OVERLAY_ROOT/base/packages/common/flatpaks.yml"
        "$OVERLAY_ROOT/base/packages/window-managers/sway.yml"
    )
    for f in "${files[@]}"; do
        run grep -Pn "\t" "$f"
        assert_failure "YAML file $(basename "$f") should not contain tabs"
    done
}

# ============================================================
# Base tools/scripts
# ============================================================

@test "build-zfs-kmod script should exist and have shebang" {
    assert_file_exists "$OVERLAY_ROOT/base/tools/build-zfs-kmod"
    assert_has_shebang "$OVERLAY_ROOT/base/tools/build-zfs-kmod"
}

@test "build-zfs-kmod should be executable" {
    run test -x "$OVERLAY_ROOT/base/tools/build-zfs-kmod"
    assert_success
}

@test "generate-readme script should exist and be executable" {
    assert_file_exists "$OVERLAY_ROOT/base/tools/generate-readme"
    run test -x "$OVERLAY_ROOT/base/tools/generate-readme"
    assert_success
}

@test "verify-flatpak-installation script should exist and have shebang" {
    assert_file_exists "$OVERLAY_ROOT/base/tools/verify-flatpak-installation"
    assert_has_shebang "$OVERLAY_ROOT/base/tools/verify-flatpak-installation"
}

# ============================================================
# Sway configs
# ============================================================

@test "Greetd config should exist and reference tuigreet" {
    assert_file_exists "$OVERLAY_ROOT/sway/configs/greetd/config.toml"
    run grep -q "tuigreet" "$OVERLAY_ROOT/sway/configs/greetd/config.toml"
    assert_success "greetd config should reference tuigreet"
}

@test "Greetd config should use start-sway as session command" {
    run grep -q "start-sway" "$OVERLAY_ROOT/sway/configs/greetd/config.toml"
    assert_success "greetd config should use start-sway"
}

@test "Sway main config should exist" {
    assert_file_exists "$OVERLAY_ROOT/sway/configs/sway/config"
}

@test "Sway config.d snippets should exist" {
    assert_dir_exists "$OVERLAY_ROOT/sway/configs/sway/config.d"

    local expected_snippets=(
        "51-display.conf"
        "60-bindings-volume.conf"
        "95-theme.conf"
    )
    for snippet in "${expected_snippets[@]}"; do
        assert_file_exists "$OVERLAY_ROOT/sway/configs/sway/config.d/$snippet"
    done
}

@test "Swaylock config should exist" {
    assert_file_exists "$OVERLAY_ROOT/sway/configs/swaylock/config"
}

@test "Plymouth theme should exist when plymouth is enabled" {
    if ! is_build_flag_set "enable_plymouth"; then
        skip "Plymouth is not enabled in adnyeus.yml"
    fi

    assert_file_exists "$OVERLAY_ROOT/sway/configs/plymouth/themes/bgrt-better-luks/bgrt-better-luks.plymouth"
}

# ============================================================
# Sway scripts
# ============================================================

@test "Sway setup scripts should exist and be executable" {
    local scripts=(
        "$OVERLAY_ROOT/sway/scripts/setup/dracut-rebuild"
        "$OVERLAY_ROOT/sway/scripts/setup/ensure-sway-session"
        "$OVERLAY_ROOT/sway/scripts/setup/setup-plymouth-theme"
    )
    for script in "${scripts[@]}"; do
        assert_file_exists "$script"
        run test -x "$script"
        assert_success "$(basename "$script") should be executable"
        assert_has_shebang "$script"
    done
}

@test "Sway runtime scripts should exist and be executable" {
    local scripts=(
        "$OVERLAY_ROOT/sway/scripts/runtime/layered-include"
        "$OVERLAY_ROOT/sway/scripts/runtime/lid"
        "$OVERLAY_ROOT/sway/scripts/runtime/volume-helper"
    )
    for script in "${scripts[@]}"; do
        assert_file_exists "$script"
        run test -x "$script"
        assert_success "$(basename "$script") should be executable"
        assert_has_shebang "$script"
    done
}

# ============================================================
# Sway session
# ============================================================

@test "Sway desktop entry should be valid" {
    assert_file_exists "$OVERLAY_ROOT/sway/session/sway.desktop"
    run grep -q "^\[Desktop Entry\]" "$OVERLAY_ROOT/sway/session/sway.desktop"
    assert_success "sway.desktop should have [Desktop Entry] header"
    run grep -q "^Exec=start-sway" "$OVERLAY_ROOT/sway/session/sway.desktop"
    assert_success "sway.desktop should exec start-sway"
}

@test "Sway environment file should export locale" {
    assert_file_exists "$OVERLAY_ROOT/sway/session/environment"
    run grep -q "LANG=en_US.UTF-8" "$OVERLAY_ROOT/sway/session/environment"
    assert_success "environment should set LANG"
    run grep -q "LC_ALL=en_US.UTF-8" "$OVERLAY_ROOT/sway/session/environment"
    assert_success "environment should set LC_ALL"
}

@test "Sway environment should set Wayland variables" {
    run grep -q "MOZ_ENABLE_WAYLAND=1" "$OVERLAY_ROOT/sway/session/environment"
    assert_success "environment should enable Wayland for Firefox"
    run grep -q "QT_QPA_PLATFORM=wayland" "$OVERLAY_ROOT/sway/session/environment"
    assert_success "environment should set Qt to Wayland"
}

@test "start-sway script should exist, be executable, and have shebang" {
    assert_file_exists "$OVERLAY_ROOT/sway/session/start-sway"
    run test -x "$OVERLAY_ROOT/sway/session/start-sway"
    assert_success "start-sway should be executable"
    assert_has_shebang "$OVERLAY_ROOT/sway/session/start-sway"
}

# ============================================================
# Sway repos
# ============================================================

@test "nwg-shell repo definition should exist" {
    assert_file_exists "$OVERLAY_ROOT/sway/repos/nwg-shell.repo"
}

# ============================================================
# Quadlet definitions (deploy)
# ============================================================

@test "Forgejo quadlet should exist and have required sections" {
    assert_file_exists "$OVERLAY_ROOT/deploy/forgejo.container"
    run grep -q "^\[Container\]" "$OVERLAY_ROOT/deploy/forgejo.container"
    assert_success "forgejo.container should have [Container] section"
    # [Install] is commented out -- services are user-activated post-install
    run grep -q "\[Install\]" "$OVERLAY_ROOT/deploy/forgejo.container"
    assert_success "forgejo.container should have [Install] section (commented or active)"
}

@test "Forgejo quadlet should have autoupdate label" {
    run grep -q "io.containers.autoupdate=registry" "$OVERLAY_ROOT/deploy/forgejo.container"
    assert_success "forgejo.container should have autoupdate label"
}

@test "Forgejo runner quadlet should exist" {
    assert_file_exists "$OVERLAY_ROOT/deploy/forgejo-runner.container"
}

@test "Exousia registry quadlet should exist" {
    assert_file_exists "$OVERLAY_ROOT/deploy/exousia-registry.container"
}

@test "Quadlet volume definitions should exist" {
    assert_file_exists "$OVERLAY_ROOT/deploy/forgejo-data.volume"
    assert_file_exists "$OVERLAY_ROOT/deploy/forgejo-runner-data.volume"
    assert_file_exists "$OVERLAY_ROOT/deploy/exousia-registry-data.volume"
}

@test "Quadlet network definition should exist" {
    assert_file_exists "$OVERLAY_ROOT/deploy/exousia.network"
}

# ============================================================
# Chezmoi systemd units
# ============================================================

@test "Chezmoi systemd user units should exist" {
    assert_file_exists "$OVERLAY_ROOT/base/systemd/user/chezmoi-init.service"
    assert_file_exists "$OVERLAY_ROOT/base/systemd/user/chezmoi-update.service"
    assert_file_exists "$OVERLAY_ROOT/base/systemd/user/chezmoi-update.timer"
}

# ============================================================
# ZFS overlay files (conditional)
# ============================================================

@test "ZFS modules-load.d config should exist" {
    if ! is_build_flag_set "enable_zfs"; then
        skip "ZFS is not enabled in adnyeus.yml"
    fi

    assert_file_exists "$OVERLAY_ROOT/base/configs-zfs/modules-load.d/zfs.conf"
}

@test "ZFS modules-load.d config should contain only 'zfs'" {
    if ! is_build_flag_set "enable_zfs"; then
        skip "ZFS is not enabled in adnyeus.yml"
    fi

    run grep -c "." "$OVERLAY_ROOT/base/configs-zfs/modules-load.d/zfs.conf"
    assert_output "1"

    run grep -q "^zfs$" "$OVERLAY_ROOT/base/configs-zfs/modules-load.d/zfs.conf"
    assert_success "modules-load.d/zfs.conf should contain 'zfs'"
}

@test "ZFS package definition should exist when ZFS is enabled" {
    if ! is_build_flag_set "enable_zfs"; then
        skip "ZFS is not enabled in adnyeus.yml"
    fi

    assert_file_exists "$OVERLAY_ROOT/base/packages/common/zfs.yml"
}

# ============================================================
# adnyeus.yml integrity
# ============================================================

@test "adnyeus.yml should exist" {
    assert_file_exists "$CONFIG_FILE"
}

@test "adnyeus.yml should reference base-image" {
    run grep -q "^base-image:" "$CONFIG_FILE"
    assert_success "adnyeus.yml should declare a base-image"
}

@test "adnyeus.yml should have modules section" {
    run grep -q "^modules:" "$CONFIG_FILE"
    assert_success "adnyeus.yml should have modules section"
}

@test "All overlay paths in adnyeus.yml should exist" {
    # Extract src paths from adnyeus.yml files modules
    while IFS= read -r src_path; do
        local full_path="${BATS_TEST_DIRNAME}/../${src_path}"
        if [ ! -e "$full_path" ]; then
            echo "Missing overlay source: $src_path" >&3
            return 1
        fi
    done < <(grep -oP '^\s+- src: \K.+' "$CONFIG_FILE")
}
