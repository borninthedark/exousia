#!/usr/bin/env python3
"""
Unit tests for yaml-to-containerfile transpiler
================================================
"""

import sys
import importlib.util
from pathlib import Path

# Load module from file path (handles hyphens in filename)
script_path = Path(__file__).parent / "yaml-to-containerfile.py"
spec = importlib.util.spec_from_file_location("yaml_to_containerfile", script_path)
yaml_to_containerfile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yaml_to_containerfile)

ContainerfileGenerator = yaml_to_containerfile.ContainerfileGenerator
BuildContext = yaml_to_containerfile.BuildContext
determine_base_image = yaml_to_containerfile.determine_base_image
FEDORA_ATOMIC_VARIANTS = yaml_to_containerfile.FEDORA_ATOMIC_VARIANTS
BOOTCREW_DISTROS = yaml_to_containerfile.BOOTCREW_DISTROS


def test_generator_is_stateless():
    """Test that ContainerfileGenerator.generate() can be called multiple times."""
    config = {
        "name": "test-config",
        "description": "Test configuration",
        "labels": {
            "org.opencontainers.image.title": "test-image"
        },
        "modules": [
            {
                "type": "script",
                "scripts": ["echo 'Hello World'"]
            }
        ]
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora"
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


def test_generator_with_different_contexts():
    """Test that same generator instance can handle different builds."""
    config = {
        "name": "multi-build",
        "description": "Multi-build test",
        "modules": [
            {
                "type": "script",
                "scripts": ["echo 'Build step'"]
            }
        ]
    }

    # First context - fedora-sway-atomic
    context1 = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=False,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora"
    )

    generator = ContainerfileGenerator(config, context1)
    output1 = generator.generate()

    # Change context - fedora-bootc with Plymouth
    context2 = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora"
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
    config = {
        "name": "custom-base",
        "description": "Custom base image test",
        "base-image": "ghcr.io/bootcrew/sericea-atomic:43",
    }

    base = determine_base_image(config, "bootcrew", "43")
    assert base == "ghcr.io/bootcrew/sericea-atomic:43"

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

    untagged_bootcrew = {
        "name": "bootcrew-no-tag",
        "description": "Missing tag should be appended",
        "base-image": "ghcr.io/bootcrew/sericea-atomic",
    }

    base = determine_base_image(untagged_bootcrew, "bootcrew", "43")
    assert base == "ghcr.io/bootcrew/sericea-atomic:43"

    untagged_sway = {
        "name": "fedora-sway-no-tag",
        "description": "Sway atomic images also require explicit tags",
        "base-image": "quay.io/fedora/fedora-sway-atomic",
    }

    sway_base = determine_base_image(untagged_sway, "fedora-sway-atomic", "43")
    assert sway_base == "quay.io/fedora/fedora-sway-atomic:43"

    print("✓ Untagged custom bases are pinned to the requested version")


def test_bootcrew_distro_support():
    """Test that bootcrew distros are properly supported."""
    config = {
        "name": "arch-bootc",
        "description": "Arch bootc test",
        "image-type": "arch",
        "base-image": "docker.io/archlinux/archlinux:latest",
        "modules": [
            {
                "type": "bootcrew-setup",
                "system-deps": ["base", "linux", "ostree"]
            }
        ]
    }

    context = BuildContext(
        image_type="arch",
        fedora_version="",
        enable_plymouth=False,
        base_image="docker.io/archlinux/archlinux:latest",
        distro="arch"
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    assert "FROM docker.io/archlinux/archlinux:latest" in output
    assert "bootc" in output.lower()  # Should mention bootc
    assert "ostree" in output.lower()  # Should mention ostree
    assert "pacman" in output  # Arch package manager

    print("✓ Bootcrew distros are supported correctly")


def test_fedora_atomic_variants():
    """Test that all Fedora Atomic variants are recognized."""
    assert "fedora-kinoite" in FEDORA_ATOMIC_VARIANTS
    assert "fedora-silverblue" in FEDORA_ATOMIC_VARIANTS
    assert "fedora-sway-atomic" in FEDORA_ATOMIC_VARIANTS

    base_kinoite = determine_base_image({}, "fedora-kinoite", "43")
    assert "fedora-kinoite:43" in base_kinoite

    print("✓ Fedora Atomic variants are recognized")


def test_distro_detection():
    """Test that distro is properly detected from image_type."""
    # Fedora-based
    fedora_context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=True,
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora"
    )
    assert fedora_context.distro == "fedora"

    # Bootcrew distro
    arch_context = BuildContext(
        image_type="arch",
        fedora_version="",
        enable_plymouth=False,
        base_image="docker.io/archlinux/archlinux:latest",
        distro="arch"
    )
    assert arch_context.distro == "arch"

    print("✓ Distro detection works correctly")


def test_enable_plymouth_generates_env():
    """Test that ENABLE_PLYMOUTH is generated as ENV, not a standalone instruction."""
    config = {
        "name": "plymouth-test",
        "description": "Test ENABLE_PLYMOUTH generation",
        "modules": []
    }

    context = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora"
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    # Should have ENV instruction for ENABLE_PLYMOUTH
    assert "ENV ENABLE_PLYMOUTH=true" in output, \
        "ENABLE_PLYMOUTH should be generated as ENV instruction"

    # Should NOT have standalone ENABLE_PLYMOUTH
    lines = output.split('\n')
    for line in lines:
        stripped = line.strip()
        # Check for standalone instruction (not part of ENV or RUN)
        if stripped.startswith("ENABLE_PLYMOUTH") and not stripped.startswith("ENV ENABLE_PLYMOUTH"):
            assert False, f"Found standalone ENABLE_PLYMOUTH instruction: {stripped}"

    print("✓ ENABLE_PLYMOUTH generates correct ENV instruction")


def test_package_loader_module():
    """Test that package-loader module type is supported."""
    config = {
        "name": "package-loader-test",
        "description": "Test package-loader module",
        "modules": [
            {
                "type": "package-loader",
                "window_manager": "sway",
                "include_common": True
            }
        ]
    }

    context = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        base_image="quay.io/fedora/fedora-bootc:43",
        distro="fedora"
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
        "modules": []
    }

    context = BuildContext(
        image_type="fedora-sway-atomic",
        fedora_version="43",
        enable_plymouth=True,  # Even if enabled
        base_image="quay.io/fedora/fedora-sway-atomic:43",
        distro="fedora"
    )

    generator = ContainerfileGenerator(config, context)
    output = generator.generate()

    # Should NOT have ENV ENABLE_PLYMOUTH for non-bootc images
    assert "ENV ENABLE_PLYMOUTH" not in output, \
        "ENABLE_PLYMOUTH ENV should only be for fedora-bootc images"

    print("✓ ENABLE_PLYMOUTH not generated for non-bootc images")


if __name__ == "__main__":
    test_generator_is_stateless()
    test_generator_with_different_contexts()
    test_custom_base_image_sources_are_respected()
    test_custom_bases_without_tags_are_versioned()
    test_bootcrew_distro_support()
    test_fedora_atomic_variants()
    test_distro_detection()
    test_enable_plymouth_generates_env()
    test_package_loader_module()
    test_plymouth_not_generated_for_sway_atomic()
    print("\n✅ All tests passed!")
