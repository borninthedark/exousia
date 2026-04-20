from pathlib import Path
from typing import Any

from .constants import SUPPORTED_API_VERSIONS, SUPPORTED_KINDS
from .exceptions import PackageValidationError


def is_typed_bundle(config: dict[str, Any]) -> bool:
    """Return True if the config uses the typed bundle schema."""
    return "apiVersion" in config or "kind" in config or "spec" in config


def normalize_package_item(item: Any, file_path: Path, key_path: str) -> str:
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


def validate_config(config: dict[str, Any], file_path: Path) -> None:
    """Validate package YAML structure while remaining backward compatible."""
    if not isinstance(config, dict):
        raise PackageValidationError(f"Package definition must be a mapping: {file_path}")

    if is_typed_bundle(config):
        api_version = config.get("apiVersion")
        if api_version not in SUPPORTED_API_VERSIONS:
            raise PackageValidationError(
                f"Unsupported or missing 'apiVersion' in {file_path}: {api_version!r}"
            )

        kind = config.get("kind")
        if kind not in SUPPORTED_KINDS:
            raise PackageValidationError(f"Unsupported or missing 'kind' in {file_path}: {kind!r}")

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
                raise PackageValidationError(f"'groups' must be a list of strings in {file_path}")
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

    if is_typed_bundle(config):
        spec = config.get("spec")
        if not isinstance(spec, dict):
            raise PackageValidationError(f"'spec' must be a mapping in {file_path}")

        packages = spec.get("packages", [])
        if not isinstance(packages, list):
            raise PackageValidationError(f"'spec.packages' must be a list in {file_path}")
        for index, item in enumerate(packages):
            normalize_package_item(item, file_path, f"spec.packages[{index}]")

        groups = spec.get("groups", [])
        if groups is not None and (not isinstance(groups, (list, dict))):
            raise PackageValidationError(
                f"'spec.groups' must be a list or install/remove mapping in {file_path}"
            )
        if isinstance(groups, list) and not all(isinstance(group, str) for group in groups):
            raise PackageValidationError(f"'spec.groups' must be a list of strings in {file_path}")
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
                raise PackageValidationError(f"'spec.conflicts' must be a mapping in {file_path}")
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
            not isinstance(replaces, list) or not all(isinstance(value, str) for value in replaces)
        ):
            raise PackageValidationError(
                f"'spec.replaces' must be a list of strings in {file_path}"
            )

        requires = spec.get("requires", {})
        if requires is not None:
            if not isinstance(requires, dict):
                raise PackageValidationError(f"'spec.requires' must be a mapping in {file_path}")
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
                normalize_package_item(item, file_path, item_path)
            return

        raise PackageValidationError(
            f"Unsupported value type in {file_path}:{key_path or '<root>'}: {type(node).__name__}"
        )

    walk(config)
