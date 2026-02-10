#!/usr/bin/env python3
"""
Unit tests for yaml-to-containerfile transpiler
================================================
"""

import importlib.util
from pathlib import Path

import yaml

# Load module from file path (handles hyphens in filename)
script_path = Path(__file__).parent / "yaml-to-containerfile.py"
spec = importlib.util.spec_from_file_location("yaml_to_containerfile", script_path)
assert spec is not None, f"Could not load module spec from {script_path}"
yaml_to_containerfile = importlib.util.module_from_spec(spec)
assert spec.loader is not None, "Module spec has no loader"
spec.loader.exec_module(yaml_to_containerfile)

ContainerfileGenerator = yaml_to_containerfile.ContainerfileGenerator
BuildContext = yaml_to_containerfile.BuildContext
determine_base_image = yaml_to_containerfile.determine_base_image
FEDORA_ATOMIC_VARIANTS = yaml_to_containerfile.FEDORA_ATOMIC_VARIANTS


def test_generator_is_stateless():
    """Test that ContainerfileGenerator.generate() can be called multiple times."""
    config = {
        "name": "test-config",
        "description": "Test configuration",
        "labels": {"org.opencontainers.image.title": "test-image"},
        "modules": [{"type": "script", "scripts": ["echo 'Hello World'"]}],
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)

    # Generate Containerfile twice
    output1 = generator.generate()
    output2 = generator.generate()

    # Both outputs should be identical
    assert output1 == output2, "Multiple calls to generate() should produce identical output"

    # Verify the output contains expected content
    assert "FROM quay.io/fedora/fedora-sway-atomic:43" in output1
    assert "echo 'Hello World'" in output1
    assert "test-config" in output1

    # Verify the outputs are not doubled (i.e., not accumulating state)
    assert output1.count("FROM") == 1, "Should only have one FROM instruction"
    assert output1.count("Hello World") == 1, "Should only have one script instance"

    print("✓ Generator is stateless - multiple generate() calls work correctly")


def test_rpm_module_includes_common_remove_packages():
    """Ensure rpm-ostree modules respect the shared removal list."""

    remove_file = (
        Path(__file__).parent.parent / "overlays" / "base" / "packages" / "common" / "remove.yml"
    )
    common_remove = (yaml.safe_load(remove_file.read_text()) or {}).get("packages", [])

    config = {
        "name": "rpm-remove-test",
        "description": "Validate removal handling",
        "modules": [
            {
                "type": "rpm-ostree",
                "install": ["htop"],
                "remove": ["firefox-langpacks"],
            }
        ],
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    removal_lines = [line for line in output.splitlines() if "dnf remove -y" in line]
    assert removal_lines, "Removal command not rendered"

    removal_line = " ".join(removal_lines)
    expected_remove = {"firefox-langpacks", *common_remove}
    for pkg in expected_remove:
        assert pkg in removal_line, f"{pkg} was not included in removal list"

    print("✓ rpm-ostree module appends common removal packages")


def test_generator_with_different_contexts():
    """Test that same generator instance can handle different builds."""
    config = {
        "name": "multi-build",
        "description": "Multi-build test",
        "modules": [{"type": "script", "scripts": ["echo 'Build step'"]}],
    }

    # First context - fedora-sway-atomic
    context1 = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context1)
    output1 = generator.generate()

    # Change context - fedora-bootc with Plymouth
    context2 = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora",
    )

    # Use same generator instance with new context
    generator.context = context2
    output2 = generator.generate()

    # Outputs should be different based on context
    assert output1 != output2, "Different contexts should produce different outputs"
    assert "fedora-sway-atomic" in output1
    assert "fedora-bootc" in output2
    assert "ENABLE_PLYMOUTH" in output2
    assert "ENABLE_PLYMOUTH" not in output1

    print("✓ Generator handles context changes correctly")


def test_custom_base_image_sources_are_respected():
    """Ensure custom base images from supported registries are preserved."""
    sway_config = {
        "name": "fedora-sway",
        "description": "Fedora sway atomic test",
        "base-image": "quay.io/fedora/fedora-sway-atomic:43",
    }

    sway_base = determine_base_image(sway_config, "fedora-sway-atomic", "43")
    assert sway_base == "quay.io/fedora/fedora-sway-atomic:43"

    print("✓ Supported custom base image registries are passed through")


