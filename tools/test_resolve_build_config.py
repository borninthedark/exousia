#!/usr/bin/env python3
"""
Unit tests for resolve_build_config.py -- ZFS and output rendering
==================================================================
"""

import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path

# Load module from file path
script_path = Path(__file__).parent / "resolve_build_config.py"
spec = importlib.util.spec_from_file_location("resolve_build_config", script_path)
assert spec is not None, f"Could not load module spec from {script_path}"
resolve_build_config = importlib.util.module_from_spec(spec)
sys.modules["resolve_build_config"] = resolve_build_config
assert spec.loader is not None, "Module spec has no loader"
spec.loader.exec_module(resolve_build_config)

render_outputs = resolve_build_config.render_outputs
resolve_yaml_config = resolve_build_config.resolve_yaml_config


@contextmanager
def working_directory(path: Path):
    """Temporarily change the process working directory."""
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def _read_outputs(tmp_path, **kwargs):
    """Helper: call render_outputs and return parsed key=value dict."""
    defaults = {
        "build_version": "43",
        "build_image_type": "fedora-sway-atomic",
        "os_family": "fedora",
        "os_version": "43",
        "resolved_config": Path("Dockerfile.generated"),
        "enable_plymouth": True,
        "enable_zfs": False,
    }
    defaults.update(kwargs)
    output_file = tmp_path / "GITHUB_OUTPUT"
    output_file.touch()
    render_outputs(output_file, **defaults)
    lines = output_file.read_text().strip().splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def test_render_outputs_includes_enable_zfs_false(tmp_path):
    """ENABLE_ZFS=false should appear when ZFS is disabled."""
    kv = _read_outputs(tmp_path, enable_zfs=False)
    assert "ENABLE_ZFS" in kv, "ENABLE_ZFS key should be in output"
    assert kv["ENABLE_ZFS"] == "false"


def test_render_outputs_includes_enable_zfs_true(tmp_path):
    """ENABLE_ZFS=true should appear when ZFS is enabled."""
    kv = _read_outputs(tmp_path, enable_zfs=True)
    assert kv["ENABLE_ZFS"] == "true"


def test_render_outputs_all_keys_present(tmp_path):
    """All expected keys should be written."""
    kv = _read_outputs(tmp_path)
    expected_keys = {
        "BUILD_VERSION",
        "BUILD_IMAGE_TYPE",
        "OS_FAMILY",
        "OS_VERSION",
        "RESOLVED_CONFIG",
        "ENABLE_PLYMOUTH",
        "ENABLE_ZFS",
    }
    assert expected_keys == set(kv.keys()), f"Missing keys: {expected_keys - set(kv.keys())}"


def test_render_outputs_plymouth_and_zfs_independent(tmp_path):
    """Plymouth and ZFS should be independently controllable."""
    kv = _read_outputs(tmp_path, enable_plymouth=False, enable_zfs=True)
    assert kv["ENABLE_PLYMOUTH"] == "false"
    assert kv["ENABLE_ZFS"] == "true"

    kv2 = _read_outputs(tmp_path, enable_plymouth=True, enable_zfs=False)
    assert kv2["ENABLE_PLYMOUTH"] == "true"
    assert kv2["ENABLE_ZFS"] == "false"


def test_render_outputs_appends_to_existing(tmp_path):
    """render_outputs should append, not overwrite existing content."""
    output_file = tmp_path / "GITHUB_OUTPUT"
    output_file.write_text("EXISTING_KEY=existing_value\n")
    render_outputs(
        output_file,
        build_version="43",
        build_image_type="fedora-bootc",
        os_family="fedora",
        os_version="43",
        resolved_config=Path("Dockerfile.generated"),
        enable_plymouth=True,
        enable_zfs=True,
    )
    content = output_file.read_text()
    assert "EXISTING_KEY=existing_value" in content, "Should preserve existing content"
    assert "ENABLE_ZFS=true" in content, "Should append new content"


def test_resolve_yaml_config_auto_prefers_adnyeus(tmp_path):
    """Auto resolution should prefer adnyeus.yml as the authoritative blueprint."""
    with working_directory(tmp_path):
        (tmp_path / "adnyeus.yml").write_text("name: canonical\n")
        definitions_dir = tmp_path / "yaml-definitions"
        definitions_dir.mkdir()
        (definitions_dir / "sway.yml").write_text("name: fallback\n")

        resolved = resolve_yaml_config("auto", "fedora-sway-atomic")

    assert resolved == (tmp_path / "adnyeus.yml").resolve()


def test_resolve_yaml_config_explicit_path_still_wins(tmp_path):
    """Explicit yaml_config input should override the adnyeus default."""
    with working_directory(tmp_path):
        (tmp_path / "adnyeus.yml").write_text("name: canonical\n")
        definitions_dir = tmp_path / "yaml-definitions"
        definitions_dir.mkdir()
        (definitions_dir / "custom.yml").write_text("name: explicit\n")

        resolved = resolve_yaml_config("custom.yml", "fedora-sway-atomic")

    assert resolved == (definitions_dir / "custom.yml").resolve()
