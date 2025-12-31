#!/usr/bin/env python3
"""
Distro Mapper for Package Validation
=====================================

Maps image types to package manager distros for the dependency transpiler.
This ensures package validation uses the correct package manager for each build.
"""

from typing import Optional


# ImageType to distro mapping (Fedora only)
IMAGE_TYPE_TO_DISTRO = {
    'fedora-bootc': 'fedora',
    'fedora-sway-atomic': 'fedora',
    'fedora-kinoite': 'fedora',
    'fedora-onyx': 'fedora',
    'fedora-budgie': 'fedora',
    'fedora-cinnamon': 'fedora',
    'fedora-cosmic': 'fedora',
    'fedora-deepin': 'fedora',
    'fedora-lxqt': 'fedora',
    'fedora-mate': 'fedora',
    'fedora-xfce': 'fedora',
}


def get_distro_for_image_type(image_type: str) -> Optional[str]:
    """
    Get the distro identifier for package validation based on image type.

    Args:
        image_type: The image type (e.g., 'fedora-bootc')

    Returns:
        Distro identifier for package transpiler (fedora only).
        Returns None if image type is unknown or unsupported.
    """
    return IMAGE_TYPE_TO_DISTRO.get(image_type.lower())


def get_package_manager_for_image_type(image_type: str) -> Optional[str]:
    """
    Get the package manager name for an image type.

    Args:
        image_type: The image type (e.g., 'fedora-bootc')

    Returns:
        Package manager name (dnf, pacman, apt, zypper, emerge, pkg)
    """
    distro = get_distro_for_image_type(image_type)

    if not distro:
        return None

    package_manager_map = {
        'fedora': 'dnf',
    }

    return package_manager_map.get(distro)


def is_supported_distro(image_type: str) -> bool:
    """
    Check if an image type has package validation support.

    Args:
        image_type: The image type to check

    Returns:
        True if the distro is supported by the package transpiler
    """
    return get_distro_for_image_type(image_type) is not None


def get_all_supported_distros() -> list[str]:
    """
    Get list of all supported distro identifiers.

    Returns:
        List of distro identifiers
    """
    return sorted(set(IMAGE_TYPE_TO_DISTRO.values()))


def main():
    """CLI for testing distro mappings."""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Map image types to distros")
    parser.add_argument("image_type", nargs="?", help="Image type to lookup")
    parser.add_argument("--list", action="store_true", help="List all supported distros")
    parser.add_argument("--all-mappings", action="store_true", help="Show all image type mappings")

    args = parser.parse_args()

    if args.list:
        print("Supported distros:")
        for distro in get_all_supported_distros():
            print(f"  - {distro}")
        return 0

    if args.all_mappings:
        print("Image Type → Distro Mappings:")
        for img_type, distro in sorted(IMAGE_TYPE_TO_DISTRO.items()):
            pkg_mgr = get_package_manager_for_image_type(img_type)
            print(f"  {img_type:25} → {distro:10} ({pkg_mgr})")
        return 0

    if not args.image_type:
        parser.error("Provide image_type or use --list/--all-mappings")

    distro = get_distro_for_image_type(args.image_type)
    if distro:
        pkg_mgr = get_package_manager_for_image_type(args.image_type)
        print(f"Image Type: {args.image_type}")
        print(f"Distro: {distro}")
        print(f"Package Manager: {pkg_mgr}")
        return 0
    else:
        print(f"Error: Unknown image type '{args.image_type}'", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit(main())
