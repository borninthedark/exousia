import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.models import ImageType
from tools import distro_mapper


def test_all_image_types_have_distro_mapping():
    for image_type in ImageType:
        distro = distro_mapper.get_distro_for_image_type(image_type.value)
        assert distro is not None, f"Missing mapping for {image_type.value}"


def test_package_manager_resolution_matches_distro():
    expected_managers = {
        "fedora": "dnf",
        "arch": "pacman",
        "debian": "apt",
        "ubuntu": "apt",
        "opensuse": "zypper",
        "gentoo": "emerge",
        "freebsd": "pkg",
    }

    for image_type in ImageType:
        distro = distro_mapper.get_distro_for_image_type(image_type.value)
        pkg_mgr = distro_mapper.get_package_manager_for_image_type(image_type.value)
        assert pkg_mgr == expected_managers[distro]


def test_unknown_image_type_returns_none():
    assert distro_mapper.get_distro_for_image_type("unknown-type") is None
    assert distro_mapper.get_package_manager_for_image_type("unknown-type") is None
    assert distro_mapper.is_supported_distro("unknown-type") is False


def test_supported_distros_are_unique_and_sorted():
    supported = distro_mapper.get_all_supported_distros()
    assert supported == sorted(supported)
    assert len(supported) == len(set(supported))
    assert "fedora" in supported
