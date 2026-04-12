#!/usr/bin/env python3
"""
Unit tests for package_loader module
=====================================
"""

import sys
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

import package_loader as package_loader_module
from package_loader import DEFAULT_COMMON_BUNDLES, PackageLoader, PackageValidationError


def _seed_common_bundles(common_dir, content="core:\n  - basepkg\n"):
    """Create all DEFAULT_COMMON_BUNDLES files so load_common('base') works."""
    for bundle in DEFAULT_COMMON_BUNDLES:
        bundle_file = common_dir / f"{bundle}.yml"
        if not bundle_file.exists():
            bundle_file.write_text(content)


def test_package_loader_initialization():
    """Test that PackageLoader initializes correctly."""
    loader = PackageLoader()

    assert loader.packages_dir.exists(), "Packages directory should exist"
    assert loader.wm_dir.exists(), "Window managers directory should exist"
    assert loader.common_dir.exists(), "Common directory should exist"

    print("✓ PackageLoader initializes correctly")


def test_load_sway_packages():
    """Test loading Sway window manager packages."""
    loader = PackageLoader()

    packages = loader.load_wm("sway")

    assert isinstance(packages, list), "Should return a list of packages"
    assert len(packages) > 0, "Should have packages"
    assert "sway" in packages, "Should include sway package"
    assert "waybar" in packages, "Should include waybar package"
    assert "kitty" in packages, "Should include kitty terminal"

    print("✓ Sway packages load correctly")


def test_load_common_packages():
    """Test loading common base packages."""
    loader = PackageLoader()

    packages = loader.load_common("base")

    assert isinstance(packages, list), "Should return a list of packages"
    assert len(packages) > 0, "Should have packages"
    assert "neovim" in packages, "Should include neovim"
    assert "git" in packages, "Should include git"
    flatpak_entries = [p for p in packages if p.startswith("flatpak")]
    assert flatpak_entries, "Should include flatpak"
    # CVE remediation: flatpak must be version-pinned to >= 1.16.5
    pinned = [p for p in flatpak_entries if ">=" in p]
    assert pinned, "flatpak must have a version constraint (>= 1.16.5)"

    print("✓ Common base packages load correctly")


def test_load_remove_packages():
    """Test loading packages to remove."""
    loader = PackageLoader()

    packages = loader.load_remove()

    assert isinstance(packages, list), "Should return a list of packages"
    assert "firefox-langpacks" in packages, "Should include firefox-langpacks"
    assert "foot" not in packages, "WM-specific removals should not live in default remove bundle"

    print("✓ Remove packages load correctly")


def test_get_package_list_with_wm():
    """Test getting complete package list for a window manager."""
    loader = PackageLoader()

    result = loader.get_package_list(wm="sway", include_common=True)

    assert "install" in result, "Should have install key"
    assert "remove" in result, "Should have remove key"
    assert isinstance(result["install"], list), "Install should be a list"
    assert isinstance(result["remove"], list), "Remove should be a list"

    # Should include both WM and common packages
    assert "sway" in result["install"], "Should include sway"
    assert "neovim" in result["install"], "Should include common packages"

    # Should not have removed packages in install list
    for pkg in result["remove"]:
        assert (
            pkg not in result["install"]
        ), f"Package {pkg} should not be in both install and remove"

    for pkg in ("foot", "dunst", "rofi", "rofi-wayland"):
        assert pkg in result["remove"], f"{pkg} should be removed by the sway bundle"

    print("✓ Complete package list generation works correctly")


def test_package_list_without_common():
    """Test getting package list without common packages."""
    loader = PackageLoader()

    result = loader.get_package_list(wm="sway", include_common=False)

    assert "sway" in result["install"], "Should include sway"

    # Should not include common packages when disabled
    # (though some overlap may exist in WM-specific definitions)

    print("✓ Package list generation without common packages works")


