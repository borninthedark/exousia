#!/usr/bin/env python3
"""
Package Loader for Exousia
===========================

Loads and merges package definitions from YAML files for different desktop
environments and window managers.
"""

import json
from pathlib import Path
from typing import Any

import yaml


class PackageValidationError(ValueError):
    """Raised when a package definition is structurally invalid."""


SUPPORTED_API_VERSIONS = {"exousia.packages/v1alpha1"}
SUPPORTED_KINDS = {
    "PackageBundle",
    "FeatureBundle",
    "PackageRemovalBundle",
    "PackageOverrideBundle",
    "KernelConfig",
    "KernelProfile",
}
DEFAULT_COMMON_BUNDLES = [
    "base-core",
    "base-media",
    "base-devtools",
    "base-rpm-packaging",
    "base-virtualization",
    "base-security",
    "base-network",
    "base-shell",
]


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
        self.kernels_dir = self.packages_dir / "kernels"

    def _infer_bundle_type(self, file_path: Path) -> str:
        """Infer bundle type from the file location."""
        if file_path.parent == self.wm_dir:
            return "window-manager"
        if file_path.parent == self.de_dir:
            return "desktop-environment"
        if file_path.parent == self.common_dir:
            return "common"
        if file_path.parent == self.kernels_dir:
            return "kernel-profile"
        return "unknown"

    def _default_common_bundle_paths(self) -> list[Path]:
        """Return the explicit default common bundle paths."""
        return [self.common_dir / f"{bundle}.yml" for bundle in DEFAULT_COMMON_BUNDLES]

    def _is_typed_bundle(self, config: dict[str, Any]) -> bool:
        """Return True if the config uses the typed bundle schema."""
        return "apiVersion" in config or "kind" in config or "spec" in config

    def _normalize_package_item(self, item: Any, file_path: Path, key_path: str) -> str:
        """Normalize a package item to a package name string."""
        if isinstance(item, str):
            normalized = item.strip()
            if normalized:
                return normalized
            raise PackageValidationError(
                f"Invalid empty package entry at {file_path}:{key_path or '<root>'}"
            )

        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
            raise PackageValidationError(
                f"Package object must contain non-empty 'name' at {file_path}:{key_path or '<root>'}"
            )

        raise PackageValidationError(
            f"Unsupported package entry type at {file_path}:{key_path or '<root>'}: {type(item).__name__}"
        )

    def _validate_config(self, config: dict[str, Any], file_path: Path) -> None:
        """Validate package YAML structure while remaining backward compatible."""
        if not isinstance(config, dict):
            raise PackageValidationError(f"Package definition must be a mapping: {file_path}")

        if self._is_typed_bundle(config):
            api_version = config.get("apiVersion")
            if api_version not in SUPPORTED_API_VERSIONS:
                raise PackageValidationError(
                    f"Unsupported or missing 'apiVersion' in {file_path}: {api_version!r}"
                )

            kind = config.get("kind")
            if kind not in SUPPORTED_KINDS:
                raise PackageValidationError(
                    f"Unsupported or missing 'kind' in {file_path}: {kind!r}"
                )

        metadata = config.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise PackageValidationError(f"'metadata' must be a mapping in {file_path}")

        if isinstance(metadata, dict):
            name = metadata.get("name")
            if name is not None and (not isinstance(name, str) or not name.strip()):
                raise PackageValidationError(
                    f"'metadata.name' must be a non-empty string in {file_path}"
                )

            metadata_type = metadata.get("type")
            if metadata_type is not None and (
                not isinstance(metadata_type, str) or not metadata_type.strip()
            ):
                raise PackageValidationError(
                    f"'metadata.type' must be a non-empty string in {file_path}"
                )

        groups = config.get("groups")
        if groups is not None:
            if isinstance(groups, list):
                if not all(isinstance(group, str) for group in groups):
                    raise PackageValidationError(
                        f"'groups' must be a list of strings in {file_path}"
                    )
            elif isinstance(groups, dict):
                for group_key in ("install", "remove"):
                    values = groups.get(group_key, [])
                    if values is not None and (
                        not isinstance(values, list)
                        or not all(isinstance(group, str) for group in values)
                    ):
                        raise PackageValidationError(
                            f"'groups.{group_key}' must be a list of strings in {file_path}"
                        )
            else:
                raise PackageValidationError(
                    f"'groups' must be a list or install/remove mapping in {file_path}"
                )

        if self._is_typed_bundle(config):
            spec = config.get("spec")
            if not isinstance(spec, dict):
                raise PackageValidationError(f"'spec' must be a mapping in {file_path}")

            packages = spec.get("packages", [])
            if not isinstance(packages, list):
                raise PackageValidationError(f"'spec.packages' must be a list in {file_path}")
            for index, item in enumerate(packages):
                self._normalize_package_item(item, file_path, f"spec.packages[{index}]")

            groups = spec.get("groups", [])
            if groups is not None and (not isinstance(groups, (list, dict))):
                raise PackageValidationError(
                    f"'spec.groups' must be a list or install/remove mapping in {file_path}"
                )
            if isinstance(groups, list) and not all(isinstance(group, str) for group in groups):
                raise PackageValidationError(
                    f"'spec.groups' must be a list of strings in {file_path}"
                )
            if isinstance(groups, dict):
                for group_key in ("install", "remove"):
                    values = groups.get(group_key, [])
                    if values is not None and (
                        not isinstance(values, list)
                        or not all(isinstance(group, str) for group in values)
                    ):
                        raise PackageValidationError(
                            f"'spec.groups.{group_key}' must be a list of strings in {file_path}"
                        )

            conflicts = spec.get("conflicts", {})
            if conflicts is not None:
                if not isinstance(conflicts, dict):
                    raise PackageValidationError(
                        f"'spec.conflicts' must be a mapping in {file_path}"
                    )
                for conflict_key in ("packages", "features"):
                    values = conflicts.get(conflict_key, [])
                    if values is not None and (
                        not isinstance(values, list)
                        or not all(isinstance(value, str) for value in values)
                    ):
                        raise PackageValidationError(
                            f"'spec.conflicts.{conflict_key}' must be a list of strings in {file_path}"
                        )

            replaces = spec.get("replaces", [])
            if replaces is not None and (
                not isinstance(replaces, list)
                or not all(isinstance(value, str) for value in replaces)
            ):
                raise PackageValidationError(
                    f"'spec.replaces' must be a list of strings in {file_path}"
                )

            requires = spec.get("requires", {})
            if requires is not None:
                if not isinstance(requires, dict):
                    raise PackageValidationError(
                        f"'spec.requires' must be a mapping in {file_path}"
                    )
                for requires_key in ("features",):
                    values = requires.get(requires_key, [])
                    if values is not None and (
                        not isinstance(values, list)
                        or not all(isinstance(value, str) for value in values)
                    ):
                        raise PackageValidationError(
                            f"'spec.requires.{requires_key}' must be a list of strings in {file_path}"
                        )
            return

        def walk(node: Any, key_path: str = "") -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in ("metadata", "groups"):
                        continue
                    child_path = f"{key_path}.{key}" if key_path else str(key)
                    walk(value, child_path)
                return

            if isinstance(node, list):
                for index, item in enumerate(node):
                    item_path = f"{key_path}[{index}]"
                    self._normalize_package_item(item, file_path, item_path)
                return

            raise PackageValidationError(
                f"Unsupported value type in {file_path}:{key_path or '<root>'}: {type(node).__name__}"
            )

        walk(config)

    def load_yaml(self, file_path: Path) -> dict[str, Any]:
        """Load a YAML file and return its contents."""
        try:
            with open(file_path, encoding="utf-8") as f:
                data: dict[str, Any] = yaml.safe_load(f)
                self._validate_config(data, file_path)
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
        if self._is_typed_bundle(config):
            spec = config.get("spec", {})
            return [
                self._normalize_package_item(item, Path("<memory>"), "spec.packages")
                for item in spec.get("packages", [])
            ]

        packages: list[str] = []

        for key, value in config.items():
            if key in ("metadata", "groups"):
                continue

            if isinstance(value, list):
                packages.extend(
                    self._normalize_package_item(value_item, Path("<memory>"), key)
                    for value_item in value
                )
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
        if self._is_typed_bundle(config):
            groups = config.get("spec", {}).get("groups", [])
            if isinstance(groups, dict):
                return list(groups.get("install", []))
            if isinstance(groups, list):
                return list(groups)
            return []

        groups = config.get("groups", [])
        if isinstance(groups, dict):
            return list(groups.get("install", []))
        return list(groups)

    def get_group_actions(self, config: dict) -> dict[str, list[str]]:
        """Extract package-group install/remove actions from configuration."""
        if self._is_typed_bundle(config):
            groups = config.get("spec", {}).get("groups", [])
        else:
            groups = config.get("groups", [])

        if isinstance(groups, list):
            return {"install": list(groups), "remove": []}

        if isinstance(groups, dict):
            return {
                "install": list(groups.get("install", []) or []),
                "remove": list(groups.get("remove", []) or []),
            }

        return {"install": [], "remove": []}

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
        if common_name == "base":
            packages: set[str] = set()
            for common_file in self._default_common_bundle_paths():
                config = self.load_yaml(common_file)
                packages.update(self.flatten_packages(config))
            return sorted(packages)

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
        if self._is_typed_bundle(config):
            return [
                self._normalize_package_item(pkg, remove_file, "spec.packages")
                for pkg in config.get("spec", {}).get("packages", [])
            ]
        pkgs = config.get("packages", [])
        return [self._normalize_package_item(pkg, remove_file, "packages") for pkg in pkgs]

    def load_rpm_overrides(self) -> list[dict[str, Any]]:
        """Load RPM override definitions from rpm-overrides.yml.

        Returns:
            List of override dicts with image, reason, and replaces keys.
            Empty list if the file does not exist.
        """
        override_file = self.common_dir / "rpm-overrides.yml"
        if not override_file.exists():
            return []
        config = self.load_yaml(override_file)
        spec = config.get("spec", {}) if self._is_typed_bundle(config) else config
        return list(spec.get("overrides", []))

    def load_kernel_config(self) -> dict[str, Any]:
        """Load kernel configuration from kernel-config.yml.

        Returns:
            Kernel config dict with source, copr/oci settings, and modules.
            Empty dict with source='default' if the file does not exist.
        """
        config_file = self.common_dir / "kernel-config.yml"
        if not config_file.exists():
            return {"source": "default", "modules": []}
        config = self.load_yaml(config_file)
        spec = config.get("spec", {}) if self._is_typed_bundle(config) else config
        return {
            "source": spec.get("source", "default"),
            "copr": spec.get("copr", {}),
            "oci": spec.get("oci", {}),
            "kernel_packages": spec.get("kernel_packages", []),
            "kernel_devel_packages": spec.get("kernel_devel_packages", []),
            "modules": spec.get("modules", []),
        }

    def load_kernel_profile(self, name: str) -> dict[str, Any]:
        """Load a kernel profile by name.

        Args:
            name: Name of the kernel profile (e.g., 'fedora-default', 'cachyos')

        Returns:
            Kernel profile dict with source, packages, devel_packages, replaces,
            and optional copr, image, version_pin fields.
        """
        profile_file = self.kernels_dir / f"{name}.yml"
        config = self.load_yaml(profile_file)
        spec = config.get("spec", {}) if self._is_typed_bundle(config) else config

        return {
            "source": spec.get("source", "repo"),
            "packages": list(spec.get("packages", [])),
            "devel_packages": list(spec.get("devel_packages", [])),
            "replaces": list(spec.get("replaces", [])),
            "copr": spec.get("copr"),
            "image": spec.get("image"),
            "version_pin": spec.get("version_pin"),
        }

    def _bundle_record(
        self, file_path: Path, config: dict[str, Any], selected_as: str
    ) -> dict[str, Any]:
        """Build a normalized bundle record."""
        metadata = config.get("metadata", {})
        bundle_name = metadata.get("name") or file_path.stem
        bundle_type = metadata.get("type") or self._infer_bundle_type(file_path)
        if self._is_typed_bundle(config):
            bundle_type = config.get("kind", bundle_type)

        spec = config.get("spec", {}) if self._is_typed_bundle(config) else {}
        conflicts = spec.get("conflicts", {}) if isinstance(spec, dict) else {}
        requires = spec.get("requires", {}) if isinstance(spec, dict) else {}
        replaces = spec.get("replaces", []) if isinstance(spec, dict) else []

        return {
            "name": bundle_name,
            "kind": bundle_type,
            "selected_as": selected_as,
            "source_file": str(file_path),
            "groups": self.get_group_actions(config),
            "packages": sorted(set(self.flatten_packages(config))),
            "conflicts": {
                "packages": sorted(set(conflicts.get("packages", []) or [])),
                "features": sorted(set(conflicts.get("features", []) or [])),
            },
            "replaces": sorted(set(replaces or [])),
            "requires": {
                "features": sorted(set(requires.get("features", []) or [])),
            },
        }

    def _validate_selected_bundles(self, bundles: list[dict[str, Any]]) -> None:
        """Validate selected bundles for feature and package conflicts."""
        bundle_names = {bundle["name"] for bundle in bundles}
        install_packages: dict[str, set[str]] = {}

        for bundle in bundles:
            for pkg in bundle["packages"]:
                install_packages.setdefault(pkg, set()).add(bundle["name"])

        for bundle in bundles:
            for required_feature in bundle.get("requires", {}).get("features", []):
                if required_feature not in bundle_names:
                    raise PackageValidationError(
                        f"Bundle '{bundle['name']}' requires missing feature '{required_feature}'"
                    )

            for conflict_feature in bundle.get("conflicts", {}).get("features", []):
                if conflict_feature in bundle_names:
                    raise PackageValidationError(
                        f"Bundle '{bundle['name']}' conflicts with selected feature '{conflict_feature}'"
                    )

            for conflict_package in bundle.get("conflicts", {}).get("packages", []):
                owners = install_packages.get(conflict_package, set()) - {bundle["name"]}
                if owners:
                    raise PackageValidationError(
                        f"Bundle '{bundle['name']}' conflicts with package '{conflict_package}' "
                        f"provided by {sorted(owners)}"
                    )

    def get_package_plan(
        self,
        wm: str | None = None,
        de: str | None = None,
        include_common: bool = True,
        extras: list[str] | None = None,
        common_bundles: list[str] | None = None,
        feature_bundles: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return a normalized package plan with provenance for the selection."""
        install_sources: dict[str, set[str]] = {}
        group_install_sources: dict[str, set[str]] = {}
        group_remove_sources: dict[str, set[str]] = {}
        bundles: list[dict[str, Any]] = []

        def add_bundle(file_path: Path, selected_as: str) -> None:
            config = self.load_yaml(file_path)
            bundle = self._bundle_record(file_path, config, selected_as)
            bundles.append(bundle)
            for group in bundle["groups"]["install"]:
                group_install_sources.setdefault(group, set()).add(bundle["name"])
            for group in bundle["groups"]["remove"]:
                group_remove_sources.setdefault(group, set()).add(bundle["name"])
            for pkg in bundle["packages"]:
                install_sources.setdefault(pkg, set()).add(bundle["name"])

        if extras and feature_bundles is not None:
            raise PackageValidationError(
                "Use either 'extras' or 'feature_bundles', not both, when resolving package plans"
            )

        if common_bundles is not None and include_common:
            raise PackageValidationError(
                "Use either explicit 'common_bundles' or 'include_common', not both"
            )

        if common_bundles is not None and "base" in common_bundles:
            raise PackageValidationError(
                "'base' is no longer a real package bundle; use explicit common bundles instead"
            )

        if feature_bundles is not None and any(bundle == "base" for bundle in feature_bundles):
            raise PackageValidationError("'base' is not a valid feature bundle")

        selected_common_bundles = (
            list(common_bundles)
            if common_bundles is not None
            else (DEFAULT_COMMON_BUNDLES if include_common else [])
        )
        selected_feature_bundles = (
            list(feature_bundles) if feature_bundles is not None else list(extras or [])
        )

        for common_bundle in selected_common_bundles:
            add_bundle(self.common_dir / f"{common_bundle}.yml", f"common:{common_bundle}")

        if selected_feature_bundles:
            for extra in selected_feature_bundles:
                add_bundle(self.common_dir / f"{extra}.yml", f"feature:{extra}")

        if wm:
            add_bundle(self.wm_dir / f"{wm}.yml", f"window-manager:{wm}")
        elif de:
            add_bundle(self.de_dir / f"{de}.yml", f"desktop-environment:{de}")

        remove_bundle_path = self.common_dir / "remove.yml"
        remove_bundle = self.load_yaml(remove_bundle_path)
        remove_packages = set(self.load_remove())
        remove_sources: dict[str, set[str]] = {}

        for pkg in remove_packages:
            remove_sources.setdefault(pkg, set()).add(
                (remove_bundle.get("metadata") or {}).get("name") or "remove"
            )

        for bundle in bundles:
            for pkg in bundle.get("conflicts", {}).get("packages", []):
                remove_packages.add(pkg)
                remove_sources.setdefault(pkg, set()).add(bundle["name"])
            for pkg in bundle.get("replaces", []):
                remove_packages.add(pkg)
                remove_sources.setdefault(pkg, set()).add(bundle["name"])

        remove_record = {
            "name": (remove_bundle.get("metadata") or {}).get("name") or "remove",
            "kind": remove_bundle.get("kind")
            or (remove_bundle.get("metadata") or {}).get("type")
            or "common",
            "selected_as": "common:remove",
            "source_file": str(remove_bundle_path),
            "packages": sorted(remove_packages),
        }

        self._validate_selected_bundles(bundles)

        install_details = [
            {"name": pkg, "from": sorted(install_sources[pkg])}
            for pkg in sorted(set(install_sources) - remove_packages)
        ]
        remove_details = [
            {"name": pkg, "from": sorted(remove_sources.get(pkg, {remove_record["name"]}))}
            for pkg in sorted(remove_packages)
        ]

        return {
            "selection": {
                "window_manager": wm,
                "desktop_environment": de,
                "include_common": include_common,
                "common_bundles": selected_common_bundles,
                "feature_bundles": selected_feature_bundles,
            },
            "bundles": bundles,
            "rpm": {
                "install": install_details,
                "remove": remove_details,
                "groups": {
                    "install": [
                        {"name": group, "from": sorted(sources)}
                        for group, sources in sorted(group_install_sources.items())
                    ],
                    "remove": [
                        {"name": group, "from": sorted(sources)}
                        for group, sources in sorted(group_remove_sources.items())
                    ],
                },
            },
        }

    def get_package_list(
        self,
        wm: str | None = None,
        de: str | None = None,
        include_common: bool = True,
        extras: list[str] | None = None,
    ) -> dict[str, list[str]]:
        """Get complete package lists for a build configuration.

        Args:
            wm: Window manager name (optional)
            de: Desktop environment name (optional)
            include_common: Whether to include common packages (default: True)
            extras: Additional common package sets to load (e.g., ['audio-production'])

        Returns:
            Dictionary with 'install', 'remove', and 'groups' keys containing package lists
        """
        plan = self.get_package_plan(wm=wm, de=de, include_common=include_common, extras=extras)
        install_packages = [item["name"] for item in plan["rpm"]["install"]]
        remove_packages = [item["name"] for item in plan["rpm"]["remove"]]

        return {
            "install": install_packages,
            "remove": remove_packages,
            "groups": [item["name"] for item in plan["rpm"]["groups"]["install"]],
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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print normalized resolved package plan as JSON",
    )
    parser.add_argument(
        "--common",
        action="append",
        dest="common_bundles",
        help="Explicit common package set to include (repeatable)",
    )
    parser.add_argument(
        "--feature",
        action="append",
        dest="feature_bundles",
        help="Explicit feature package set to include (repeatable)",
    )
    parser.add_argument(
        "--common-bundle", action="append", dest="common_bundles", help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--feature-bundle", action="append", dest="feature_bundles", help=argparse.SUPPRESS
    )

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
    if args.json:
        print(
            json.dumps(
                loader.get_package_plan(
                    wm=args.wm,
                    de=args.de,
                    include_common=args.common_bundles is None,
                    common_bundles=args.common_bundles,
                    feature_bundles=args.feature_bundles,
                ),
                indent=2,
            )
        )
        return

    packages = loader.get_package_list(
        wm=args.wm,
        de=args.de,
        include_common=args.common_bundles is None,
        extras=args.feature_bundles,
    )

    print("Packages to install:")
    for pkg in packages["install"]:
        print(f"  {pkg}")

    print("\nPackages to remove:")
    for pkg in packages["remove"]:
        print(f"  {pkg}")


if __name__ == "__main__":
    main()
