"""
YAML Selector Service
=====================

Service for automatically selecting appropriate YAML definitions based on
OS, desktop environment, and window manager inputs.

Standalone version (no FastAPI dependencies).
"""

from pathlib import Path
from typing import Optional, Dict, Any
import yaml


# Default paths
REPO_ROOT = Path(__file__).resolve().parents[1]
YAML_DEFINITIONS_DIR = REPO_ROOT / "yaml-definitions"


class YamlSelectorService:
    """Service for selecting and loading YAML definitions."""

    DISTRO_DEFINITIONS = {
        "fedora-bootc": "sway-bootc.yml",
        "fedora-atomic": "sway-atomic.yml",
        "fedora-sway-atomic": "sway-atomic.yml",
    }

    DE_DEFINITIONS: dict[str, str] = {}

    WM_DEFINITIONS = {
        "sway": {
            "bootc": "sway-bootc.yml",
            "atomic": "sway-atomic.yml",
        },
    }

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

        raise FileNotFoundError(
            f"YAML definition not found: {definition_filename}"
        )

    def select_definition(
        self,
        os: Optional[str] = None,
        image_type: Optional[str] = None,
        desktop_environment: Optional[str] = None,
        window_manager: Optional[str] = None,
    ) -> Optional[str]:
        """Select appropriate YAML definition based on inputs."""
        if desktop_environment:
            de_def: str | None = self.DE_DEFINITIONS.get(desktop_environment.lower())
            if de_def and (self.definitions_dir / de_def).exists():
                return de_def

        if window_manager and image_type:
            wm_key = window_manager.lower()
            if wm_key in self.WM_DEFINITIONS:
                img_variant = "bootc" if "bootc" in image_type else "atomic"
                wm_def = self.WM_DEFINITIONS[wm_key].get(img_variant)
                if wm_def and (self.definitions_dir / wm_def).exists():
                    return wm_def

        if os and image_type:
            combined_key = f"{os}-{image_type}"
            if combined_key in self.DISTRO_DEFINITIONS:
                distro_def = self.DISTRO_DEFINITIONS[combined_key]
                if (self.definitions_dir / distro_def).exists():
                    return distro_def

        if image_type and image_type in self.DISTRO_DEFINITIONS:
            distro_def = self.DISTRO_DEFINITIONS[image_type]
            if (self.definitions_dir / distro_def).exists():
                return distro_def

        if os and os in self.DISTRO_DEFINITIONS:
            distro_def = self.DISTRO_DEFINITIONS[os]
            if (self.definitions_dir / distro_def).exists():
                return distro_def

        adnyeus_default = REPO_ROOT / "adnyeus.yml"
        if adnyeus_default.exists():
            return "adnyeus.yml"

        default_def = "sway-bootc.yml"
        if (self.definitions_dir / default_def).exists():
            return default_def

        return None

    def load_and_customize_yaml(
        self,
        definition_filename: str,
        desktop_environment: Optional[str] = None,
        window_manager: Optional[str] = None,
        distro_version: Optional[str] = None,
        enable_plymouth: Optional[bool] = None,
    ) -> str:
        """Load a YAML definition and customize it with provided overrides."""
        definition_path = self._resolve_definition_path(definition_filename)

        with open(definition_path, 'r') as f:
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

    def get_available_definitions(self) -> Dict[str, Any]:
        """Get list of available YAML definitions."""
        definitions: Dict[str, Any] = {}

        if not self.definitions_dir.exists():
            return definitions

        for yaml_file in self.definitions_dir.glob("*.yml"):
            try:
                with open(yaml_file, 'r') as f:
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