def test_flatten_packages():
    """Test the flatten_packages method."""
    loader = PackageLoader()

    config = {
        "metadata": {"name": "test", "type": "test"},
        "core": ["pkg1", "pkg2"],
        "utilities": {"shell": ["bash", "zsh"], "editor": ["vim"]},
    }

    packages = loader.flatten_packages(config)

    assert "pkg1" in packages, "Should include core packages"
    assert "pkg2" in packages, "Should include core packages"
    assert "bash" in packages, "Should include nested packages"
    assert "zsh" in packages, "Should include nested packages"
    assert "vim" in packages, "Should include nested packages"
    assert "test" not in packages, "Should not include metadata"

    print("✓ Package flattening works correctly")


def test_list_available_wms():
    """Test listing available window managers."""
    loader = PackageLoader()

    wms = loader.list_available_wms()

    assert isinstance(wms, list), "Should return a list"
    assert "sway" in wms, "Should include sway"

    print("✓ Listing available WMs works correctly")


def test_list_available_des():
    """Test listing available desktop environments."""
    loader = PackageLoader()

    des = loader.list_available_des()

    assert isinstance(des, list), "Should return a list"
    # May or may not have DEs, but should return a list

    print("✓ Listing available DEs works correctly")


def test_no_duplicate_packages():
    """Test that package lists don't have duplicates."""
    loader = PackageLoader()

    result = loader.get_package_list(wm="sway", include_common=True)

    install_packages = result["install"]
    unique_packages = set(install_packages)

    assert len(install_packages) == len(
        unique_packages
    ), f"Install list has duplicates: {len(install_packages)} vs {len(unique_packages)}"

    print("✓ Package lists are deduplicated correctly")


def test_custom_packages_dir(tmp_path):
    """Test PackageLoader with a custom packages directory."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - testpkg\n")
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    loader = PackageLoader(packages_dir=tmp_path)
    assert loader.packages_dir == tmp_path
    pkgs = loader.load_common("base")
    assert "testpkg" in pkgs


def test_load_yaml_file_not_found(tmp_path):
    """Test that missing YAML files raise FileNotFoundError."""
    import pytest

    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(FileNotFoundError, match="not found"):
        loader.load_yaml(tmp_path / "nonexistent.yml")


def test_load_yaml_invalid_yaml(tmp_path):
    """Test that invalid YAML raises ValueError."""
    import pytest

    bad = tmp_path / "bad.yml"
    bad.write_text(":\n  invalid: [\n")
    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid YAML"):
        loader.load_yaml(bad)


def test_get_groups():
    """Test extracting groups from config."""
    loader = PackageLoader()
    config = {"groups": ["group-a", "group-b"], "core": ["pkg1"]}
    groups = loader.get_groups(config)
    assert groups == ["group-a", "group-b"]


def test_get_groups_missing():
    """Test get_groups returns empty list when no groups key."""
    loader = PackageLoader()
    assert loader.get_groups({"core": ["pkg1"]}) == []


def test_get_group_actions_with_mapping():
    """Typed/legacy group mappings should preserve install/remove actions."""
    loader = PackageLoader()
    config = {"groups": {"install": ["group-a"], "remove": ["group-b"]}, "core": ["pkg1"]}

    actions = loader.get_group_actions(config)
    assert actions == {"install": ["group-a"], "remove": ["group-b"]}


def test_get_package_list_includes_groups(tmp_path):
    """Test that get_package_list collects groups from WM config."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text("groups:\n  - sway-group\ncore:\n  - wmpkg\n")

    loader = PackageLoader(packages_dir=tmp_path)
    result = loader.get_package_list(wm="test")
    assert "sway-group" in result["groups"]
    assert "basepkg" in result["install"]
    assert "wmpkg" in result["install"]


def test_list_wms_empty_dir(tmp_path):
    """Test list_available_wms with no wm directory."""
    loader = PackageLoader(packages_dir=tmp_path)
    assert loader.list_available_wms() == []


def test_list_des_empty_dir(tmp_path):
    """Test list_available_des with no de directory."""
    loader = PackageLoader(packages_dir=tmp_path)
    assert loader.list_available_des() == []


