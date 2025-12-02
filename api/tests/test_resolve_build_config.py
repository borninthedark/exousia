"""Unit tests for build configuration resolution helpers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

# Load the resolve_build_config module from the tools directory
REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_PATH = REPO_ROOT.parent / "tools" / "resolve_build_config.py"

_spec = importlib.util.spec_from_file_location("resolve_build_config", TOOLS_PATH)
resolve_build_config = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
assert _spec and _spec.loader
_spec.loader.exec_module(resolve_build_config)  # type: ignore[arg-type]


@pytest.fixture()
def tmp_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolated workspace so helper functions write into a temp directory."""

    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_read_fedora_version_file_defaults(tmp_workspace: Path):
    version, image_type = resolve_build_config.read_fedora_version_file(
        tmp_workspace / ".fedora-version"
    )

    assert version == resolve_build_config.DEFAULT_VERSION
    assert image_type == resolve_build_config.DEFAULT_IMAGE_TYPE


def test_read_fedora_version_file_populates_values(tmp_workspace: Path):
    version_file = tmp_workspace / ".fedora-version"
    version_file.write_text("44:fedora-bootc")

    version, image_type = resolve_build_config.read_fedora_version_file(version_file)

    assert version == "44"
    assert image_type == "fedora-bootc"


def test_read_fedora_version_file_warns_on_malformed(tmp_workspace: Path, capsys: pytest.CaptureFixture[str]):
    version_file = tmp_workspace / ".fedora-version"
    version_file.write_text("invalid-content")

    version, image_type = resolve_build_config.read_fedora_version_file(version_file)
    captured = capsys.readouterr()

    assert version == resolve_build_config.DEFAULT_VERSION
    assert image_type == resolve_build_config.DEFAULT_IMAGE_TYPE
    assert "malformed" in captured.out


def test_apply_fedora_overrides_updates_base_image_and_desktop(tmp_workspace: Path):
    config_path = tmp_workspace / "adnyeus.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "image-version": "43",
                "base-image": "quay.io/fedora/fedora-bootc:43",
                "desktop": {"desktop_environment": "sway"},
            }
        )
    )

    resolved = resolve_build_config.apply_fedora_overrides(
        yaml_config=config_path,
        target_image_type="fedora-bootc",
        target_version="44",
        window_manager="river",
        desktop_environment="",
    )
    updated = yaml.safe_load(resolved.read_text())

    assert resolved.name == "resolved-config.yml"
    assert updated["image-version"] == "44"
    assert updated["base-image"] == "quay.io/fedora/fedora-bootc:44"
    assert updated["desktop"]["window_manager"] == "river"
    assert "desktop_environment" not in updated["desktop"]


def test_apply_fedora_overrides_keeps_custom_base_image(tmp_workspace: Path):
    config_path = tmp_workspace / "custom.yml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "image-version": "rawhide",
                "base-image": "ghcr.io/custom/image:latest",
                "desktop": {"window_manager": "sway"},
            }
        )
    )

    resolved = resolve_build_config.apply_fedora_overrides(
        yaml_config=config_path,
        target_image_type="fedora-sway-atomic",
        target_version="rawhide",
        window_manager="",
        desktop_environment="",
    )
    updated = yaml.safe_load(resolved.read_text())

    assert updated["base-image"] == "ghcr.io/custom/image:latest"
    assert updated["image-version"] == "rawhide"


def test_resolve_yaml_config_prefers_matching_definition(tmp_workspace: Path):
    yaml_definitions = tmp_workspace / "yaml-definitions"
    yaml_definitions.mkdir()
    fedora_bootc = yaml_definitions / "fedora-bootc.yml"
    fedora_bootc.write_text("name: test\nmodules: []\n")

    selected = resolve_build_config.resolve_yaml_config("auto", "fedora-bootc")

    assert selected == fedora_bootc


def test_resolve_yaml_config_falls_back_to_default(tmp_workspace: Path):
    default_yaml = tmp_workspace / "adnyeus.yml"
    default_yaml.write_text("name: default\nmodules: []\n")

    selected = resolve_build_config.resolve_yaml_config("auto", "fedora-bootc")

    assert selected == default_yaml


def test_resolve_yaml_config_errors_when_missing(tmp_workspace: Path):
    with pytest.raises(SystemExit):
        resolve_build_config.resolve_yaml_config("auto", "fedora-bootc")


def test_apply_desktop_override_rewrites_bootc_yaml():
    from api.routers.build import apply_desktop_override

    yaml_content = yaml.safe_dump({"desktop": {"desktop_environment": "sway"}})
    updated_yaml = apply_desktop_override(
        yaml_content=yaml_content,
        image_type="fedora-bootc",
        window_manager="river",
        desktop_environment=None,
    )
    updated = yaml.safe_load(updated_yaml)

    assert updated["desktop"]["window_manager"] == "river"
    assert "desktop_environment" not in updated["desktop"]


def test_apply_desktop_override_ignores_non_bootc():
    from api.routers.build import apply_desktop_override

    yaml_content = yaml.safe_dump({"desktop": {"desktop_environment": "sway"}})
    unchanged = apply_desktop_override(
        yaml_content=yaml_content,
        image_type="fedora-sway-atomic",
        window_manager="river",
        desktop_environment=None,
    )

    assert yaml.safe_load(unchanged) == yaml.safe_load(yaml_content)
