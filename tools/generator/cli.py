import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from .constants import FEDORA_ATOMIC_VARIANTS
from .context import BuildContext
from .generator import ContainerfileGenerator


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    """Load and validate YAML configuration."""
    try:
        with open(config_path, encoding="utf-8") as f:
            config: dict[str, Any] = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        sys.exit(1)


def determine_base_image(config: dict[str, Any], image_type: str, version: str) -> str:
    """Determine the base image URL based on configuration."""
    if not version:
        raise ValueError("version must be specified")

    preferred_base = config.get("base-image")

    def ensure_version_tag(image: str) -> str:
        """Ensure the image reference is tagged with the provided version."""
        tail = image.split("/")[-1]

        # If the image already includes a tag or digest, keep it as-is
        if ":" in tail or "@" in tail:
            return image

        return f"{image}:{version}"

    if preferred_base:
        return ensure_version_tag(preferred_base)

    # Fedora-based images
    if image_type == "fedora-bootc":
        return f"quay.io/fedora/fedora-bootc:{version}"

    # Fedora Atomic variants
    if image_type in FEDORA_ATOMIC_VARIANTS:
        return f"{FEDORA_ATOMIC_VARIANTS[image_type]}:{version}"

    # Use config default
    return preferred_base or f"quay.io/fedora/fedora-bootc:{version}"


def validate_config(config: dict[str, Any]) -> bool:
    """Validate YAML configuration structure."""
    required_fields = ["name", "description", "modules"]

    for field in required_fields:
        if field not in config:
            print(f"Error: Missing required field: {field}", file=sys.stderr)
            return False

    print("✓ Configuration validation passed")
    return True


def main(generator: ContainerfileGenerator | None = None):
    parser = argparse.ArgumentParser(
        description="Transpile YAML config to Containerfile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Containerfile for fedora-sway-atomic
  uv run python -m generator --config adnyeus.yml --output Dockerfile.generated

  # Generate for fedora-bootc with Plymouth enabled
  uv run python -m generator --config adnyeus.yml --image-type fedora-bootc --enable-plymouth --output Dockerfile.bootc.generated

  # Validate only
  uv run python -m generator --config adnyeus.yml --validate
        """,
    )

    parser.add_argument(
        "-c", "--config", type=Path, required=True, help="Path to YAML configuration file"
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Output Containerfile path (default: stdout)"
    )
    parser.add_argument(
        "--resolved-package-plan",
        type=Path,
        help="Write normalized resolved package plan JSON to this path",
    )
    # Build the list of all supported image types dynamically
    all_image_types = ["fedora-bootc", *FEDORA_ATOMIC_VARIANTS.keys()]

    parser.add_argument(
        "--image-type", choices=all_image_types, help="Base image type (default: from config)"
    )
    parser.add_argument(
        "--fedora-version",
        default="",
        help="Fedora version (default: from config, ignored for Linux bootc distros)",
    )
    parser.add_argument(
        "--enable-plymouth", action="store_true", default=True, help="Enable Plymouth"
    )
    parser.add_argument("--disable-plymouth", action="store_true", help="Disable Plymouth")
    parser.add_argument(
        "--enable-zfs", action="store_true", default=False, help="Enable ZFS support"
    )
    parser.add_argument("--disable-zfs", action="store_true", help="Disable ZFS support")
    parser.add_argument(
        "--validate", action="store_true", help="Validate config only, don't generate"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load configuration
    if args.verbose:
        print(f"Loading configuration from: {args.config}")
    config = load_yaml_config(args.config)

    # Validate
    if not validate_config(config):
        sys.exit(1)

    if args.validate:
        print("Configuration is valid!")
        sys.exit(0)

    # Determine build context
    image_type = args.image_type or config.get("image-type", "fedora-sway-atomic")
    fedora_version = args.fedora_version or str(config.get("image-version", "43"))
    enable_plymouth = args.enable_plymouth and not args.disable_plymouth
    enable_zfs = args.enable_zfs and not args.disable_zfs

    # Extract build configuration
    build_config = config.get("build", {})
    use_upstream_sway_config = build_config.get("use_upstream_sway_config", False)

    try:
        base_image = determine_base_image(config, image_type, fedora_version)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Only Fedora-based images are supported
    distro = "fedora"

    # Extract desktop configuration
    desktop_config = config.get("desktop", {})
    desktop_environment = desktop_config.get("desktop_environment", "")
    window_manager = desktop_config.get("window_manager", "")

    if args.verbose:
        print("Build context:")
        print(f"  Image type: {image_type}")
        print(f"  Distro: {distro}")
        print(f"  Fedora version: {fedora_version}")
        print(f"  Plymouth: {enable_plymouth}")
        print(f"  ZFS: {enable_zfs}")
        print(f"  Sway Config: {'upstream' if use_upstream_sway_config else 'custom'}")
        print(f"  Base image: {base_image}")
        print(f"  Desktop Environment: {desktop_environment}")
        print(f"  Window Manager: {window_manager}")

    context = BuildContext(
        image_type=image_type,
        fedora_version=fedora_version,
        enable_plymouth=enable_plymouth,
        use_upstream_sway_config=use_upstream_sway_config,
        base_image=base_image,
        enable_zfs=enable_zfs,
        distro=distro,
        desktop_environment=desktop_environment,
        window_manager=window_manager,
    )

    # Generate Containerfile
    if generator is None:
        generator = ContainerfileGenerator(config, context)
    containerfile_content = generator.generate()

    # Output
    if args.output:
        args.output.write_text(containerfile_content)
        print(f"✓ Containerfile generated: {args.output}")
    else:
        print(containerfile_content)

    if args.resolved_package_plan:
        args.resolved_package_plan.write_text(
            json.dumps(generator.get_resolved_package_plan(), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"✓ Resolved package plan written: {args.resolved_package_plan}")