def test_get_package_list_with_extras(tmp_path):
    """Test that extras loads additional common package sets."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")
    (common / "audio-production.yml").write_text(
        "groups:\n  - audio-group\nrealtime:\n  - tuned\nplugins:\n  - lsp-plugins\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    result = loader.get_package_list(extras=["audio-production"])

    assert "basepkg" in result["install"]
    assert "tuned" in result["install"]
    assert "lsp-plugins" in result["install"]
    assert "audio-group" in result["groups"]


def test_get_package_list_extras_none(tmp_path):
    """Test that extras=None does not load extra packages."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")

    loader = PackageLoader(packages_dir=tmp_path)
    result = loader.get_package_list(extras=None)

    assert result["install"] == ["basepkg"]
    assert result["groups"] == []


def test_get_package_plan_includes_provenance(tmp_path):
    """Resolved plan should retain bundle provenance for installs/removals."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text(
        "metadata:\n  name: remove\n  type: common\npackages:\n  - badpkg\n"
    )
    (common / "audio-production.yml").write_text(
        "metadata:\n  name: audio-production\n  type: common\nplugins:\n  - tuned\n"
    )

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text(
        "metadata:\n  name: sway\n  type: window-manager\ncore:\n  - sway\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    plan = loader.get_package_plan(
        wm="test",
        include_common=False,
        common_bundles=["base-core"],
        feature_bundles=["audio-production"],
    )

    install = {item["name"]: item["from"] for item in plan["rpm"]["install"]}
    remove = {item["name"]: item["from"] for item in plan["rpm"]["remove"]}

    assert install["basepkg"] == ["base-core"]
    assert install["tuned"] == ["audio-production"]
    assert install["sway"] == ["sway"]
    assert remove["badpkg"] == ["remove"]


def test_get_package_plan_includes_group_actions(tmp_path):
    """Resolved plan should preserve group install/remove provenance."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text(
        "groups:\n  install:\n    - workstation-product-environment\n  remove:\n    - legacy-xfce-support\ncore:\n  - wmpkg\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    plan = loader.get_package_plan(wm="test")

    assert plan["rpm"]["groups"]["install"] == [
        {"name": "workstation-product-environment", "from": ["test"]}
    ]
    assert plan["rpm"]["groups"]["remove"] == [{"name": "legacy-xfce-support", "from": ["test"]}]


def test_get_package_plan_attributes_sway_conflict_removals():
    """WM-owned removals should be attributed to the selected WM bundle."""
    loader = PackageLoader()
    plan = loader.get_package_plan(wm="sway")

    remove = {item["name"]: item["from"] for item in plan["rpm"]["remove"]}

    assert remove["foot"] == ["wm-sway"]
    assert remove["dunst"] == ["wm-sway"]
    assert remove["rofi"] == ["wm-sway"]
    assert remove["rofi-wayland"] == ["wm-sway"]
    assert remove["firefox"] == ["remove"]


def test_load_yaml_rejects_invalid_package_value_type(tmp_path):
    """Scalar package values should fail validation."""
    import pytest

    bad = tmp_path / "bad.yml"
    bad.write_text("metadata:\n  name: bad\ncore: true\n")
    loader = PackageLoader(packages_dir=tmp_path)

    with pytest.raises(PackageValidationError, match="Unsupported value type"):
        loader.load_yaml(bad)


def test_load_yaml_accepts_package_objects(tmp_path):
    """Future-friendly package objects with name should be accepted."""
    definition = tmp_path / "pkg.yml"
    definition.write_text("metadata:\n  name: demo\ncore:\n  - name: package-a\n  - package-b\n")
    loader = PackageLoader(packages_dir=tmp_path)
    config = loader.load_yaml(definition)

    assert loader.flatten_packages(config) == ["package-a", "package-b"]


def test_typed_bundle_schema_loads_and_flattens(tmp_path):
    """Typed bundles should validate and flatten via spec.packages."""
    common = tmp_path / "common"
    common.mkdir()
    typed_content = (
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: PackageBundle\n"
        "metadata:\n"
        "  name: base-core\n"
        "spec:\n"
        "  packages:\n"
        "    - name: pkg-a\n"
        "    - pkg-b\n"
    )
    _seed_common_bundles(common)
    (common / "base-core.yml").write_text(typed_content)
    (common / "remove.yml").write_text("packages: []\n")

    loader = PackageLoader(packages_dir=tmp_path)
    packages = loader.load_common("base")

    assert "pkg-a" in packages
    assert "pkg-b" in packages