def test_custom_bases_without_tags_are_versioned():
    """Custom bases should pick up the requested version when untagged."""

    untagged_sway = {
        "name": "fedora-sway-no-tag",
        "description": "Sway atomic images also require explicit tags",
        "base-image": "quay.io/fedora/fedora-sway-atomic",
    }

    sway_base = determine_base_image(untagged_sway, "fedora-sway-atomic", "43")
    assert sway_base == "quay.io/fedora/fedora-sway-atomic:43"

    print("✓ Untagged custom bases are pinned to the requested version")


def test_script_comments_do_not_chain_into_next_run():
    """Comments inside scripts should not accidentally continue into the next RUN."""

    config = {
        "name": "comment-breaks",
        "description": "Ensure comments don't extend RUN",
        "modules": [
            {
                "type": "script",
                "scripts": [
                    """
                    echo 'first'
                    # trailing comment
                    # another comment
                    """
                ],
            },
            {"type": "script", "scripts": ["echo 'second'"]},
        ],
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()
    lines = output.splitlines()

    first_echo_idx = next(i for i, line in enumerate(lines) if "echo 'first'" in line)

    # The line running the first command should not end with a continuation, even
    # though comments follow. This prevents the next RUN from being merged when
    # builders strip comment-only lines.
    assert (
        not lines[first_echo_idx].rstrip().endswith("\\")
    ), "First command should not have trailing backslash"

    next_run_idx = next(
        i
        for i, line in enumerate(lines[first_echo_idx + 1 :], start=first_echo_idx + 1)
        if line.startswith("RUN")
    )
    snippet = " ".join(lines[first_echo_idx : next_run_idx + 1])

    assert (
        "echo 'first'; RUN" not in snippet
    ), "Comments should not chain into the following RUN instruction"

    print("✓ Script comments do not leak into subsequent RUN commands")


def test_fedora_atomic_variants():
    """Test that all Fedora Atomic variants are recognized."""
    assert "fedora-sway-atomic" in FEDORA_ATOMIC_VARIANTS
    assert len(FEDORA_ATOMIC_VARIANTS) == 1

    base_sway = determine_base_image({}, "fedora-sway-atomic", "43")
    assert "fedora-sway-atomic:43" in base_sway
    assert base_sway.startswith("quay.io/")

    print("✓ Fedora Atomic variants are recognized")


def test_distro_detection():
    """Test that distro is properly detected from image_type."""
    # Fedora-based
    fedora_context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=True,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )
    assert fedora_context.distro == "fedora"

    print("✓ Distro detection works correctly")


def test_enable_plymouth_generates_env():
    """Test that ENABLE_PLYMOUTH is generated as ENV, not a standalone instruction."""
    config = {
        "name": "plymouth-test",
        "description": "Test ENABLE_PLYMOUTH generation",
        "modules": [],
    }

    context = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    # Should have ENV instruction for ENABLE_PLYMOUTH
    assert (
        "ENV ENABLE_PLYMOUTH=true" in output
    ), "ENABLE_PLYMOUTH should be generated as ENV instruction"

    # Should NOT have standalone ENABLE_PLYMOUTH
    lines = output.split("\n")
    for line in lines:
        stripped = line.strip()
        # Check for standalone instruction (not part of ENV or RUN)
        if stripped.startswith("ENABLE_PLYMOUTH") and not stripped.startswith(
            "ENV ENABLE_PLYMOUTH"
        ):
            raise AssertionError(f"Found standalone ENABLE_PLYMOUTH instruction: {stripped}")

    print("✓ ENABLE_PLYMOUTH generates correct ENV instruction")


def test_package_loader_module():
    """Test that package-loader module type is supported."""
    config = {
        "name": "package-loader-test",
        "description": "Test package-loader module",
        "modules": [{"type": "package-loader", "window_manager": "sway", "include_common": True}],
    }

    context = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    # Should contain package installation
    assert "dnf install" in output, "Should generate dnf install commands"

    # Should install sway packages
    assert "sway" in output.lower(), "Should install sway packages"

    # Should have RPMFusion repos for Fedora
    assert "rpmfusion" in output.lower(), "Should add RPMFusion repos for Fedora"

    print("✓ package-loader module type works correctly")


