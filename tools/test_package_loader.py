#!/usr/bin/env python3
"""
Unit tests for package_loader.loader module.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import package_loader.cli
import package_loader.loader
from package_loader import DEFAULT_COMMON_BUNDLES, PackageLoader, PackageValidationError


def _seed_common_bundles(common_dir, content="core:\n  - basepkg\n"):
    """Create all DEFAULT_COMMON_BUNDLES files so load_common('base') works."""
    for bundle in DEFAULT_COMMON_BUNDLES:
        bundle_file = common_dir / f"{bundle}.yml"
        if not bundle_file.exists():
            bundle_file.write_text(content)


def test_loader_init_defaults():
    """Test that PackageLoader initializes correctly."""
    loader = PackageLoader()

    assert loader.packages_dir.exists(), "Packages directory should exist"
    assert loader.wm_dir.exists(), "Window managers directory should exist"
    assert loader.de_dir.exists(), "Desktop environments directory should exist"
    assert loader.common_dir.exists(), "Common directory should exist"


def test_loader_init_overrides(tmp_path):
    """Test that PackageLoader allows overriding all directories."""
    pkg_dir = tmp_path / "pkg"
    wm_dir = tmp_path / "wm"
    de_dir = tmp_path / "de"
    common_dir = tmp_path / "common"
    kernels_dir = tmp_path / "kernels"

    loader = PackageLoader(
        packages_dir=pkg_dir,
        wm_dir=wm_dir,
        de_dir=de_dir,
        common_dir=common_dir,
        kernels_dir=kernels_dir,
    )

    assert loader.packages_dir == pkg_dir
    assert loader.wm_dir == wm_dir
    assert loader.de_dir == de_dir
    assert loader.common_dir == common_dir
    assert loader.kernels_dir == kernels_dir


def test_loader_load_wm(tmp_path):
    """Test loading a window manager configuration."""
    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "sway.yml").write_text("core:\n  - sway\n  - swaylock\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_wm("sway")

    assert "sway" in packages
    assert "swaylock" in packages
    assert len(packages) == 2


def test_loader_load_de(tmp_path):
    """Test loading a desktop environment configuration."""
    de_dir = tmp_path / "desktop-environments"
    de_dir.mkdir()
    (de_dir / "gnome.yml").write_text("main:\n  - gnome-shell\n  - nautilus\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_de("gnome")

    assert "gnome-shell" in packages
    assert "nautilus" in packages


def test_loader_load_common_base(tmp_path):
    """Test loading the base common package set."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    _seed_common_bundles(common_dir, "core:\n  - basepkg\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_common("base")

    assert "basepkg" in packages
    # Should include all default bundles (they all have basepkg in this test)
    assert len(packages) == 1


