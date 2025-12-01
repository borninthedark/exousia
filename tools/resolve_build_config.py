#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

import yaml


DEFAULT_VERSION = "43"
DEFAULT_IMAGE_TYPE = "fedora-sway-atomic"


def read_fedora_version_file(path: Path) -> tuple[str, str]:
    if not path.exists():
        print(f"Using defaults: {DEFAULT_VERSION}:{DEFAULT_IMAGE_TYPE}")
        return DEFAULT_VERSION, DEFAULT_IMAGE_TYPE

    content = path.read_text().strip()
    if not content:
        print(f"Using defaults: {DEFAULT_VERSION}:{DEFAULT_IMAGE_TYPE}")
        return DEFAULT_VERSION, DEFAULT_IMAGE_TYPE

    parts = content.split(":", 1)
    if len(parts) == 2:
        version, image_type = parts
        print(f"Detected from .fedora-version: {version}:{image_type}")
        return version, image_type

    print("::warning::.fedora-version is malformed; falling back to defaults")
    return DEFAULT_VERSION, DEFAULT_IMAGE_TYPE


def resolve_yaml_config(input_yaml_config: str, target_image_type: str) -> Path:
    if input_yaml_config == "auto":
        candidate = Path(f"yaml-definitions/{target_image_type}.yml")
        if candidate.exists():
            print(f"Auto-detected config: {candidate}")
            return candidate.resolve()

        default_config = Path("exousia.yml")
        if default_config.exists():
            print(f"Using default config: {default_config}")
            return default_config.resolve()

        print(f"::error::No config file found for {target_image_type}")
        sys.exit(1)

    yaml_config = Path(input_yaml_config)
    if not yaml_config.exists():
        print(f"::error::YAML config file not found: {yaml_config}")
        sys.exit(1)

    return yaml_config.resolve()


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

    if target_image_type == "fedora-bootc":
        desktop = config.get("desktop") or {}

        if window_manager:
            desktop["window_manager"] = window_manager
            desktop.pop("desktop_environment", None)
        elif desktop_environment:
            desktop["desktop_environment"] = desktop_environment
            desktop.pop("window_manager", None)

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

    input_image_type = os.environ.get("INPUT_IMAGE_TYPE", "current")
    input_distro_version = os.environ.get("INPUT_DISTRO_VERSION", "current")
    input_enable_plymouth = os.environ.get("INPUT_ENABLE_PLYMOUTH", "true").lower()
    input_window_manager = os.environ.get("INPUT_WINDOW_MANAGER", "")
    input_desktop_environment = os.environ.get("INPUT_DESKTOP_ENVIRONMENT", "")
    input_yaml_config = os.environ.get("INPUT_YAML_CONFIG", "auto")

    print(f"Input image type: {input_image_type}")
    print(f"Input distro version: {input_distro_version}")
    print(f"Input Plymouth: {input_enable_plymouth}")
    print(f"Input window manager: {input_window_manager}")
    print(f"Input desktop environment: {input_desktop_environment}")
    print(f"Input YAML config: {input_yaml_config}")

    fedora_version_file = Path(".fedora-version")
    current_version, current_image_type = read_fedora_version_file(fedora_version_file)

    target_version = input_distro_version if input_distro_version != "current" else current_version
    target_image_type = input_image_type if input_image_type != "current" else current_image_type
    enable_plymouth = input_enable_plymouth == "true"

    print(f"Resolved target: {target_image_type} version {target_version}")
    print(f"Plymouth enabled: {enable_plymouth}")

    yaml_config = resolve_yaml_config(input_yaml_config, target_image_type)

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

    if target_image_type.startswith("fedora-"):
        desired = f"{target_version}:{target_image_type}\n"
        current_contents = fedora_version_file.read_text() if fedora_version_file.exists() else ""
        if current_contents != desired:
            fedora_version_file.write_text(desired)
            print(f"Configuration updated to: {desired.strip()}")
        else:
            print("Configuration unchanged")

    os_family = "unknown"
    os_version = "latest"
    family_map = {
        "arch": ("arch", "latest"),
        "gentoo": ("gentoo", "latest"),
        "debian": ("debian", "unstable"),
        "ubuntu": ("ubuntu", "mantic"),
        "opensuse": ("opensuse", "tumbleweed"),
        "proxmox": ("proxmox", "unstable"),
    }

    if target_image_type.startswith("fedora-"):
        os_family, os_version = "fedora", target_version
    elif target_image_type in family_map:
        os_family, os_version = family_map[target_image_type]

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