def test_package_plan_rejects_conflicting_features(tmp_path):
    """Typed bundles should reject selected conflicting features."""
    import pytest

    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")
    (common / "audio.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: FeatureBundle\n"
        "metadata:\n"
        "  name: audio\n"
        "spec:\n"
        "  packages:\n"
        "    - audacity\n"
        "  conflicts:\n"
        "    features:\n"
        "      - gaming\n"
    )
    (common / "gaming.yml").write_text(
        "apiVersion: exousia.packages/v1alpha1\n"
        "kind: FeatureBundle\n"
        "metadata:\n"
        "  name: gaming\n"
        "spec:\n"
        "  packages:\n"
        "    - steam\n"
    )

    loader = PackageLoader(packages_dir=tmp_path)
    with pytest.raises(PackageValidationError, match="conflicts with selected feature"):
        loader.get_package_plan(extras=["audio", "gaming"])


def test_export_to_text_files_writes_legacy_outputs(tmp_path):
    """Legacy export should write both install and remove package lists."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

    output_dir = tmp_path / "legacy-out"
    loader = PackageLoader(packages_dir=tmp_path)
    loader.export_to_text_files(wm="test", output_dir=output_dir)

    add_file = output_dir / "packages.add"
    remove_file = output_dir / "packages.remove"

    assert add_file.exists()
    assert remove_file.exists()
    assert "basepkg" in add_file.read_text()
    assert "wmpkg" in add_file.read_text()
    assert "badpkg" in remove_file.read_text()


def test_main_lists_available_bundle_targets(tmp_path, monkeypatch, capsys):
    """CLI should print available WM and DE bundle names."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common)
    (common / "remove.yml").write_text("packages: []\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test-wm.yml").write_text("core:\n  - sway\n")

    de_dir = tmp_path / "desktop-environments"
    de_dir.mkdir()
    (de_dir / "test-de.yml").write_text("core:\n  - gnome-shell\n")

    monkeypatch.setattr(
        package_loader_module, "PackageLoader", lambda: PackageLoader(packages_dir=tmp_path)
    )

    monkeypatch.setattr(sys, "argv", ["package_loader.py", "--list-wms"])
    package_loader_module.main()
    wm_output = capsys.readouterr().out

    monkeypatch.setattr(sys, "argv", ["package_loader.py", "--list-des"])
    package_loader_module.main()
    de_output = capsys.readouterr().out

    assert "test-wm" in wm_output
    assert "test-de" in de_output


def test_main_json_output_uses_explicit_bundle_selection(tmp_path, monkeypatch, capsys):
    """CLI JSON mode should emit the resolved package plan."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages: []\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

    monkeypatch.setattr(
        package_loader_module, "PackageLoader", lambda: PackageLoader(packages_dir=tmp_path)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_loader.py",
            "--json",
            "--wm",
            "test",
            "--common-bundle",
            "base-core",
        ],
    )

    package_loader_module.main()
    payload = capsys.readouterr().out

    assert '"window_manager": "test"' in payload
    assert '"common_bundles": [' in payload
    assert '"base-core"' in payload


def test_main_export_command_uses_selected_output_dir(tmp_path, monkeypatch, capsys):
    """CLI export mode should write legacy output files to the requested directory."""
    common = tmp_path / "common"
    common.mkdir()
    _seed_common_bundles(common, content="core:\n  - basepkg\n")
    (common / "remove.yml").write_text("packages:\n  - badpkg\n")

    wm_dir = tmp_path / "window-managers"
    wm_dir.mkdir()
    (wm_dir / "test.yml").write_text("core:\n  - wmpkg\n")

    output_dir = tmp_path / "out"
    monkeypatch.setattr(
        package_loader_module, "PackageLoader", lambda: PackageLoader(packages_dir=tmp_path)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "package_loader.py",
            "--export",
            "--wm",
            "test",
            "--output-dir",
            str(output_dir),
        ],
    )

    package_loader_module.main()
    output = capsys.readouterr().out

    assert "Exported package lists" in output
    assert (output_dir / "packages.add").exists()
    assert (output_dir / "packages.remove").exists()
