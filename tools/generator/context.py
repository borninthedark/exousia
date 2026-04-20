from dataclasses import dataclass


@dataclass
class DistroConfig:
    """Configuration for a specific distro."""

    name: str
    base_image_template: str
    package_manager: str
    update_command: str
    install_command: str
    clean_command: str
    build_deps_install: str
    build_deps_remove: str
    bootc_build_deps: list[str]


@dataclass
class BuildContext:
    """Build context for evaluating conditions and generating Containerfile."""

    image_type: str
    fedora_version: str  # For Fedora-based images; can be empty for Linux bootc
    enable_plymouth: bool
    use_upstream_sway_config: bool
    base_image: str
    enable_zfs: bool = False
    distro: str = "fedora"  # fedora-only
    desktop_environment: str = ""  # kde, gnome, mate, etc.
    window_manager: str = ""  # sway, kwin, etc.