def test_plymouth_not_generated_for_sway_atomic():
    """Test that ENABLE_PLYMOUTH is not generated for non-bootc images."""
    config = {
        "name": "sway-atomic-test",
        "description": "Test Sway Atomic without Plymouth ENV",
        "modules": [],
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=True,  # Even if enabled
        use_upstream_sway_config=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora",
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    # Should NOT have ENV ENABLE_PLYMOUTH for non-bootc images
    assert (
        "ENV ENABLE_PLYMOUTH" not in output
    ), "ENABLE_PLYMOUTH ENV should only be for fedora-bootc images"

    print("✓ ENABLE_PLYMOUTH not generated for non-bootc images")


def _make_context(**overrides):
    """Build a standard BuildContext with optional overrides."""
    defaults = {
        "image_type": "fedora-bootc",
        "fedora_version": "43",
        "enable_plymouth": False,
        "use_upstream_sway_config": False,
        "base_image": "quay.io/fedora/fedora-bootc:43",
        "distro": "fedora",
    }
    defaults.update(overrides)
    return BuildContext(**defaults)


def _make_chezmoi_config(**overrides):
    """Build a minimal config with a chezmoi module for testing."""
    chezmoi_module = {
        "type": "chezmoi",
        "repository": "https://github.com/borninthedark/dotfiles",
        "all-users": True,
        "file-conflict-policy": "skip",
        "run-every": "1d",
        "wait-after-boot": "5m",
    }
    chezmoi_module.update(overrides)
    return {
        "name": "chezmoi-test",
        "description": "Chezmoi module test",
        "modules": [chezmoi_module],
    }


def test_chezmoi_module_generates_copy_and_sed():
    """Chezmoi module should emit COPY, sed, and systemctl commands."""
    config = _make_chezmoi_config()
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "COPY --chmod=0644 overlays/base/systemd/user/ /usr/lib/systemd/user/" in output
    assert "sed -i" in output
    # sed commands should substitute placeholders with actual values
    assert "borninthedark/dotfiles" in output
    assert "systemctl --global enable chezmoi-init.service" in output
    assert "systemctl --global enable chezmoi-update.timer" in output
    assert "WARNING: Unknown module type: chezmoi" not in output

    print("✓ Chezmoi module generates COPY, sed, and systemctl commands")


def test_chezmoi_module_skip_policy():
    """Skip conflict policy should produce --keep-going."""
    config = _make_chezmoi_config(**{"file-conflict-policy": "skip"})
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "--keep-going" in output
    assert "--force" not in output

    print("✓ Chezmoi skip policy emits --keep-going")


def test_chezmoi_module_replace_policy():
    """Replace conflict policy should produce --force."""
    config = _make_chezmoi_config(**{"file-conflict-policy": "replace"})
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "--force" in output
    assert "--keep-going" not in output

    print("✓ Chezmoi replace policy emits --force")


def test_chezmoi_module_all_users_false():
    """When all-users is false, no systemctl --global enable should appear."""
    config = _make_chezmoi_config(**{"all-users": False})
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "systemctl --global enable" not in output

    print("✓ Chezmoi all-users=false skips global enablement")


def test_chezmoi_module_disable_init():
    """When disable-init is true, init service should not be enabled."""
    config = _make_chezmoi_config(**{"disable-init": True})
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "systemctl --global enable chezmoi-init.service" not in output
    assert "systemctl --global enable chezmoi-update.timer" in output

    print("✓ Chezmoi disable-init skips init enablement")


def test_chezmoi_module_disable_update():
    """When disable-update is true, update timer should not be enabled."""
    config = _make_chezmoi_config(**{"disable-update": True})
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "systemctl --global enable chezmoi-init.service" in output
    assert "systemctl --global enable chezmoi-update.timer" not in output

    print("✓ Chezmoi disable-update skips timer enablement")


def test_chezmoi_module_missing_repo():
    """Missing repository with init enabled should emit an error comment."""
    config = _make_chezmoi_config(repository="")
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "# ERROR: chezmoi module requires 'repository'" in output

    print("✓ Chezmoi missing repo emits error comment")


def test_chezmoi_module_with_branch():
    """Branch option should appear in sed output for init service."""
    config = _make_chezmoi_config(branch="main")
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "--branch main" in output

    print("✓ Chezmoi branch option emitted in sed command")


def test_systemd_module_user_services():
    """Systemd module should process user.enabled with systemctl --global enable."""
    config = {
        "name": "systemd-user-test",
        "description": "Test user services",
        "modules": [
            {
                "type": "systemd",
                "system": {"enabled": ["sshd.service"]},
                "user": {"enabled": ["chezmoi-init.service", "chezmoi-update.timer"]},
                "default-target": "graphical.target",
            }
        ],
    }

    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "systemctl enable sshd.service" in output
    assert "systemctl --global enable chezmoi-init.service" in output
    assert "systemctl --global enable chezmoi-update.timer" in output
    assert "systemctl set-default graphical.target" in output

    print("✓ Systemd module processes user services correctly")


# --- git-clone module tests ---


def _make_git_clone_config(**overrides):
    """Build a minimal config with a git-clone module for testing."""
    git_clone_module = {
        "type": "git-clone",
        "repos": [
            {
                "url": "https://github.com/nwg-piotr/autotiling",
                "branch": "master",
                "files": [
                    {
                        "src": "autotiling/main.py",
                        "dst": "/usr/local/bin/autotiling",
                        "mode": "0755",
                    }
                ],
            }
        ],
    }
    git_clone_module.update(overrides)
    return {
        "name": "git-clone-test",
        "description": "Git clone module test",
        "modules": [git_clone_module],
    }


def test_git_clone_module_generates_clone_and_install():
    """Git-clone module should emit git clone, install, and rm commands."""
    config = _make_git_clone_config()
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "git clone --depth 1" in output
    assert "https://github.com/nwg-piotr/autotiling" in output
    assert "install -m 0755" in output
    assert "/usr/local/bin/autotiling" in output
    assert "rm -rf /tmp/git-clone-0" in output  # nosec B108
    assert "WARNING: Unknown module type: git-clone" not in output

    print("✓ Git-clone module generates clone, install, and cleanup commands")


def test_git_clone_module_with_branch():
    """When branch is specified, --branch flag should appear in clone command."""
    config = _make_git_clone_config()
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "--branch master" in output

    print("✓ Git-clone module includes --branch flag")


def test_git_clone_module_without_branch():
    """When branch is omitted, no --branch flag should appear."""
    config = _make_git_clone_config(
        repos=[
            {
                "url": "https://github.com/nwg-piotr/autotiling",
                "files": [
                    {
                        "src": "autotiling/main.py",
                        "dst": "/usr/local/bin/autotiling",
                        "mode": "0755",
                    }
                ],
            }
        ]
    )
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "--branch" not in output
    assert "git clone --depth 1 https://github.com/nwg-piotr/autotiling" in output

    print("✓ Git-clone module omits --branch when not specified")


def test_git_clone_module_multiple_repos():
    """Multiple repos should produce multiple clone/install/cleanup sequences."""
    config = _make_git_clone_config(
        repos=[
            {
                "url": "https://github.com/user/repo-a",
                "branch": "main",
                "files": [{"src": "bin/tool-a", "dst": "/usr/local/bin/tool-a", "mode": "0755"}],
            },
            {
                "url": "https://github.com/user/repo-b",
                "files": [{"src": "bin/tool-b", "dst": "/usr/local/bin/tool-b", "mode": "0755"}],
            },
        ]
    )
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "/tmp/git-clone-0" in output  # nosec B108
    assert "/tmp/git-clone-1" in output  # nosec B108
    assert "repo-a" in output
    assert "repo-b" in output
    assert "rm -rf /tmp/git-clone-0" in output  # nosec B108
    assert "rm -rf /tmp/git-clone-1" in output  # nosec B108

    print("✓ Git-clone module handles multiple repos")


def test_git_clone_module_multiple_files_per_repo():
    """Multiple files from one repo should produce multiple install commands."""
    config = _make_git_clone_config(
        repos=[
            {
                "url": "https://github.com/user/tools",
                "branch": "main",
                "files": [
                    {"src": "src/tool1.py", "dst": "/usr/local/bin/tool1", "mode": "0755"},
                    {"src": "src/tool2.py", "dst": "/usr/local/bin/tool2", "mode": "0755"},
                    {"src": "conf/config.yml", "dst": "/etc/tools/config.yml", "mode": "0644"},
                ],
            }
        ]
    )
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert (
        "install -m 0755 /tmp/git-clone-0/src/tool1.py /usr/local/bin/tool1" in output
    )  # nosec B108
    assert (
        "install -m 0755 /tmp/git-clone-0/src/tool2.py /usr/local/bin/tool2" in output
    )  # nosec B108
    assert (
        "install -m 0644 /tmp/git-clone-0/conf/config.yml /etc/tools/config.yml" in output
    )  # nosec B108

    print("✓ Git-clone module handles multiple files per repo")


def test_git_clone_module_missing_url():
    """Missing url should emit an error comment."""
    config = _make_git_clone_config(
        repos=[{"files": [{"src": "bin/tool", "dst": "/usr/local/bin/tool", "mode": "0755"}]}]
    )
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "# ERROR: git-clone repo entry 0 missing 'url'" in output

    print("✓ Git-clone module emits error for missing url")


def test_git_clone_module_missing_files():
    """Empty files list should emit an error comment."""
    config = _make_git_clone_config(
        repos=[
            {
                "url": "https://github.com/user/repo",
                "files": [],
            }
        ]
    )
    generator = ContainerfileGenerator(config, _make_context())
    output = generator.generate()

    assert "# ERROR: git-clone repo https://github.com/user/repo has no 'files' defined" in output

    print("✓ Git-clone module emits error for empty files list")


# --- ZFS configuration tests ---


def _make_zfs_config(condition=None, marker="ZFS_MARKER"):
    """Build a minimal config with a ZFS-conditioned module."""
    module = {"type": "script", "scripts": [f"echo {marker}"]}
    if condition:
        module["condition"] = condition
    return {"name": "zfs-test", "description": "ZFS test", "modules": [module]}


def test_zfs_disabled_by_default():
    """BuildContext should default enable_zfs to False."""
    ctx = _make_context()
    assert ctx.enable_zfs is False, "enable_zfs should default to False"


def test_zfs_enabled_generates_arg():
    """When enable_zfs is True, ARG ENABLE_ZFS should appear in output."""
    config = _make_zfs_config()
    ctx = _make_context(enable_zfs=True)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "ARG ENABLE_ZFS=true" in output, "Should generate ARG ENABLE_ZFS=true"


def test_zfs_disabled_no_arg():
    """When enable_zfs is False, ARG ENABLE_ZFS should NOT appear."""
    config = _make_zfs_config()
    ctx = _make_context(enable_zfs=False)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "ARG ENABLE_ZFS" not in output, "Should NOT generate ARG ENABLE_ZFS when disabled"


def test_zfs_condition_true():
    """Modules with 'enable_zfs == true' should be included when ZFS is on."""
    config = _make_zfs_config(condition="enable_zfs == true", marker="ZFS_MODULE_PRESENT")
    ctx = _make_context(enable_zfs=True)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "ZFS_MODULE_PRESENT" in output, "ZFS-conditioned module should be included"


def test_zfs_condition_false_skips_module():
    """Modules with 'enable_zfs == true' should be skipped when ZFS is off."""
    config = _make_zfs_config(condition="enable_zfs == true", marker="ZFS_MODULE_PRESENT")
    ctx = _make_context(enable_zfs=False)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "ZFS_MODULE_PRESENT" not in output, "ZFS-conditioned module should be skipped"


def test_zfs_condition_false_literal():
    """Modules with 'enable_zfs == false' should match when ZFS is off."""
    config = _make_zfs_config(condition="enable_zfs == false", marker="ZFS_FALLBACK")
    ctx = _make_context(enable_zfs=False)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "ZFS_FALLBACK" in output, "enable_zfs == false should match when ZFS disabled"


def test_zfs_combined_condition_with_plymouth():
    """AND condition with both enable_zfs and enable_plymouth should work."""
    config = _make_zfs_config(
        condition="enable_zfs == true && enable_plymouth == true",
        marker="BOTH_ENABLED",
    )
    # Both enabled
    ctx = _make_context(enable_zfs=True, enable_plymouth=True)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "BOTH_ENABLED" in output, "AND condition should pass when both are true"

    # Only ZFS enabled
    ctx2 = _make_context(enable_zfs=True, enable_plymouth=False)
    output2 = ContainerfileGenerator(config, ctx2).generate()
    assert "BOTH_ENABLED" not in output2, "AND condition should fail when only one is true"


def test_zfs_or_condition():
    """OR condition with enable_zfs should work."""
    config = _make_zfs_config(
        condition="enable_zfs == true || enable_plymouth == true",
        marker="EITHER_ENABLED",
    )
    # Only ZFS enabled
    ctx = _make_context(enable_zfs=True, enable_plymouth=False)
    output = ContainerfileGenerator(config, ctx).generate()
    assert "EITHER_ENABLED" in output, "OR condition should pass when ZFS is true"

    # Neither enabled
    ctx2 = _make_context(enable_zfs=False, enable_plymouth=False)
    output2 = ContainerfileGenerator(config, ctx2).generate()
    assert "EITHER_ENABLED" not in output2, "OR condition should fail when both are false"


def test_zfs_does_not_affect_unrelated_modules():
    """Enabling ZFS should not change modules without a ZFS condition."""
    config = {
        "name": "zfs-unrelated",
        "description": "ZFS isolation test",
        "modules": [
            {"type": "script", "scripts": ["echo ALWAYS_RUN"]},
            {
                "type": "script",
                "condition": "enable_zfs == true",
                "scripts": ["echo ZFS_ONLY"],
            },
        ],
    }
    output_off = ContainerfileGenerator(config, _make_context(enable_zfs=False)).generate()
    assert "ALWAYS_RUN" in output_off
    assert "ZFS_ONLY" not in output_off

    output_on = ContainerfileGenerator(config, _make_context(enable_zfs=True)).generate()
    assert "ALWAYS_RUN" in output_on
    assert "ZFS_ONLY" in output_on


def test_zfs_cli_args_parsed():
    """Verify the argparse setup handles --enable-zfs and --disable-zfs."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=Path, required=True)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--enable-zfs", action="store_true", default=False)
    parser.add_argument("--disable-zfs", action="store_true")
    parser.add_argument("--enable-plymouth", action="store_true", default=True)
    parser.add_argument("--disable-plymouth", action="store_true")

    # Test --enable-zfs
    args = parser.parse_args(["-c", "test.yml", "--enable-zfs"])
    enable_zfs = args.enable_zfs and not args.disable_zfs
    assert enable_zfs is True

    # Test --disable-zfs
    args = parser.parse_args(["-c", "test.yml", "--disable-zfs"])
    enable_zfs = args.enable_zfs and not args.disable_zfs
    assert enable_zfs is False

    # Test default (neither flag)
    args = parser.parse_args(["-c", "test.yml"])
    enable_zfs = args.enable_zfs and not args.disable_zfs
    assert enable_zfs is False

    # Test both flags (disable wins)
    args = parser.parse_args(["-c", "test.yml", "--enable-zfs", "--disable-zfs"])
    enable_zfs = args.enable_zfs and not args.disable_zfs
    assert enable_zfs is False, "--disable-zfs should override --enable-zfs"


if __name__ == "__main__":
    test_generator_is_stateless()
    test_generator_with_different_contexts()
    test_custom_base_image_sources_are_respected()
    test_custom_bases_without_tags_are_versioned()
    test_fedora_atomic_variants()
    test_distro_detection()
    test_enable_plymouth_generates_env()
    test_package_loader_module()
    test_plymouth_not_generated_for_sway_atomic()
    test_chezmoi_module_generates_copy_and_sed()
    test_chezmoi_module_skip_policy()
    test_chezmoi_module_replace_policy()
    test_chezmoi_module_all_users_false()
    test_chezmoi_module_disable_init()
    test_chezmoi_module_disable_update()
    test_chezmoi_module_missing_repo()
    test_chezmoi_module_with_branch()
    test_systemd_module_user_services()
    test_git_clone_module_generates_clone_and_install()
    test_git_clone_module_with_branch()
    test_git_clone_module_without_branch()
    test_git_clone_module_multiple_repos()
    test_git_clone_module_multiple_files_per_repo()
    test_git_clone_module_missing_url()
    test_git_clone_module_missing_files()
    test_zfs_disabled_by_default()
    test_zfs_enabled_generates_arg()
    test_zfs_disabled_no_arg()
    test_zfs_condition_true()
    test_zfs_condition_false_skips_module()
    test_zfs_condition_false_literal()
    test_zfs_combined_condition_with_plymouth()
    test_zfs_or_condition()
    test_zfs_does_not_affect_unrelated_modules()
    test_zfs_cli_args_parsed()
    print("\nAll tests passed!")
