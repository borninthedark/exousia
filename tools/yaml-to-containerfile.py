#!/usr/bin/env python3
"""
Exousia YAML to Containerfile Transpiler
=========================================

Converts BlueBuild-compatible YAML configuration into Containerfile format.
Supports conditional logic, multiple base images, and modular build steps.

Usage:
    python3 yaml-to-containerfile.py --config exousia.yml --output Containerfile
    python3 yaml-to-containerfile.py --config exousia.yml --image-type fedora-bootc --validate
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


@dataclass
class BuildContext:
    """Build context for evaluating conditions and generating Containerfile."""
    image_type: str
    fedora_version: str
    enable_plymouth: bool
    base_image: str


class ContainerfileGenerator:
    """Generates Containerfile from YAML configuration."""

    def __init__(self, config: Dict[str, Any], context: BuildContext):
        self.config = config
        self.context = context

    def generate(self) -> str:
        """Generate complete Containerfile from config.

        This method is stateless and can be called multiple times.
        Each call generates a fresh Containerfile.
        """
        self.lines: List[str] = []
        self._add_header()
        self._add_build_args()
        self._add_from()
        self._add_labels()
        self._add_environment()
        self._process_modules()
        return "\n".join(self.lines)

    def _add_header(self):
        """Add file header with generation info."""
        self.lines.extend([
            "# " + "=" * 70,
            f"# Auto-generated Containerfile from {self.config.get('name', 'config')}.yml",
            "# DO NOT EDIT MANUALLY - Changes will be overwritten",
            f"# Generated for: {self.context.image_type}",
            "# " + "=" * 70,
            "",
        ])

    def _add_build_args(self):
        """Add ARG declarations."""
        self.lines.extend([
            "# " + "-" * 30,
            "# Build arguments",
            "# " + "-" * 30,
            f"ARG FEDORA_VERSION={self.context.fedora_version}",
        ])

        if self.context.image_type == "fedora-bootc":
            self.lines.append(f"ARG ENABLE_PLYMOUTH={str(self.context.enable_plymouth).lower()}")

        self.lines.append("")

    def _add_from(self):
        """Add FROM instruction."""
        self.lines.extend([
            "# " + "-" * 30,
            "# Base image",
            "# " + "-" * 30,
            f"FROM {self.context.base_image}",
            "",
        ])

    def _add_labels(self):
        """Add LABEL instructions."""
        labels = self.config.get("labels", {})
        if not labels:
            return

        self.lines.append("# OCI Labels for better metadata")
        for key, value in labels.items():
            self.lines.append(f'LABEL {key}="{value}"')
        self.lines.append("")

    def _add_environment(self):
        """Add environment variables."""
        self.lines.extend([
            "# " + "-" * 30,
            "# Environment",
            "# " + "-" * 30,
            f"ENV BUILD_IMAGE_TYPE={self.context.image_type}",
        ])

        if self.context.image_type == "fedora-bootc":
            plymouth_val = str(self.context.enable_plymouth).lower()
            self.lines.append(f"    ENABLE_PLYMOUTH={plymouth_val}")
            self.lines.append("")
            self.lines.append(
                f'RUN echo "BUILD_IMAGE_TYPE={self.context.image_type}" '
                f'>> /etc/environment && \\'
            )
            self.lines.append(
                f'    echo "ENABLE_PLYMOUTH={plymouth_val}" >> /etc/environment'
            )
        else:
            self.lines.append("")
            self.lines.append(
                f'RUN echo "BUILD_IMAGE_TYPE={self.context.image_type}" '
                f'>> /etc/environment'
            )

        self.lines.append("")

    def _process_modules(self):
        """Process all modules in order."""
        modules = self.config.get("modules", [])

        for idx, module in enumerate(modules, 1):
            module_type = module.get("type")
            condition = module.get("condition")

            # Skip module if condition not met
            if condition and not self._evaluate_condition(condition):
                continue

            # Add section comment
            self.lines.extend([
                "# " + "-" * 30,
                f"# Module {idx}: {module_type}",
                "# " + "-" * 30,
            ])

            # Process based on type
            if module_type == "files":
                self._process_files_module(module)
            elif module_type == "script":
                self._process_script_module(module)
            elif module_type == "rpm-ostree":
                self._process_rpm_module(module)
            elif module_type == "systemd":
                self._process_systemd_module(module)
            else:
                self.lines.append(f"# WARNING: Unknown module type: {module_type}")

            self.lines.append("")

    def _process_files_module(self, module: Dict[str, Any]):
        """Process files module (COPY instructions)."""
        files = module.get("files", [])

        for file_spec in files:
            src = file_spec.get("src")
            dst = file_spec.get("dst")
            mode = file_spec.get("mode", "0644")

            if src and dst:
                # Handle directory copies (trailing /)
                if src.endswith("/"):
                    self.lines.append(f"COPY --chmod={mode} {src} {dst}")
                else:
                    self.lines.append(f"COPY --chmod={mode} {src} {dst}")

    def _process_script_module(self, module: Dict[str, Any]):
        """Process script module (RUN instructions)."""
        scripts = module.get("scripts", [])

        if not scripts:
            return

        # Shell keywords that should not have trailing semicolons
        SHELL_KEYWORDS = {'if', 'then', 'else', 'elif', 'fi', 'do', 'done', 'case', 'esac'}

        # Combine multiple scripts into single RUN if possible
        if len(scripts) == 1:
            script = scripts[0].strip()
            if "\n" in script:
                # Multi-line script - preserve shell structure
                lines = [line.strip() for line in script.split("\n") if line.strip()]
                self.lines.append("RUN set -e; \\")
                for i, line in enumerate(lines):
                    # Check if line ends with a shell keyword
                    last_word = line.split()[-1] if line.split() else ""
                    needs_semicolon = last_word not in SHELL_KEYWORDS and i < len(lines) - 1

                    if needs_semicolon:
                        self.lines.append(f"    {line}; \\")
                    elif i < len(lines) - 1:
                        self.lines.append(f"    {line} \\")
                    else:
                        self.lines.append(f"    {line}")
            else:
                self.lines.append(f"RUN {script}")
        else:
            # Multiple separate commands
            self.lines.append("RUN set -euxo pipefail; \\")
            for i, script in enumerate(scripts):
                script = script.strip()
                if i < len(scripts) - 1:
                    self.lines.append(f"    {script}; \\")
                else:
                    self.lines.append(f"    {script}")

    def _process_rpm_module(self, module: Dict[str, Any]):
        """Process rpm-ostree module (DNF operations)."""
        self.lines.append("# hadolint ignore=DL3041,SC2086")
        self.lines.append("RUN set -euxo pipefail; \\")

        # Install dnf5
        self.lines.append("    dnf install -y dnf5 dnf5-plugins && \\")
        self.lines.append("    rm -f /usr/bin/dnf && ln -s /usr/bin/dnf5 /usr/bin/dnf; \\")

        # Add repositories
        repos = module.get("repos", [])
        if repos:
            self.lines.append("    FEDORA_VERSION=$(rpm -E %fedora); \\")
            for repo in repos:
                # Replace version placeholder
                repo_url = repo.replace("43", "${FEDORA_VERSION}")
                self.lines.append(f"    dnf install -y {repo_url}; \\")

        # Config manager
        config_opts = module.get("config-manager", [])
        for opt in config_opts:
            self.lines.append(f"    dnf config-manager setopt {opt}.enabled=1; \\")

        # Conditional package installation (e.g., Sway packages for fedora-bootc)
        install_conditional = module.get("install-conditional", [])
        for cond_install in install_conditional:
            condition = cond_install.get("condition")
            if condition and self._evaluate_condition(condition):
                packages = cond_install.get("packages", [])
                if packages:
                    # Read from packages.sway file
                    self.lines.append('    echo "==> Installing Sway desktop packages..."; \\')
                    self.lines.append(
                        '    grep -vE \'^#|^$\' '
                        '/usr/local/share/sericea-bootc/packages-sway | '
                        'xargs -r dnf install -y --skip-unavailable; \\'
                    )

        # Regular package installation
        install_packages = module.get("install", [])
        if install_packages:
            self.lines.append(
                '    echo "==> Installing custom packages from packages.add..."; \\'
            )
            self.lines.append(
                '    grep -vE \'^#|^$\' '
                '/usr/local/share/sericea-bootc/packages-added | '
                'xargs -r dnf install -y; \\'
            )

        # Package removal
        remove_packages = module.get("remove", [])
        if remove_packages:
            self.lines.append('    echo "==> Removing packages from packages.remove..."; \\')
            self.lines.append(
                '    grep -vE \'^#|^$\' '
                '/usr/local/share/sericea-bootc/packages-removed | '
                'xargs -r dnf remove -y; \\'
            )

        # Upgrade and cleanup
        self.lines.append("    dnf upgrade -y; \\")
        self.lines.append("    dnf clean all")

    def _process_systemd_module(self, module: Dict[str, Any]):
        """Process systemd module (service management)."""
        system = module.get("system", {})
        enabled = system.get("enabled", [])
        default_target = module.get("default-target")

        commands = []

        if default_target:
            commands.append(f"systemctl set-default {default_target}")

        for service in enabled:
            commands.append(f"systemctl enable {service}")

        if commands:
            self.lines.append("RUN " + " && \\\n    ".join(commands))

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against current context."""
        # Simple condition evaluation
        # Supports: image-type == "value", enable_plymouth == true/false

        condition = condition.strip()

        # Handle AND conditions
        if " && " in condition:
            parts = condition.split(" && ")
            return all(self._evaluate_condition(part.strip()) for part in parts)

        # Handle OR conditions
        if " || " in condition:
            parts = condition.split(" || ")
            return any(self._evaluate_condition(part.strip()) for part in parts)

        # Simple equality check
        if "==" in condition:
            left, right = [x.strip() for x in condition.split("==", 1)]
            right = right.strip('"\'')

            if left == "image-type":
                return self.context.image_type == right
            if left == "enable_plymouth":
                return self.context.enable_plymouth == (right.lower() == "true")

        return False