def test_loader_load_common_named(tmp_path):
    """Test loading a specific common bundle."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "test.yml").write_text("extra:\n  - testpkg\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_common("test")

    assert "testpkg" in packages


def test_loader_load_remove(tmp_path):
    """Test loading the removal list."""
    common_dir = tmp_path / "common"
    common_dir.mkdir()
    (common_dir / "remove.yml").write_text("packages:\n  - badpkg1\n  - badpkg2\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_remove()

    assert "badpkg1" in packages
    assert "badpkg2" in packages


def test_loader_load_yaml_missing(tmp_path):
    """Test that missing YAML file raises FileNotFoundError."""
    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        loader.load_wm("nonexistent")


def test_loader_load_yaml_invalid(tmp_path):
    """Test that invalid YAML raises ValueError."""
    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "broken.yml").write_text("core: [unclosed list")

    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load_wm("broken")


def test_loader_list_available_wms(tmp_path):
    """Test listing available window managers."""
    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "sway.yml").write_text("core: []")
    (wm_dir / "i3.yml").write_text("core: []")

    loader = PackageLoader(packages_dir=tmp_path)
    wms = loader.list_available_wms()

    assert "sway" in wms
    assert "i3" in wms
    assert len(wms) == 2


def test_loader_list_available_des(tmp_path):
    """Test listing available desktop environments."""
    de_dir = tmp_path / "desktop-environments"
    de_dir.mkdir()
    (de_dir / "gnome.yml").write_text("core: []")

    loader = PackageLoader(packages_dir=tmp_path)
    des = loader.list_available_des()

    assert "gnome" in des


def test_loader_get_package_list(tmp_path):
    """Test getting combined package list for a build."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - neovim\n")
    (common / "remove.yml").write_text("packages:\n  - nano\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "sway.yml").write_text("core:\n  - sway\n")

    loader = PackageLoader(packages_dir=tmp_path)
    result = loader.get_package_list(wm="sway")

    assert isinstance(result["install"], list), "Install should be a list"
    assert isinstance(result["remove"], list), "Remove should be a list"

    # Should include both WM and common packages
    assert "sway" in result["install"], "Should include sway"
    assert "neovim" in result["install"], "Should include common packages"
    assert "nano" in result["remove"], "Should include remove list"


def test_loader_get_package_plan_provenance(tmp_path):
    """Test that package plan correctly tracks provenance."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "sway.yml").write_text("core:\n  - wmpkg\n")

    loader = PackageLoader(packages_dir=tmp_path)
    plan = loader.get_package_plan(wm="sway")

    # Verify RPM install section
    install_pkgs = {item["name"]: item["from"] for item in plan["rpm"]["install"]}
    assert "wmpkg" in install_pkgs
    assert "window-manager:sway" in install_pkgs["wmpkg"]

    assert "basepkg" in install_pkgs
    # Should come from one of the default common bundles
    assert any(f.startswith("common:") for f in install_pkgs["basepkg"])

    # Verify RPM remove section
    remove_pkgs = {item["name"]: item["from"] for item in plan["rpm"]["remove"]}
    assert "badpkg" in remove_pkgs
    assert "remove" in remove_pkgs["badpkg"]


def test_loader_get_package_plan_conflicts(tmp_path):
    """Test that conflicts are correctly identified."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common)
    (common / "remove.yml").write_text("packages: []")

    # Create a feature bundle that conflicts with another package
    (common / "conflict.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: FeatureBundle\n"
        "metadata:\n  name: conflict\n"
        "spec:\n"
        "  packages: ['pkg-a']\n"
        "  conflicts:\n"
        "    packages: ['pkg-b']\n"
    )

    # Create another bundle that provides the conflicting package
    (common / "provider.yml").write_text("core:\n  - pkg-b\n")

    loader = PackageLoader(packages_dir=tmp_path)

    with pytest.raises(PackageValidationError, match="conflicts with package 'pkg-b'"):
        loader.get_package_plan(feature_bundles=["conflict", "provider"])


def test_loader_get_package_plan_requirements(tmp_path):
    """Test that missing required features raise validation error."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common)
    (common / "remove.yml").write_text("packages: []")

    # Feature A requires feature B
    (common / "feat-a.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: FeatureBundle\n"
        "metadata:\n  name: feat-a\n"
        "spec:\n"
        "  packages: []\n"
        "  requires:\n"
        "    features: ['feat-b']\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)

    with pytest.raises(PackageValidationError, match="requires missing feature 'feat-b'"):
        loader.get_package_plan(feature_bundles=["feat-a"])


def test_loader_get_package_plan_replaces(tmp_path):
    """Test that replaces field appends to remove list."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common)
    (common / "remove.yml").write_text("packages: []")

    (common / "replacer.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: FeatureBundle\n"
        "metadata:\n  name: replacer\n"
        "spec:\n"
        "  packages: ['new-pkg']\n"
        "  replaces: ['old-pkg']\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    plan = loader.get_package_plan(feature_bundles=["replacer"])

    remove_names = [item["name"] for item in plan["rpm"]["remove"]]
    assert "old-pkg" in remove_names


def test_loader_load_rpm_overrides(tmp_path):
    """Test loading RPM overrides."""
    common = tmp_path / "common"
    common.mkdir()
    (common / "rpm-overrides.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: PackageOverrideBundle\n"
        "spec:\n"
        "  overrides:\n"
        "    - image: 'ghcr.io/org/repo:tag'\n"
        "      reason: 'cve-fix'\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    overrides = loader.load_rpm_overrides()

    assert len(overrides) == 1
    assert overrides[0]["image"] == "ghcr.io/org/repo:tag"


def test_loader_load_kernel_config(tmp_path):
    """Test loading kernel configuration."""
    common = tmp_path / "common"
    common.mkdir()
    (common / "kernel-config.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: KernelConfig\n"
        "spec:\n"
        "  source: 'copr'\n"
        "  copr:\n"
        "    repo: 'user/repo'\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    config = loader.load_kernel_config()

    assert config["source"] == "copr"
    assert config["copr"]["repo"] == "user/repo"


def test_export_to_text_files_writes_legacy_outputs(tmp_path):
    """Test that legacy text export works."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common)
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

    output_dir = tmp_path / "out"
    loader = PackageLoader(packages_dir=tmp_path)

    # Suppress deprecation warning for this test
    with pytest.warns(DeprecationWarning):
        loader.export_to_text_files(wm="test", output_dir=output_dir)

    assert (output_dir / "packages.add").exists()
    assert (output_dir / "packages.remove").exists()

    add_content = (output_dir / "packages.add").read_text()
    assert "wmpkg" in add_content
    assert "basepkg" in add_content

    remove_content = (output_dir / "packages.remove").read_text()
    assert "badpkg" in remove_content


# ---------------------------------------------------------------------------
# CLI tests (main)
# ---------------------------------------------------------------------------


class TestPackageLoaderCLI:
    def test_main_lists_available_bundle_targets(self, tmp_path, capsys):
        """CLI list commands should output available YAML names."""
        wm_dir = tmp_path / "window-managers"
        wm_dir.mkdir()
        (wm_dir / "test-wm.yml").write_text("core:\n  - sway\n")

        de_dir = tmp_path / "desktop-environments"
        de_dir.mkdir()
        (de_dir / "test-de.yml").write_text("core:\n  - gnome-shell\n")

        loader = PackageLoader(packages_dir=tmp_path)

        package_loader.cli.main(argv=["--list-wms"], loader=loader)
        wm_output = capsys.readouterr().out

        package_loader.cli.main(argv=["--list-des"], loader=loader)
        de_output = capsys.readouterr().out

        assert "test-wm" in wm_output
        assert "test-de" in de_output

    def test_main_json_output_uses_explicit_bundle_selection(self, tmp_path, capsys):
        """CLI --json should output a full resolved package plan."""
        common = tmp_path / "common"
        common.mkdir()
        _seed_common_bundles(common)
        (common / "remove.yml").write_text("packages: []\n")

        wm_dir = tmp_path / "window-managers"
        wm_dir.mkdir()
        (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

        loader = PackageLoader(packages_dir=tmp_path)

        package_loader.cli.main(
            argv=["--json", "--wm", "test", "--common", "base-core"], loader=loader
        )
        payload = capsys.readouterr().out

        assert '"window_manager": "test"' in payload
        assert '"common_bundles": [' in payload
        assert '"base-core"' in payload

    def test_main_export_command_uses_selected_output_dir(self, tmp_path, capsys):
        """CLI --export should write legacy files to the specified directory."""
        common = tmp_path / "common"
        common.mkdir()
        _seed_common_bundles(common)
        (common / "remove.yml").write_text("packages: []\n")

        wm_dir = tmp_path / "window-managers"
        wm_dir.mkdir()
        (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

        output_dir = tmp_path / "out"
        loader = PackageLoader(packages_dir=tmp_path)

        package_loader.cli.main(
            argv=["--export", "--wm", "test", "--output-dir", str(output_dir)], loader=loader
        )
        output = capsys.readouterr().out

        assert "Exported package lists" in output
        assert (output_dir / "packages.add").exists()
        assert (output_dir / "packages.remove").exists()

    def test_main_default_mode_prints_install_and_remove_lists(self, tmp_path, capsys):
        """CLI default mode should print resolved install and removal packages."""
        common = tmp_path / "common"
        common.mkdir()
        _seed_common_bundles(common)
        (common / "remove.yml").write_text("packages:\n  - badpkg\n")

        wm_dir = tmp_path / "window-managers"
        wm_dir.mkdir()
        (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

        loader = PackageLoader(packages_dir=tmp_path)

        package_loader.cli.main(argv=["--wm", "test"], loader=loader)
        output = capsys.readouterr().out

        assert "Packages to install:" in output
        assert "basepkg" in output
        assert "wmpkg" in output
        assert "Packages to remove:" in output
        assert "badpkg" in output


def test_export_to_text_files_uses_default_output_dir(tmp_path):
    """Legacy export should default to custom-pkgs/ relative to packages_dir."""
    wm_dir = tmp_path / "packages" / "window-managers"
    wm_dir.mkdir(parents=True)
    (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

    common = tmp_path / "packages" / "common"
    common.mkdir(parents=True)
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    loader = PackageLoader(packages_dir=tmp_path / "packages")
    # Suppress deprecation warning
    with pytest.warns(DeprecationWarning):
        loader.export_to_text_files(wm="test")

    assert (tmp_path / "custom-pkgs" / "packages.add").exists()
    assert (tmp_path / "custom-pkgs" / "packages.remove").exists()


# --- Kernel Profile Tests ---


def test_load_kernel_profile_fedora_default():
    """Test loading the default Fedora kernel profile."""
    loader = PackageLoader()
    profile = loader.load_kernel_profile("fedora-default")

    assert profile["source"] == "repo"
    assert "kernel" in profile["packages"]
    assert "kernel-devel" in profile["devel_packages"]
    assert profile["replaces"] == []


def test_load_kernel_profile_cachyos():
    """Test loading the CachyOS kernel profile."""
    loader = PackageLoader()
    profile = loader.load_kernel_profile("cachyos")

    assert profile["source"] == "copr"
    assert profile["copr"] == {"repo": "bieszczaders/kernel-cachyos"}
    assert "kernel-cachyos" in profile["packages"]
    assert "kernel" in profile["replaces"]


def test_load_kernel_profile_missing():
    """Test that missing kernel profile raises FileNotFoundError."""
    loader = PackageLoader()
    with pytest.raises(FileNotFoundError, match="not found"):
        loader.load_kernel_profile("nonexistent-kernel")


# --- Merged from test_package_logic_deep_dive.py ---


def test_loader_flatten_packages_recursive_nested():
    """Test flatten_packages recursive call with nested dict."""
    loader = PackageLoader()
    config = {"sub": {"pkg1": ["a"]}}
    assert "a" in loader.flatten_packages(config)


def test_loader_get_groups_non_typed_bundle_dict():
    """Test get_groups with non-typed bundle and dict groups."""
    loader = PackageLoader()
    config = {"groups": {"install": ["g1"]}}
    assert loader.get_groups(config) == ["g1"]


def test_loader_get_group_actions_edge_cases():
    """Test get_group_actions with various inputs."""
    loader = PackageLoader()

    # Not a list or dict
    assert loader.get_group_actions({"groups": 123}) == {"install": [], "remove": []}

    # Dict with None values
    assert loader.get_group_actions({"groups": {"install": None, "remove": None}}) == {
        "install": [],
        "remove": [],
    }


def test_loader_bundle_record_no_typed():
    """Test _bundle_record with non-typed bundle."""
    loader = PackageLoader()
    record = loader._bundle_record(Path("test.yml"), {"metadata": {"name": "test"}}, "selected")
    assert record["name"] == "test"
    assert record["kind"] == "unknown"


# --- Merged from test_coverage_gap_filler.py ---


def test_loader_get_groups_list_typed_v2():
    """Test get_groups with typed bundle and list spec.groups."""
    loader = PackageLoader()
    config = {
        "apiVersion": "exousia.packages/v1alpha1",
        "kind": "PackageBundle",
        "spec": {"groups": ["g1", "g2"]},
    }
    assert loader.get_groups(config) == ["g1", "g2"]


def test_loader_get_groups_none_typed_v2():
    """Test get_groups with typed bundle and None spec.groups."""
    loader = PackageLoader()
    config = {
        "apiVersion": "exousia.packages/v1alpha1",
        "kind": "PackageBundle",
        "spec": {"groups": None},
    }
    assert loader.get_groups(config) == []


def test_loader_load_kernel_config_not_found(tmp_path):
    """Test load_kernel_config when file is missing."""
    loader = PackageLoader(common_dir=tmp_path)
    config = loader.load_kernel_config()
    assert config["source"] == "default"


def test_loader_load_rpm_overrides_not_found(tmp_path):
    """Test load_rpm_overrides when file is missing."""
    loader = PackageLoader(common_dir=tmp_path)
    overrides = loader.load_rpm_overrides()
    assert overrides == []


def test_loader_get_package_plan_de_v2(tmp_path):
    """Test get_package_plan with desktop_environment."""
    de_dir = tmp_path / "desktop-environments"
    de_dir.mkdir()
    (de_dir / "kde.yml").write_text("core:\n  - kde-desktop")

    common_dir = tmp_path / "packages" / "common"
    common_dir.mkdir(parents=True)
    (common_dir / "remove.yml").write_text("packages: []")

    loader = PackageLoader(packages_dir=tmp_path / "packages", de_dir=de_dir)
    plan = loader.get_package_plan(de="kde", include_common=False)
    assert any(b["name"] == "kde" for b in plan["bundles"])


def test_loader_main_no_loader_passed_cli():
    """Test loader main handles None loader by creating one."""
    # We use a real directory to avoid errors, but we won't assert on output
    # This just ensures line 50 of cli.py is hit.
    with patch("package_loader.cli.PackageLoader") as mock_loader_class:
        package_loader.cli.main(argv=["--list-wms"])
        mock_loader_class.assert_called_once()
