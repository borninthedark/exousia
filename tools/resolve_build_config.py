#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

import yaml

# Add tools directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent))

YAML_SELECTOR_AVAILABLE = True
YAML_SELECTOR_IMPORT_ERROR: Exception | None = None

try:
    from yaml_selector_service import YamlSelectorService
except Exception as exc:
    YAML_SELECTOR_AVAILABLE = False
    YAML_SELECTOR_IMPORT_ERROR = exc


DEFAULT_VERSION = "43"
DEFAULT_IMAGE_TYPE = "fedora-sway-atomic"


def resolve_yaml_config(
    input_yaml_config: str,
    target_image_type: str,
    os_name: str = "",
    window_manager: str = "",
    desktop_environment: str = "",
) -> Path:
    """
    Resolve YAML configuration path using YamlSelectorService.

    Args:
        input_yaml_config: Explicit path or "auto" for auto-selection
        target_image_type: Image type (e.g., "fedora-bootc", "fedora-sway-atomic")
        os_name: OS name for selection (Fedora only)
        window_manager: Window manager for selection (e.g., "sway")
        desktop_environment: Desktop environment for selection (e.g., "lxqt")

    Returns:
        Resolved Path to YAML config file
    """
    if target_image_type == "linux-bootc":
        print("::error::linux-bootc builds are no longer supported; use Fedora image types instead")
        sys.exit(1)

    if input_yaml_config != "auto":
        # Try to resolve the YAML config path with automatic search
        config_path = Path(input_yaml_config)

        # Check for path traversal attacks
        if config_path.is_absolute() or any(part == ".." for part in config_path.parts):
            print(
                f"::error::Invalid YAML config path (path traversal detected): {input_yaml_config}"
            )
            sys.exit(1)

        # Try multiple locations in order:
        # 1. Exact path as specified
        # 2. yaml-definitions/ + filename
        # 3. Search entire repo for the file
        candidate_paths = [
            config_path,  # Try exact path first
            Path("yaml-definitions") / config_path,  # Try yaml-definitions/ directory
        ]

        # Find first existing path
        for candidate in candidate_paths:
            if candidate.exists():
                resolved = candidate.resolve()
                print(f"Resolved YAML config: {resolved}")
                return resolved

        # If not found in standard locations, search the repo
        print(
            f"::warning::YAML config not found in standard locations, searching repo for: {config_path.name}"
        )
        import subprocess

        try:
            result = subprocess.run(
                ["find", ".", "-name", config_path.name, "-type", "f"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            matches = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            if matches:
                # Prefer yaml-definitions matches first, then others
                yaml_def_matches = [m for m in matches if "yaml-definitions" in m]
                selected_match = yaml_def_matches[0] if yaml_def_matches else matches[0]
                resolved = Path(selected_match).resolve()
                print(f"Found YAML config via repo search: {resolved}")
                return resolved
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            print(f"::warning::Repo search failed: {e}")

        print(f"::error::YAML config file not found: {input_yaml_config}")
        print(f"::error::Searched locations: {[str(p) for p in candidate_paths]}")
        sys.exit(1)

    # Auto-selection mode
    if not YAML_SELECTOR_AVAILABLE:
        if YAML_SELECTOR_IMPORT_ERROR is not None:
            print(f"::error::Failed to import YamlSelectorService: {YAML_SELECTOR_IMPORT_ERROR}")
            sys.exit(1)
    else:
        try:
            local_definitions = Path("yaml-definitions")
            selector = YamlSelectorService(
                definitions_dir=local_definitions if local_definitions.exists() else None
            )

            # Use YamlSelectorService to intelligently select definition
            selected_filename = selector.select_definition(
                os=os_name,
                image_type=target_image_type,
                desktop_environment=desktop_environment,
                window_manager=window_manager,
            )

            if selected_filename:
                # Resolve the path (could be in yaml-definitions/ or repo root)
                selected_path: Path = selector._resolve_definition_path(selected_filename)
                print(f"Auto-selected config: {selected_path} (from {selected_filename})")
                return selected_path

            print("::warning::YamlSelectorService could not select a definition")
        except Exception as e:
            print(f"::warning::YamlSelectorService failed: {e}")

    # Fallback logic if YamlSelectorService unavailable or failed
    candidate = Path(f"yaml-definitions/{target_image_type}.yml")
    if candidate.exists():
        print(f"Fallback: using {candidate}")
        return candidate.resolve()

    # Check for common definitions based on image type
    fallback_map = {
        "fedora-bootc": "sway-bootc.yml",
        "fedora-sway-atomic": "sway-atomic.yml",
        "fedora-atomic": "sway-atomic.yml",
    }

    if target_image_type in fallback_map:
        fallback_name = fallback_map[target_image_type]
        fallback_path = Path("yaml-definitions") / fallback_name
        if fallback_path.exists():
            print(f"Fallback: using {fallback_path}")
            return fallback_path.resolve()

    # Last resort: adnyeus.yml
    default_config = Path("adnyeus.yml")
    if default_config.exists():
        print(f"::warning::Using default config: {default_config}")
        return default_config.resolve()

    print(f"::error::No config file found for {target_image_type}")
    sys.exit(1)


def apply_fedora_overrides(
    yaml_config: Path,
    target_image_type: str,
    target_version: str,
    window_manager: str,
    desktop_environment: str,
) -> Path:
    config = yaml.safe_load(yaml_config.read_text()) or {}

    config["image-version"] = target_version

    base_image = config.get("base-image")
    if isinstance(base_image, str) and base_image.startswith(
        ("quay.io/fedora/fedora-bootc", "quay.io/fedora/fedora-sway-atomic")
    ):
        prefix = base_image.split(":", 1)[0]
        config["base-image"] = f"{prefix}:{target_version}"
    elif base_image is None:
        config["base-image"] = f"quay.io/fedora/fedora-bootc:{target_version}"

    # Desktop customization - supports combined DE+WM
    if window_manager or desktop_environment:
        desktop = config.get("desktop") or {}

        if window_manager:
            desktop["window_manager"] = window_manager
        if desktop_environment:
            desktop["desktop_environment"] = desktop_environment

        config["desktop"] = desktop

    resolved_yaml = Path("resolved-config.yml")
    resolved_yaml.write_text(yaml.safe_dump(config))
    print(f"YAML configuration updated and written to {resolved_yaml}")
    return resolved_yaml


def render_outputs(
    output_path: Path,
    build_version: str,
    build_image_type: str,
    os_family: str,
    os_version: str,
    containerfile_path: Path,
    enable_plymouth: bool,
) -> None:
    with output_path.open("a", encoding="utf-8") as output:
        output.write(f"BUILD_VERSION={build_version}\n")
        output.write(f"BUILD_IMAGE_TYPE={build_image_type}\n")
        output.write(f"OS_FAMILY={os_family}\n")
        output.write(f"OS_VERSION={os_version}\n")
        output.write(f"CONTAINERFILE={containerfile_path}\n")
        output.write(f"ENABLE_PLYMOUTH={'true' if enable_plymouth else 'false'}\n")


def main() -> None:
    print("::group::Configuration Detection")

    input_image_type = os.environ.get("INPUT_IMAGE_TYPE", DEFAULT_IMAGE_TYPE)
    input_distro_version = os.environ.get("INPUT_DISTRO_VERSION", DEFAULT_VERSION)
    input_enable_plymouth = os.environ.get("INPUT_ENABLE_PLYMOUTH", "true").lower()
    input_window_manager = os.environ.get("INPUT_WINDOW_MANAGER", "")
    input_desktop_environment = os.environ.get("INPUT_DESKTOP_ENVIRONMENT", "")
    input_os = os.environ.get("INPUT_OS", "")
    input_yaml_config = os.environ.get("INPUT_YAML_CONFIG", "auto")

    print(f"Input image type: {input_image_type}")
    print(f"Input distro version: {input_distro_version}")
    print(f"Input OS: {input_os}")
    print(f"Input Plymouth: {input_enable_plymouth}")
    print(f"Input window manager: {input_window_manager}")
    print(f"Input desktop environment: {input_desktop_environment}")
    print(f"Input YAML config: {input_yaml_config}")

    target_version = input_distro_version
    target_image_type = input_image_type
    enable_plymouth = input_enable_plymouth == "true"

    os_name = input_os

    print(f"Resolved target: {target_image_type} version {target_version}")
    print(f"Plymouth enabled: {enable_plymouth}")

    yaml_config = resolve_yaml_config(
        input_yaml_config,
        target_image_type,
        os_name=os_name,
        window_manager=input_window_manager,
        desktop_environment=input_desktop_environment,
    )

    resolved_yaml = yaml_config
    if target_image_type.startswith("fedora-"):
        print(f"Applying Fedora version ({target_version}) to YAML config")
        resolved_yaml = apply_fedora_overrides(
            yaml_config,
            target_image_type,
            target_version,
            input_window_manager,
            input_desktop_environment,
        )

    print("::group::YAML to Containerfile Transpilation")
    print(f"Generating Containerfile from {resolved_yaml}...")

    containerfile_path = Path("Containerfile.generated")
    cmd = [
        "python3",
        "tools/yaml-to-containerfile.py",
        "--config",
        str(resolved_yaml),
        "--image-type",
        target_image_type,
        "--fedora-version",
        str(target_version),
        "--output",
        str(containerfile_path),
        "--verbose",
        "--enable-plymouth" if enable_plymouth else "--disable-plymouth",
    ]
    subprocess.run(cmd, check=True)

    print(f"Generated Containerfile: {containerfile_path}")
    print("::endgroup::")

    os_family = "unknown"
    os_version = "latest"

    if target_image_type.startswith("fedora-"):
        os_family, os_version = "fedora", target_version

    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        print("::error::GITHUB_OUTPUT is not set")
        sys.exit(1)

    render_outputs(
        Path(github_output),
        target_version,
        target_image_type,
        os_family,
        os_version,
        containerfile_path,
        enable_plymouth,
    )

    print("::endgroup::")


if __name__ == "__main__":
    main()
