# isort: skip_file
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from generator.cli import determine_base_image, load_yaml_config, validate_config
from generator.cli import main as generator_main
from generator.context import BuildContext
from generator.generator import ContainerfileGenerator
from package_loader import PackageLoader, PackageValidationError
from package_loader import main as loader_main
from package_loader.validator import validate_config as validator_validate_config

# --- Generator CLI Coverage ---


def test_generator_determine_base_image_unknown():
    """Test determine_base_image with unknown image type and no preferred base."""
    assert determine_base_image({}, "unknown", "43") == "quay.io/fedora/fedora-bootc:43"


def test_generator_main_validate_flag(monkeypatch, tmp_path, capsys):
    """Test main with --validate flag."""
    cfg = tmp_path / "valid.yml"
    cfg.write_text("name: test\ndescription: test\nmodules: []\n")
    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "--validate"])
    with pytest.raises(SystemExit) as exc:
        generator_main()
    assert exc.value.code == 0
    assert "Configuration is valid" in capsys.readouterr().out


def test_generator_load_yaml_errors(tmp_path, capsys):
    """Test load_yaml_config error paths."""
    # FileNotFoundError
    with pytest.raises(SystemExit) as exc:
        load_yaml_config(tmp_path / "missing.yml")
    assert exc.value.code == 1
    assert "Config file not found" in capsys.readouterr().err

    # YAMLError
    bad_yaml = tmp_path / "bad.yml"
    bad_yaml.write_text("invalid: [")
    with pytest.raises(SystemExit) as exc:
        load_yaml_config(bad_yaml)
    assert exc.value.code == 1
    assert "Error parsing YAML" in capsys.readouterr().err


def test_generator_validate_config_failure(capsys):
    """Test validate_config with missing fields."""
    assert validate_config({"name": "test"}) is False
    assert "Missing required field: description" in capsys.readouterr().err


def test_generator_main_exit_on_invalid_config(monkeypatch, tmp_path):
    """Test main exits on invalid config."""
    cfg = tmp_path / "invalid.yml"
    cfg.write_text("name: test")  # Missing fields
    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg)])
    with pytest.raises(SystemExit) as exc:
        generator_main()
    assert exc.value.code == 1


def test_generator_main_verbose(monkeypatch, tmp_path, capsys):
    """Test main with verbose flag."""
    cfg = tmp_path / "valid.yml"
    cfg.write_text("name: test\ndescription: test\nmodules: []\nimage-type: fedora-bootc\n")
    monkeypatch.setattr(sys, "argv", ["prog", "-c", str(cfg), "-v"])

    # Mock generator to avoid full run
    mock_gen = MagicMock()
    mock_gen.generate.return_value = "FROM base"

    generator_main(generator=mock_gen)
    out = capsys.readouterr().out
    assert "Loading configuration from" in out
    assert "Build context:" in out


def test_generator_get_resolved_package_plan_empty():
    """Test get_resolved_package_plan with empty generator."""
    context = BuildContext("type", "43", True, False, "base")
    gen = ContainerfileGenerator({"name": "test"}, context)
    plan = gen.get_resolved_package_plan()
    assert plan["image"]["name"] == "test"
    assert plan["rpm"]["install"] == []


# --- Package Loader Validator Coverage ---


def test_validator_validate_config_spec_groups_dict(tmp_path):
    """Test validator with spec.groups as a dictionary."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    config = {**base, "spec": {"groups": {"install": ["a"], "remove": ["b"]}, "packages": []}}
    validator_validate_config(config, Path("test.yml"))


def test_validator_validate_config_spec_groups_invalid_install(tmp_path):
    """Test validator rejects invalid groups.install."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    config = {**base, "spec": {"groups": {"install": 123}, "packages": []}}
    with pytest.raises(
        PackageValidationError, match="'spec.groups.install' must be a list of strings"
    ):
        validator_validate_config(config, Path("test.yml"))


def test_validator_validate_config_api_version_missing(tmp_path):
    """Test validator rejects missing apiVersion in typed bundle."""
    with pytest.raises(PackageValidationError, match="Unsupported or missing 'apiVersion'"):
        validator_validate_config({"kind": "PackageBundle", "spec": {}}, Path("test.yml"))


def test_validator_validate_config_metadata_name_missing(tmp_path):
    """Test validator rejects empty metadata.name."""
    with pytest.raises(PackageValidationError, match="'metadata.name' must be a non-empty string"):
        validator_validate_config(
            {
                "apiVersion": "exousia.packages/v1alpha1",
                "kind": "PackageBundle",
                "metadata": {"name": ""},
                "spec": {"packages": []},
            },
            Path("test.yml"),
        )


def test_validator_validate_config_metadata_type_invalid(tmp_path):
    """Test validator rejects non-string metadata.type."""
    with pytest.raises(PackageValidationError, match="'metadata.type' must be a non-empty string"):
        validator_validate_config(
            {
                "apiVersion": "exousia.packages/v1alpha1",
                "kind": "PackageBundle",
                "metadata": {"name": "test", "type": 123},
                "spec": {"packages": []},
            },
            Path("test.yml"),
        )


