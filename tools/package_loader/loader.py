from pathlib import Path
from typing import Any

import yaml

from .constants import DEFAULT_COMMON_BUNDLES
from .exceptions import PackageValidationError
from .validator import is_typed_bundle, normalize_package_item, validate_config


class PackageLoader:
    """Loads package definitions from YAML files."""

    def __init__(
        self,
        packages_dir: Path | None = None,
        wm_dir: Path | None = None,
        de_dir: Path | None = None,
        common_dir: Path | None = None,
        kernels_dir: Path | None = None,
    ):
        """Initialize the package loader.

        Args:
            packages_dir: Root directory containing package definitions
            wm_dir: Directory containing window manager definitions
            de_dir: Directory containing desktop environment definitions
            common_dir: Directory containing common package definitions
            kernels_dir: Directory containing kernel profile definitions
        """
        if packages_dir is None:
            # Default to ../packages relative to this script
            script_dir = Path(__file__).parent.parent
            packages_dir = script_dir.parent / "overlays" / "base" / "packages"

        self.packages_dir = Path(packages_dir)
        self.wm_dir = Path(wm_dir) if wm_dir else self.packages_dir / "window-managers"
        self.de_dir = Path(de_dir) if de_dir else self.packages_dir / "desktop-environments"
        self.common_dir = Path(common_dir) if common_dir else self.packages_dir / "common"
        self.kernels_dir = Path(kernels_dir) if kernels_dir else self.packages_dir / "kernels"

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
        return is_typed_bundle(config)

    def _normalize_package_item(self, item: Any, file_path: Path, key_path: str) -> str:
        """Normalize a package item to a package name string."""
        return normalize_package_item(item, file_path, key_path)

    def _validate_config(self, config: dict[str, Any], file_path: Path) -> None:
        """Validate package YAML structure while remaining backward compatible."""
        validate_config(config, file_path)

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
        packages: list[str] = []

        if self._is_typed_bundle(config):
            spec = config.get("spec", {})
            pkgs = spec.get("packages", [])
            return [
                self._normalize_package_item(pkg, Path("unknown"), "spec.packages") for pkg in pkgs
            ]

        for key, value in config.items():
            if key in ("metadata", "groups"):
                continue

            if isinstance(value, list):
                for index, item in enumerate(value):
                    packages.append(
                        self._normalize_package_item(item, Path("unknown"), f"{key}[{index}]")
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
            output_dir = self.packages_dir.parent / "custom-pkgs"

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
