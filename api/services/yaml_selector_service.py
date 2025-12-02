"""
YAML Selector Service
=====================

Service for automatically selecting appropriate YAML definitions based on
OS, desktop environment, and window manager inputs.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import yaml

from ..config import settings


class YamlSelectorService:
    """Service for selecting and loading YAML definitions."""

    # Mapping of OS/distro to available YAML definitions
    DISTRO_DEFINITIONS = {
        "fedora-bootc": "sway-bootc.yml",
        "fedora-atomic": "sway-atomic.yml",
        "fedora-kinoite": "fedora-kinoite.yml",
        "arch": "arch-bootc.yml",
        "debian": "debian-bootc.yml",
        "ubuntu": "ubuntu-bootc.yml",
        "opensuse": "opensuse-bootc.yml",
    }

    # Mapping of desktop environments to their preferred definitions
    DE_DEFINITIONS = {
        "kde": "fedora-kinoite.yml",
        "mate": "fedora-mate.yml",  # TODO: Create fedora-mate.yml if needed
    }

    # Mapping of window managers to their preferred definitions
    WM_DEFINITIONS = {
        "sway": {
            "bootc": "sway-bootc.yml",
            "atomic": "sway-atomic.yml",
        },
        "hyprland": {
            "bootc": "sway-bootc.yml",  # Can be customized for hyprland
            "atomic": "sway-atomic.yml",
        },
    }

    def __init__(self):
        self.definitions_dir = settings.YAML_DEFINITIONS_DIR

    def select_definition(
        self,
        os: Optional[str] = None,
        image_type: Optional[str] = None,
        desktop_environment: Optional[str] = None,
        window_manager: Optional[str] = None,
    ) -> Optional[str]:
        """
        Select appropriate YAML definition based on inputs.

        Priority order:
        1. Desktop environment (if specified)
        2. Window manager + image type (if specified)
        3. OS/distro + image type
        4. Image type alone
        5. Default (sway-bootc.yml)

        Args:
            os: Operating system/distro (e.g., "fedora", "arch", "debian")
            image_type: Image type (e.g., "fedora-bootc", "fedora-atomic")
            desktop_environment: Desktop environment (e.g., "kde", "mate")
            window_manager: Window manager (e.g., "sway", "hyprland")

        Returns:
            Filename of the selected YAML definition
        """
        # Priority 1: Desktop environment
        if desktop_environment:
            de_def = self.DE_DEFINITIONS.get(desktop_environment.lower())
            if de_def and (self.definitions_dir / de_def).exists():
                return de_def

        # Priority 2: Window manager + image type
        if window_manager and image_type:
            wm_key = window_manager.lower()
            if wm_key in self.WM_DEFINITIONS:
                # Determine if bootc or atomic
                img_variant = "bootc" if "bootc" in image_type else "atomic"
                wm_def = self.WM_DEFINITIONS[wm_key].get(img_variant)
                if wm_def and (self.definitions_dir / wm_def).exists():
                    return wm_def

        # Priority 3: OS/distro + image type combination
        if os and image_type:
            # Try combining os and image_type
            combined_key = f"{os}-{image_type}"
            if combined_key in self.DISTRO_DEFINITIONS:
                distro_def = self.DISTRO_DEFINITIONS[combined_key]
                if (self.definitions_dir / distro_def).exists():
                    return distro_def

        # Priority 4: Image type alone
        if image_type and image_type in self.DISTRO_DEFINITIONS:
            distro_def = self.DISTRO_DEFINITIONS[image_type]
            if (self.definitions_dir / distro_def).exists():
                return distro_def

        # Priority 5: OS alone
        if os and os in self.DISTRO_DEFINITIONS:
            distro_def = self.DISTRO_DEFINITIONS[os]
            if (self.definitions_dir / distro_def).exists():
                return distro_def

        # Default fallback to adnyeus.yml at project root
        # First check for adnyeus.yml in parent directory (project root)
        project_root = self.definitions_dir.parent
        adnyeus_default = project_root / "adnyeus.yml"
        if adnyeus_default.exists():
            return "../adnyeus.yml"

        # Fallback to sway-bootc.yml in definitions dir
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
        """
        Load a YAML definition and customize it with provided overrides.

        Args:
            definition_filename: Name of the YAML definition file
            desktop_environment: Desktop environment to set
            window_manager: Window manager to set
            distro_version: Version to set in the YAML
            enable_plymouth: Whether to enable plymouth

        Returns:
            Customized YAML content as string
        """
        definition_path = self.definitions_dir / definition_filename

        if not definition_path.exists():
            raise FileNotFoundError(f"YAML definition not found: {definition_filename}")

        # Load YAML
        with open(definition_path, 'r') as f:
            config = yaml.safe_load(f)

        # Apply customizations
        if distro_version:
            config["image-version"] = distro_version

        if enable_plymouth is not None:
            if "build" not in config:
                config["build"] = {}
            config["build"]["enable_plymouth"] = enable_plymouth

        # Desktop customization
        if desktop_environment or window_manager:
            if "desktop" not in config:
                config["desktop"] = {}

            if window_manager:
                config["desktop"]["window_manager"] = window_manager
                # Remove desktop_environment if setting window_manager
                config["desktop"].pop("desktop_environment", None)
            elif desktop_environment:
                config["desktop"]["desktop_environment"] = desktop_environment
                # Remove window_manager if setting desktop_environment
                config["desktop"].pop("window_manager", None)

        return yaml.safe_dump(config)

    def get_available_definitions(self) -> Dict[str, Any]:
        """
        Get list of available YAML definitions.

        Returns:
            Dictionary mapping filenames to metadata
        """
        definitions = {}

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
                # Skip files that can't be parsed
                continue

        return definitions
