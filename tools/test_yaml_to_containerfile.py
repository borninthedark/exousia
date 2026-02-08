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
    print("\n✅ All tests passed!")
