"""
YAML Selector Service
=====================

Service for loading YAML build definitions.

Standalone version (no FastAPI dependencies).
"""

from pathlib import Path
from typing import Any

import yaml

# Default paths
REPO_ROOT = Path(__file__).resolve().parents[1]
YAML_DEFINITIONS_DIR = REPO_ROOT / "yaml-definitions"

DEFINITION_FILENAME = "sway.yml"


class YamlSelectorService:
    """Service for selecting and loading YAML definitions."""

    def __init__(self, definitions_dir: Path | None = None):
        provided_dir = definitions_dir.resolve() if definitions_dir else None
        self.definitions_dir = provided_dir or YAML_DEFINITIONS_DIR

    @staticmethod
    def _is_traversal(path: Path) -> bool:
        return path.is_absolute() or any(part == ".." for part in path.parts)

    def _is_allowed_path(self, path: Path) -> bool:
        allowed_bases = {
            self.definitions_dir.resolve(),
            REPO_ROOT.resolve(),
        }
        return any(path.resolve().is_relative_to(base) for base in allowed_bases)

    def _resolve_definition_path(self, definition_filename: str) -> Path:
        """Resolve a YAML definition path and ensure it stays within trusted roots."""
        filename_path = Path(definition_filename)

        if self._is_traversal(filename_path):
            raise ValueError("Path traversal detected in definition filename")

        candidate_paths = [
            (self.definitions_dir / filename_path).resolve(),
            (REPO_ROOT / filename_path).resolve(),
        ]

        allowed_candidates = [c for c in candidate_paths if self._is_allowed_path(c)]

        if not allowed_candidates:
            raise ValueError("Definition path escapes allowed directories")

        for candidate in allowed_candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(f"YAML definition not found: {definition_filename}")

    def select_definition(
        self,
        os: str | None = None,
        image_type: str | None = None,
        desktop_environment: str | None = None,
        window_manager: str | None = None,
    ) -> str | None:
        """Select appropriate YAML definition."""
        # Single consolidated definition
        if (self.definitions_dir / DEFINITION_FILENAME).exists():
            return DEFINITION_FILENAME

        # Fallback to adnyeus.yml in repo root
        adnyeus_default = REPO_ROOT / "adnyeus.yml"
        if adnyeus_default.exists():
            return "adnyeus.yml"

        return None

    def load_and_customize_yaml(
        self,
        definition_filename: str,
        desktop_environment: str | None = None,
        window_manager: str | None = None,
        distro_version: str | None = None,
        enable_plymouth: bool | None = None,
    ) -> str:
        """Load a YAML definition and customize it with provided overrides."""
        definition_path = self._resolve_definition_path(definition_filename)

        with open(definition_path) as f:
            config = yaml.safe_load(f)

        if distro_version:
            config["image-version"] = distro_version

        if enable_plymouth is not None:
            if "build" not in config:
                config["build"] = {}
            config["build"]["enable_plymouth"] = enable_plymouth

        if desktop_environment or window_manager:
            if "desktop" not in config:
                config["desktop"] = {}
            if window_manager:
                config["desktop"]["window_manager"] = window_manager
            if desktop_environment:
                config["desktop"]["desktop_environment"] = desktop_environment

        dumped: str = yaml.safe_dump(config)
        return dumped

    def get_available_definitions(self) -> dict[str, Any]:
        """Get list of available YAML definitions."""
        definitions: dict[str, Any] = {}

        if not self.definitions_dir.exists():
            return definitions

        for yaml_file in self.definitions_dir.glob("*.yml"):
            try:
                with open(yaml_file) as f:
                    config = yaml.safe_load(f)

                definitions[yaml_file.name] = {
                    "name": config.get("name", yaml_file.stem),
                    "description": config.get("description", ""),
                    "image_type": config.get("image-type", ""),
                    "desktop": config.get("desktop", {}),
                }
            except Exception:
                continue

        return definitions
