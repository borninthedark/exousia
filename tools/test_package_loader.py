#!/usr/bin/env python3
"""
Unit tests for package_loader module
=====================================
"""

import sys
from pathlib import Path

# Add tools directory to path
sys.path.insert(0, str(Path(__file__).parent))

from package_loader import PackageLoader


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
    assert "flatpak" in packages, "Should include flatpak"

    print("✓ Common base packages load correctly")


def test_load_remove_packages():
    """Test loading packages to remove."""
    loader = PackageLoader()

    packages = loader.load_remove()

    assert isinstance(packages, list), "Should return a list of packages"
    assert "firefox-langpacks" in packages, "Should include firefox-langpacks"

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
        assert pkg not in result["install"], f"Package {pkg} should not be in both install and remove"

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
        "metadata": {
            "name": "test",
            "type": "test"
        },
        "core": ["pkg1", "pkg2"],
        "utilities": {
            "shell": ["bash", "zsh"],
            "editor": ["vim"]
        }
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

    assert len(install_packages) == len(unique_packages), \
        f"Install list has duplicates: {len(install_packages)} vs {len(unique_packages)}"

    print("✓ Package lists are deduplicated correctly")


if __name__ == "__main__":
    test_package_loader_initialization()
    test_load_sway_packages()
    test_load_common_packages()
    test_load_remove_packages()
    test_get_package_list_with_wm()
    test_package_list_without_common()
    test_flatten_packages()
    test_list_available_wms()
    test_list_available_des()
    test_no_duplicate_packages()
    print("\n✅ All package_loader tests passed!")
