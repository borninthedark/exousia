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
        base_image="quay.io/fedora/fedora-sway-atomic:43"
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
        base_image="quay.io/fedora/fedora-sway-atomic:43"
    )

    generator = ContainerfileGenerator(config, context1)
    output1 = generator.generate()

    # Change context - fedora-bootc with Plymouth
    context2 = BuildContext(
        image_type="fedora-bootc",
        fedora_version="43",
        enable_plymouth=True,
        base_image="quay.io/fedora/fedora-bootc:43"
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

    desktop_config = {
        "name": "fedora-desktop",
        "description": "Fedora atomic desktop test",
        "base-image": "quay.io/fedora-ostree-desktops/kinoite-atomic:43",
    }

    desktop_base = determine_base_image(desktop_config, "fedora-atomic-desktop", "43")
    assert desktop_base == "quay.io/fedora-ostree-desktops/kinoite-atomic:43"

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

    untagged_desktop = {
        "name": "fedora-desktop-no-tag",
        "description": "Atomic desktop images also require explicit tags",
        "base-image": "quay.io/fedora-ostree-desktops/kinoite-atomic",
    }

    desktop_base = determine_base_image(untagged_desktop, "fedora-atomic-desktop", "43")
    assert desktop_base == "quay.io/fedora-ostree-desktops/kinoite-atomic:43"

    print("✓ Untagged custom bases are pinned to the requested version")


if __name__ == "__main__":
    test_generator_is_stateless()
    test_generator_with_different_contexts()
    print("\n✅ All tests passed!")