def test_validator_validate_config_groups_invalid_list(tmp_path):
    """Test validator rejects groups list with non-strings."""
    with pytest.raises(PackageValidationError, match="'groups' must be a list of strings"):
        validator_validate_config({"groups": [123]}, Path("test.yml"))


def test_validator_validate_config_spec_groups_invalid_type(tmp_path):
    """Test validator rejects spec.groups with invalid type."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    with pytest.raises(
        PackageValidationError, match="'spec.groups' must be a list or install/remove mapping"
    ):
        validator_validate_config(
            {**base, "spec": {"groups": 123, "packages": []}}, Path("test.yml")
        )


def test_validator_validate_config_spec_conflicts_not_dict(tmp_path):
    """Test validator rejects non-mapping spec.conflicts."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    with pytest.raises(PackageValidationError, match="'spec.conflicts' must be a mapping"):
        validator_validate_config(
            {**base, "spec": {"conflicts": [], "packages": []}}, Path("test.yml")
        )


def test_validator_validate_config_spec_conflicts_packages_not_list(tmp_path):
    """Test validator rejects non-list spec.conflicts.packages."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    with pytest.raises(
        PackageValidationError, match="'spec.conflicts.packages' must be a list of strings"
    ):
        validator_validate_config(
            {**base, "spec": {"conflicts": {"packages": 123}, "packages": []}}, Path("test.yml")
        )


def test_validator_validate_config_spec_requires_not_dict(tmp_path):
    """Test validator rejects non-mapping spec.requires."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    with pytest.raises(PackageValidationError, match="'spec.requires' must be a mapping"):
        validator_validate_config(
            {**base, "spec": {"requires": [], "packages": []}}, Path("test.yml")
        )


def test_validator_validate_config_spec_requires_features_not_list(tmp_path):
    """Test validator rejects non-list spec.requires.features."""
    base = {"apiVersion": "exousia.packages/v1alpha1", "kind": "PackageBundle"}
    with pytest.raises(
        PackageValidationError, match="'spec.requires.features' must be a list of strings"
    ):
        validator_validate_config(
            {**base, "spec": {"requires": {"features": 123}, "packages": []}}, Path("test.yml")
        )


# --- Package Loader Loader Coverage ---


def test_loader_load_yaml_io_error(tmp_path):
    """Test load_yaml raises FileNotFoundError for missing file."""
    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="Package definition not found"):
        loader.load_yaml(tmp_path / "missing.yml")


def test_loader_load_yaml_invalid_yaml(tmp_path):
    """Test load_yaml raises ValueError for invalid YAML."""
    bad = tmp_path / "bad.yml"
    bad.write_text("invalid: [")
    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load_yaml(bad)


def test_loader_flatten_packages_recursive_dict(tmp_path):
    """Test flatten_packages with nested dictionaries."""
    loader = PackageLoader()
    config = {"category1": {"pkg1": ["a", "b"], "category2": {"pkg2": ["c"]}}}
    packages = loader.flatten_packages(config)
    assert sorted(packages) == ["a", "b", "c"]


def test_loader_get_groups_typed_bundle_dict(tmp_path):
    """Test get_groups with typed bundle using dict groups."""
    loader = PackageLoader()
    config = {
        "apiVersion": "exousia.packages/v1alpha1",
        "kind": "PackageBundle",
        "spec": {"groups": {"install": ["group1"], "remove": ["group2"]}},
    }
    assert loader.get_groups(config) == ["group1"]


def test_loader_get_group_actions_invalid(tmp_path):
    """Test get_group_actions with invalid groups type."""
    loader = PackageLoader()
    assert loader.get_group_actions({"groups": 123}) == {"install": [], "remove": []}


# --- Package Loader CLI Coverage ---


def test_loader_main_list_commands(monkeypatch, tmp_path, capsys):
    """Test loader main with list commands."""
    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "sway.yml").write_text("name: sway")

    de_dir = tmp_path / "desktop-environments"
    de_dir.mkdir()
    (de_dir / "gnome.yml").write_text("name: gnome")

    loader = PackageLoader(packages_dir=tmp_path)

    # List WMs
    monkeypatch.setattr(sys, "argv", ["prog", "--list-wms"])
    loader_main(loader=loader)
    assert "sway" in capsys.readouterr().out

    # List DEs
    monkeypatch.setattr(sys, "argv", ["prog", "--list-des"])
    loader_main(loader=loader)
    assert "gnome" in capsys.readouterr().out


# --- Main entrypoints (0% coverage files) ---


def test_generator_main_file_execution():
    """Import __main__ to get coverage for the if __name__ == '__main__' block if possible."""
    import generator.__main__

    assert generator.__main__.main is not None


def test_package_loader_main_file_execution():
    """Import __main__ to get coverage."""
    import package_loader.__main__

    assert package_loader.__main__.main is not None
