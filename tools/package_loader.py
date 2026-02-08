#!/usr/bin/env python3
"""
Package Loader for Exousia
===========================

Loads and merges package definitions from YAML files for different desktop
environments and window managers.
"""

from pathlib import Path

import yaml


class PackageLoader:
    """Loads package definitions from YAML files."""

    def __init__(self, packages_dir: Path | None = None):
        """Initialize the package loader.

        Args:
            packages_dir: Root directory containing package definitions
        """
        if packages_dir is None:
            # Default to ../packages relative to this script
            script_dir = Path(__file__).parent
            packages_dir = script_dir.parent / "overlays" / "base" / "packages"

        self.packages_dir = Path(packages_dir)
        self.wm_dir = self.packages_dir / "window-managers"
        self.de_dir = self.packages_dir / "desktop-environments"
        self.common_dir = self.packages_dir / "common"

    def load_yaml(self, file_path: Path) -> dict:
        """Load a YAML file and return its contents."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data: dict = yaml.safe_load(f)
                return data
        except FileNotFoundError as err:
            raise FileNotFoundError(f"Package definition not found: {file_path}") from err
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {file_path}: {e}") from e

    def flatten_packages(self, config: dict) -> list[str]:
        """Flatten a package configuration into a list of package names.

        Recursively extracts all package names from nested dictionaries and lists,
        skipping the 'metadata' and 'groups' keys.

        Args:
            config: Package configuration dictionary

        Returns:
            List of package names
        """
        packages = []

        for key, value in config.items():
            if key in ("metadata", "groups"):
                continue

            if isinstance(value, list):
                packages.extend(value)
            elif isinstance(value, dict):
                packages.extend(self.flatten_packages(value))

        return packages

    def get_groups(self, config: dict) -> list[str]:
        """Extract package groups from configuration.

        Args:
            config: Package configuration dictionary

        Returns:
            List of package group names
        """
        groups: list[str] = config.get("groups", [])
        return groups

    def load_wm(self, wm_name: str) -> list[str]:
        """Load packages for a window manager.

        Args:
            wm_name: Name of the window manager (e.g., 'sway')

        Returns:
            List of package names
        """
        wm_file = self.wm_dir / f"{wm_name}.yml"
        config = self.load_yaml(wm_file)
        return self.flatten_packages(config)

    def load_de(self, de_name: str) -> list[str]:
        """Load packages for a desktop environment.

        Args:
            de_name: Name of the desktop environment (e.g., 'gnome', 'kde')

        Returns:
            List of package names
        """
        de_file = self.de_dir / f"{de_name}.yml"
        config = self.load_yaml(de_file)
        return self.flatten_packages(config)

    def load_common(self, common_name: str = "base") -> list[str]:
        """Load common packages.

        Args:
            common_name: Name of the common package set (default: 'base')

        Returns:
            List of package names
        """
        common_file = self.common_dir / f"{common_name}.yml"
        config = self.load_yaml(common_file)
        return self.flatten_packages(config)

    def load_remove(self) -> list[str]:
        """Load packages to remove.

        Returns:
            List of package names to remove
        """
        remove_file = self.common_dir / "remove.yml"
        config = self.load_yaml(remove_file)
        pkgs: list[str] = config.get("packages", [])
        return pkgs

    def get_package_list(
        self, wm: str | None = None, de: str | None = None, include_common: bool = True
    ) -> dict[str, list[str]]:
        """Get complete package lists for a build configuration.

        Args:
            wm: Window manager name (optional)
            de: Desktop environment name (optional)
            include_common: Whether to include common packages (default: True)

        Returns:
            Dictionary with 'install', 'remove', and 'groups' keys containing package lists
        """
        install_packages: set[str] = set()
        groups: list[str] = []

        # Load common packages
        if include_common:
            install_packages.update(self.load_common("base"))

        # Load WM or DE packages and groups
        if wm:
            wm_file = self.wm_dir / f"{wm}.yml"
            wm_config = self.load_yaml(wm_file)
            install_packages.update(self.flatten_packages(wm_config))
            groups.extend(self.get_groups(wm_config))
        elif de:
            de_file = self.de_dir / f"{de}.yml"
            de_config = self.load_yaml(de_file)
            install_packages.update(self.flatten_packages(de_config))
            groups.extend(self.get_groups(de_config))

        # Load packages to remove
        remove_packages = self.load_remove()

        # Remove any packages that are in both install and remove
        # (remove takes precedence)
        install_packages = install_packages - set(remove_packages)

        return {
            "install": sorted(install_packages),
            "remove": remove_packages,
            "groups": groups,
        }

    def list_available_wms(self) -> list[str]:
        """List all available window managers."""
        if not self.wm_dir.exists():
            return []
        return [f.stem for f in self.wm_dir.glob("*.yml")]

    def list_available_des(self) -> list[str]:
        """List all available desktop environments."""
        if not self.de_dir.exists():
            return []
        return [f.stem for f in self.de_dir.glob("*.yml")]

    def export_to_text_files(
        self, wm: str | None = None, de: str | None = None, output_dir: Path | None = None
    ) -> None:
        """Export package lists to text files (legacy format).

        **DEPRECATED**: This method exports to the legacy text-based format.
        The recommended approach is to use YAML package definitions directly
        in the build configuration with the package-loader module.

        Creates packages.add and packages.remove files in the specified directory.

        Args:
            wm: Window manager name (optional)
            de: Desktop environment name (optional)
            output_dir: Directory to write files to (default: custom-pkgs/)
        """
        import warnings

        warnings.warn(
            "export_to_text_files() is deprecated. Use YAML package definitions "
            "with package-loader module in build configurations instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if output_dir is None:
            output_dir = Path(__file__).parent.parent / "custom-pkgs"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        packages = self.get_package_list(wm=wm, de=de)

        # Write install packages
        add_file = output_dir / "packages.add"
        with open(add_file, "w", encoding="utf-8") as f:
            f.write("# Auto-generated package list (LEGACY FORMAT - DEPRECATED)\n")
            f.write(f"# Generated for: {wm or de or 'base'}\n")
            f.write("# DO NOT EDIT MANUALLY - Changes will be overwritten\n")
            f.write("# NOTE: Use packages/ YAML definitions with package-loader module instead\n\n")
            for pkg in packages["install"]:
                f.write(f"{pkg}\n")

        # Write remove packages
        remove_file = output_dir / "packages.remove"
        with open(remove_file, "w", encoding="utf-8") as f:
            f.write("# Auto-generated package removal list (LEGACY FORMAT - DEPRECATED)\n")
            f.write("# DO NOT EDIT MANUALLY - Changes will be overwritten\n")
            f.write("# NOTE: Use packages/ YAML definitions with package-loader module instead\n\n")
            for pkg in packages["remove"]:
                f.write(f"{pkg}\n")


def main():
    """CLI entry point for package loader."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Load and manage package definitions for Exousia builds"
    )
    parser.add_argument("--wm", help="Window manager to load")
    parser.add_argument("--de", help="Desktop environment to load")
    parser.add_argument("--list-wms", action="store_true", help="List available window managers")
    parser.add_argument(
        "--list-des", action="store_true", help="List available desktop environments"
    )
    parser.add_argument(
        "--export", action="store_true", help="Export to text files (legacy format)"
    )
    parser.add_argument("--output-dir", type=Path, help="Output directory for exported files")

    args = parser.parse_args()

    loader = PackageLoader()

    if args.list_wms:
        wms = loader.list_available_wms()
        print("Available window managers:")
        for wm in wms:
            print(f"  - {wm}")
        return

    if args.list_des:
        des = loader.list_available_des()
        print("Available desktop environments:")
        for de in des:
            print(f"  - {de}")
        return

    if args.export:
        loader.export_to_text_files(wm=args.wm, de=args.de, output_dir=args.output_dir)
        print(f"✓ Exported package lists to {args.output_dir or 'custom-pkgs/'}")
        return

    # Default: print package list
    packages = loader.get_package_list(wm=args.wm, de=args.de)

    print("Packages to install:")
    for pkg in packages["install"]:
        print(f"  {pkg}")

    print("\nPackages to remove:")
    for pkg in packages["remove"]:
        print(f"  {pkg}")


if __name__ == "__main__":
    main()