def load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load and validate YAML configuration."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        sys.exit(1)


def determine_base_image(config: Dict[str, Any], image_type: str, version: str) -> str:
    """Determine the base image URL based on configuration."""
    preferred_base = config.get("base-image")
    allowed_prefixes = [
        "quay.io/fedora/fedora-bootc",
        "quay.io/fedora/fedora-sway-atomic",
        "ghcr.io/bootcrew/",
    ]

    def ensure_version_tag(image: str) -> str:
        """Ensure the image reference is tagged with the provided version.

        Images may omit an explicit tag (defaulting to "latest"), which is
        undesirable for OS/DE builds where version pinning is expected. This
        helper appends the requested version tag when the reference lacks a
        tag or digest.
        """

        tail = image.split("/")[-1]

        # If the image already includes a tag or digest, keep it as-is
        if ":" in tail or "@" in tail:
            return image

        return f"{image}:{version}"

    if preferred_base and any(preferred_base.startswith(prefix) for prefix in allowed_prefixes):
        return ensure_version_tag(preferred_base)

    if image_type == "fedora-bootc":
        return f"quay.io/fedora/fedora-bootc:{version}"
    if image_type == "fedora-sway-atomic":
        return f"quay.io/fedora/fedora-sway-atomic:{version}"
    if image_type == "bootcrew":
        return f"ghcr.io/bootcrew/bootc:{version}"

    # Use config default
    return preferred_base or f"quay.io/fedora/fedora-bootc:{version}"


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate YAML configuration structure."""
    required_fields = ["name", "description", "modules"]

    for field in required_fields:
        if field not in config:
            print(f"Error: Missing required field: {field}", file=sys.stderr)
            return False

    print("✓ Configuration validation passed")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Transpile YAML config to Containerfile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Containerfile for fedora-sway-atomic
  python3 yaml-to-containerfile.py --config exousia.yml --output Containerfile.generated

  # Generate for fedora-bootc with Plymouth enabled
  python3 yaml-to-containerfile.py --config exousia.yml --image-type fedora-bootc --enable-plymouth --output Containerfile.bootc.generated

  # Validate only
  python3 yaml-to-containerfile.py --config exousia.yml --validate
        """
    )

    parser.add_argument("-c", "--config", type=Path, required=True,
                        help="Path to YAML configuration file")
    parser.add_argument("-o", "--output", type=Path,
                        help="Output Containerfile path (default: stdout)")
    parser.add_argument("--image-type", choices=[
                        "fedora-bootc",
                        "fedora-sway-atomic",
                        "bootcrew",
                        ],
                        help="Base image type (default: from config)")
    parser.add_argument("--fedora-version", default="43",
                        help="Fedora version (default: 43)")
    parser.add_argument("--enable-plymouth", action="store_true", default=True,
                        help="Enable Plymouth")
    parser.add_argument("--disable-plymouth", action="store_true",
                        help="Disable Plymouth")
    parser.add_argument("--validate", action="store_true",
                        help="Validate config only, don't generate")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")

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
    base_image = determine_base_image(config, image_type, fedora_version)

    if args.verbose:
        print("Build context:")
        print(f"  Image type: {image_type}")
        print(f"  Fedora version: {fedora_version}")
        print(f"  Plymouth: {enable_plymouth}")
        print(f"  Base image: {base_image}")

    context = BuildContext(
        image_type=image_type,
        fedora_version=fedora_version,
        enable_plymouth=enable_plymouth,
        base_image=base_image
    )

    # Generate Containerfile
    generator = ContainerfileGenerator(config, context)
    containerfile_content = generator.generate()

    # Output
    if args.output:
        args.output.write_text(containerfile_content)
        print(f"✓ Containerfile generated: {args.output}")
    else:
        print(containerfile_content)


if __name__ == "__main__":
    main()
