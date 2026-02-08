#!/usr/bin/env python3
"""
Exousia YAML to Containerfile Transpiler
=========================================

Converts BlueBuild-compatible YAML configuration into Containerfile format.
Supports conditional logic, multiple base images, and modular build steps.

Usage:
    python3 yaml-to-containerfile.py --config adnyeus.yml --output Containerfile
    python3 yaml-to-containerfile.py --config adnyeus.yml --image-type fedora-bootc --validate
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


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


# Fedora Atomic Desktop variants
FEDORA_ATOMIC_VARIANTS = {
    "fedora-sway-atomic": "quay.io/fedora/fedora-sway-atomic",
}


@dataclass
class BuildContext:
    """Build context for evaluating conditions and generating Containerfile."""

    image_type: str
    fedora_version: str  # For Fedora-based images; can be empty for Linux bootc
    enable_plymouth: bool
    use_upstream_sway_config: bool
    base_image: str
    distro: str = "fedora"  # fedora-only
    desktop_environment: str = ""  # kde, gnome, mate, etc.
    window_manager: str = ""  # sway, kwin, etc.


class ContainerfileGenerator:
    """Generates Containerfile from YAML configuration."""

    def __init__(self, config: dict[str, Any], context: BuildContext):
        self.config = config
        self.context = context

    def generate(self) -> str:
        """Generate complete Containerfile from config.

        This method is stateless and can be called multiple times.
        Each call generates a fresh Containerfile.
        """
        self.lines: list[str] = []
        self._add_header()
        self._add_build_args()
        self._add_from()
        # SHELL directive removed - not supported in OCI format
        # RUN commands use explicit bash with pipefail instead
        self._add_labels()
        self._add_environment()
        self._process_modules()
        return "\n".join(self.lines)

    def _load_common_remove_packages(self) -> list[str]:
        """Load the shared removal list from packages/common/remove.yml."""
        try:
            from package_loader import PackageLoader

            loader = PackageLoader()
            return list(loader.load_remove())
        except Exception:
            return []

    def _add_header(self):
        """Add file header with generation info."""
        self.lines.extend(
            [
                "# " + "=" * 70,
                f"# Auto-generated Containerfile from {self.config.get('name', 'config')}.yml",
                "# DO NOT EDIT MANUALLY - Changes will be overwritten",
                f"# Generated for: {self.context.image_type}",
                "# " + "=" * 70,
                "",
            ]
        )

    def _add_build_args(self):
        """Add ARG declarations."""
        self.lines.extend(
            [
                "# " + "-" * 30,
                "# Build arguments",
                "# " + "-" * 30,
                f"ARG FEDORA_VERSION={self.context.fedora_version}",
            ]
        )

        if self.context.image_type == "fedora-bootc":
            self.lines.append(f"ARG ENABLE_PLYMOUTH={str(self.context.enable_plymouth).lower()}")

        self.lines.append("")

    def _add_from(self):
        """Add FROM instruction."""
        self.lines.extend(
            [
                "# " + "-" * 30,
                "# Base image",
                "# " + "-" * 30,
                f"FROM {self.context.base_image}",
                "",
            ]
        )

    def _add_shell(self):
        """DEPRECATED: SHELL directive not supported in OCI image format.

        This method is no longer used. RUN commands explicitly use bash with
        pipefail via 'set -euxo pipefail' instead.

        Note: If building with Docker format (not OCI), this directive could be
        re-enabled, but it's not necessary since RUN commands already specify bash.
        """
        # SHELL directive removed - causes warnings with OCI format:
        # "SHELL is not supported for OCI image format, [/bin/bash -o pipefail -c]
        # will be ignored. Must use `docker` format"
        pass

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
        self.lines.extend(
            [
                "# " + "-" * 30,
                "# Environment",
                "# " + "-" * 30,
                f"ENV BUILD_IMAGE_TYPE={self.context.image_type}",
            ]
        )

        if self.context.image_type == "fedora-bootc":
            plymouth_val = str(self.context.enable_plymouth).lower()
            self.lines.append(f"ENV ENABLE_PLYMOUTH={plymouth_val}")
            self.lines.append("")
            self.lines.append(
                f'RUN echo "BUILD_IMAGE_TYPE={self.context.image_type}" '
                f">> /etc/environment && \\"
            )
            self.lines.append(
                f'    echo "ENABLE_PLYMOUTH={plymouth_val}" >> /etc/environment && \\'
            )
            self.lines.append('    echo "LANG=en_US.UTF-8" >> /etc/environment && \\')
            self.lines.append('    echo "LC_ALL=en_US.UTF-8" >> /etc/environment')
        else:
            self.lines.append("")
            self.lines.append(
                f'RUN echo "BUILD_IMAGE_TYPE={self.context.image_type}" '
                f">> /etc/environment && \\"
            )
            self.lines.append('    echo "LANG=en_US.UTF-8" >> /etc/environment && \\')
            self.lines.append('    echo "LC_ALL=en_US.UTF-8" >> /etc/environment')

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
            self.lines.extend(
                [
                    "# " + "-" * 30,
                    f"# Module {idx}: {module_type}",
                    "# " + "-" * 30,
                ]
            )

            # Process based on type
            if module_type == "files":
                self._process_files_module(module)
            elif module_type == "script":
                self._process_script_module(module)
            elif module_type == "rpm-ostree":
                self._process_rpm_module(module)
            elif module_type == "package-loader":
                self._process_package_loader_module(module)
            elif module_type == "systemd":
                self._process_systemd_module(module)
            elif module_type == "sddm-themes":
                self._process_sddm_themes_module(module)
            else:
                self.lines.append(f"# WARNING: Unknown module type: {module_type}")

            self.lines.append("")

    def _process_files_module(self, module: dict[str, Any]):
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

    def _render_script_lines(self, lines: list[str], set_command: str):
        """Render a sequence of shell lines as a single RUN instruction."""

        # Keywords that start or are in the middle of compound statements (no semicolon needed)
        COMPOUND_STARTERS = {"if", "then", "else", "elif", "do", "case"}
        # Keywords that end compound statements (need semicolon before next command)
        COMPOUND_ENDERS = {"fi", "done", "esac"}

        self.lines.append(f"RUN {set_command}; \\")

        in_heredoc = False

        def has_next_command(idx: int) -> bool:
            """Return True if there is another non-comment line after idx."""

            for next_line in lines[idx + 1 :]:
                stripped_next = next_line.strip()
                if stripped_next and not stripped_next.startswith("#"):
                    return True
            return False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Check if line already ends with backslash (line continuation)
            has_continuation = line.rstrip().endswith("\\")

            # Check if line ends with a shell keyword
            last_word = line.split()[-1] if line.split() else ""
            has_more_commands = has_next_command(i)

            if in_heredoc:
                # Preserve heredoc contents verbatim
                self.lines.append(f"    {line}")
                if stripped == "EOF":
                    in_heredoc = False
                continue

            if "<<" in stripped:
                # Start of heredoc: emit as-is and switch to heredoc mode
                self.lines.append(f"    {line}")
                in_heredoc = True
                continue

            # Comment lines should not influence line continuations because build
            # tools may strip them before sending commands to the shell.
            if stripped.startswith("#"):
                self.lines.append(f"    {line}")
                continue

            if has_continuation:
                # Line already has backslash continuation, don't add semicolon
                self.lines.append(f"    {line}")
            elif last_word in COMPOUND_ENDERS and has_more_commands:
                # Compound statement enders (fi, done, esac) need semicolon before next command
                self.lines.append(f"    {line}; \\")
            elif last_word in COMPOUND_STARTERS and has_more_commands:
                # Compound statement starters/middles don't need semicolon
                self.lines.append(f"    {line} \\")
            elif has_more_commands:
                # Regular commands need semicolon
                self.lines.append(f"    {line}; \\")
            else:
                # Last line
                self.lines.append(f"    {line}")

    def _process_script_module(self, module: dict[str, Any]):
        """Process script module (RUN instructions)."""
        scripts = module.get("scripts", [])

        if not scripts:
            return

        def collect_lines(script_block: str) -> list[str]:
            return [line.strip() for line in script_block.split("\n") if line.strip()]

        if len(scripts) == 1:
            script = scripts[0]
            if "\n" in script:
                lines = collect_lines(script)
                if lines:
                    self._render_script_lines(lines, "set -e")
            else:
                script = script.strip()
                if script:
                    self.lines.append(f"RUN {script}")
        else:
            all_lines: list[str] = []
            for script in scripts:
                if "\n" in script:
                    all_lines.extend(collect_lines(script))
                else:
                    stripped = script.strip()
                    if stripped:
                        all_lines.append(stripped)

            if all_lines:
                self._render_script_lines(all_lines, "set -euxo pipefail")

    def _process_rpm_module(self, module: dict[str, Any]):
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
                    pkg_list = " ".join(packages)
                    self.lines.append(
                        f'    echo "==> Installing {len(packages)} conditional packages..."; \\'
                    )
                    self.lines.append(f"    dnf install -y --skip-unavailable {pkg_list}; \\")

        # Regular package installation
        install_packages = module.get("install", [])
        if install_packages:
            pkg_list = " ".join(install_packages)
            self.lines.append(
                f'    echo "==> Installing {len(install_packages)} custom packages..."; \\'
            )
            self.lines.append(f"    dnf install -y {pkg_list}; \\")

        # Package removal
        remove_packages = list(dict.fromkeys(module.get("remove", [])))

        # Always honor the shared removal list so common removals are consistent
        for pkg in self._load_common_remove_packages():
            if pkg not in remove_packages:
                remove_packages.append(pkg)

        if remove_packages:
            pkg_list = " ".join(remove_packages)
            self.lines.append(f'    echo "==> Removing {len(remove_packages)} packages..."; \\')
            self.lines.append(f"    dnf remove -y {pkg_list}; \\")

        # Upgrade and cleanup
        self.lines.append("    dnf upgrade -y; \\")
        self.lines.append("    dnf clean all")

    def _process_package_loader_module(self, module: dict[str, Any]):
        """Process package-loader module (new YAML-based package management)."""
        import sys
        from pathlib import Path

        # Import the package loader
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))

        try:
            from package_loader import PackageLoader
        except ImportError:
            self.lines.append("# ERROR: package_loader module not found")
            return

        loader = PackageLoader()

        wm = module.get("window_manager")
        de = module.get("desktop_environment")
        include_common = module.get("include_common", True)

        # Load packages
        try:
            packages = loader.get_package_list(wm=wm, de=de, include_common=include_common)
        except Exception as e:
            self.lines.append(f"# ERROR loading packages: {e}")
            return

        install_packages = packages["install"]
        remove_packages = packages["remove"]
        groups = packages.get("groups", [])

        # Generate installation instructions
        self.lines.append("# hadolint ignore=DL3041,SC2086")
        self.lines.append("RUN set -euxo pipefail; \\")

        # Install dnf5
        self.lines.append("    dnf install -y dnf5 dnf5-plugins && \\")
        self.lines.append("    rm -f /usr/bin/dnf && ln -s /usr/bin/dnf5 /usr/bin/dnf; \\")

        # Add repositories (RPMFusion for Fedora)
        if self.context.distro == "fedora":
            self.lines.append("    FEDORA_VERSION=$(rpm -E %fedora); \\")
            self.lines.append(
                "    dnf install -y https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm; \\"
            )
            self.lines.append(
                "    dnf install -y https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \\"
            )
            self.lines.append("    dnf config-manager setopt fedora-cisco-openh264.enabled=1; \\")

        # Install package groups (for Fedora-based distros)
        # Groups are only supported on Fedora/DNF-based systems
        if groups and self.context.distro == "fedora":
            for group in groups:
                self.lines.append(f"    dnf install -y @{group}; \\")

        # Remove conflicting packages FIRST (before installation)
        # This is critical for packages like swaylock when switching between variants
        if remove_packages:
            packages_str = " ".join(remove_packages)
            self.lines.append(f"    dnf remove -y {packages_str} || true; \\")

        # Install individual packages
        if install_packages:
            # Build exclude flags for packages that need to be removed
            # This prevents DNF from pulling them in as dependencies during install
            exclude_flags = ""
            if remove_packages:
                exclude_flags = " ".join(f"--exclude={pkg}" for pkg in remove_packages) + " "

            # Split packages into chunks to avoid command line length issues
            chunk_size = 50
            chunks = [
                install_packages[i : i + chunk_size]
                for i in range(0, len(install_packages), chunk_size)
            ]

            for _i, chunk in enumerate(chunks):
                packages_str = " ".join(chunk)
                self.lines.append(
                    f"    dnf install -y --skip-unavailable {exclude_flags}{packages_str}; \\"
                )

        # Upgrade and cleanup
        self.lines.append("    dnf upgrade -y; \\")
        self.lines.append("    dnf clean all")

    def _process_systemd_module(self, module: dict[str, Any]):
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

    def _process_sddm_themes_module(self, module: dict[str, Any]):
        """Process sddm-themes module for automatic theme extraction and configuration."""
        themes_source = module.get("source", "/tmp/sddm-themes-source")  # nosec B108
        themes_dest = module.get("destination", "/usr/share/sddm/themes")
        config_file = module.get("config", "/etc/sddm.conf.d/99-theme.conf")

        self.lines.extend(
            [
                "RUN set -eux; \\",
                f"    THEMES_SOURCE='{themes_source}'; \\",
                f"    THEMES_DEST='{themes_dest}'; \\",
                f"    SDDM_CONF='{config_file}'; \\",
                "    echo '==> Setting up SDDM themes'; \\",
                '    mkdir -p "$THEMES_DEST"; \\',
                '    if [ ! -d "$THEMES_SOURCE" ] || [ -z "$(ls -A "$THEMES_SOURCE" 2>/dev/null || true)" ]; then \\',
                "        echo 'No SDDM theme bundles found, skipping theme setup'; \\",
                "        exit 0; \\",
                "    fi; \\",
                "    EXTRACTED_THEMES=(); \\",
                '    for bundle in "$THEMES_SOURCE"/*.zip "$THEMES_SOURCE"/*.tar "$THEMES_SOURCE"/*.tar.gz "$THEMES_SOURCE"/*.tgz "$THEMES_SOURCE"/*.tar.bz2 "$THEMES_SOURCE"/*.tar.xz 2>/dev/null || true; do \\',
                '        [ -e "$bundle" ] || continue; \\',
                '        echo "Processing theme bundle: $(basename "$bundle")"; \\',
                '        case "$bundle" in \\',
                "            *.zip) \\",
                '                unzip -q "$bundle" -d "$THEMES_DEST"; \\',
                "                ;; \\",
                "            *.tar.gz|*.tgz) \\",
                '                tar -xzf "$bundle" -C "$THEMES_DEST"; \\',
                "                ;; \\",
                "            *.tar.bz2) \\",
                '                tar -xjf "$bundle" -C "$THEMES_DEST"; \\',
                "                ;; \\",
                "            *.tar.xz) \\",
                '                tar -xJf "$bundle" -C "$THEMES_DEST"; \\',
                "                ;; \\",
                "            *.tar) \\",
                '                tar -xf "$bundle" -C "$THEMES_DEST"; \\',
                "                ;; \\",
                "        esac; \\",
                '        echo "  Extracted: $(basename "$bundle")"; \\',
                "    done; \\",
                '    for theme_dir in "$THEMES_DEST"/*; do \\',
                '        [ -d "$theme_dir" ] || continue; \\',
                '        if [ -f "$theme_dir/metadata.desktop" ]; then \\',
                '            theme_name=$(basename "$theme_dir"); \\',
                '            EXTRACTED_THEMES+=("$theme_name"); \\',
                '            echo "  Found valid theme: $theme_name"; \\',
                "        fi; \\",
                "    done; \\",
                "    if [ ${#EXTRACTED_THEMES[@]} -gt 0 ]; then \\",
                '        DEFAULT_THEME="${EXTRACTED_THEMES[0]}"; \\',
                '        echo "==> Setting default SDDM theme: $DEFAULT_THEME"; \\',
                '        mkdir -p "$(dirname "$SDDM_CONF")"; \\',
                '        printf \'[Theme]\\\\n# Auto-configured by sddm-themes module\\\\nCurrent=%s\\\\n\' "$DEFAULT_THEME" > "$SDDM_CONF"; \\',
                '        echo "  Theme configuration written to: $SDDM_CONF"; \\',
                '        echo "  Total themes installed: ${#EXTRACTED_THEMES[@]}"; \\',
                "    else \\",
                "        echo 'No valid SDDM themes found in bundles'; \\",
                "    fi; \\",
                "    echo '==> SDDM theme setup complete'",
            ]
        )

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against current context."""
        # Simple condition evaluation
        # Supports: image-type == "value", enable_plymouth == true/false,
        #          use_upstream_sway_config == true/false, distro == "value",
        #          desktop_environment == "value", window_manager == "value"

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
            right = right.strip("\"'")

            if left == "image-type":
                return self.context.image_type == right
            if left == "distro":
                return self.context.distro == right
            if left == "enable_plymouth":
                return self.context.enable_plymouth == (right.lower() == "true")
            if left == "use_upstream_sway_config":
                return self.context.use_upstream_sway_config == (right.lower() == "true")
            if left == "desktop_environment":
                return self.context.desktop_environment == right
            if left == "window_manager":
                return self.context.window_manager == right

        return False


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
    preferred_base = config.get("base-image")

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


def main():
    parser = argparse.ArgumentParser(
        description="Transpile YAML config to Containerfile",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate Containerfile for fedora-sway-atomic
  python3 yaml-to-containerfile.py --config adnyeus.yml --output Containerfile.generated

  # Generate for fedora-bootc with Plymouth enabled
  python3 yaml-to-containerfile.py --config adnyeus.yml --image-type fedora-bootc --enable-plymouth --output Containerfile.bootc.generated

  # Validate only
  python3 yaml-to-containerfile.py --config adnyeus.yml --validate
        """,
    )

    parser.add_argument(
        "-c", "--config", type=Path, required=True, help="Path to YAML configuration file"
    )
    parser.add_argument(
        "-o", "--output", type=Path, help="Output Containerfile path (default: stdout)"
    )
    # Build the list of all supported image types dynamically
    all_image_types = ["fedora-bootc", *FEDORA_ATOMIC_VARIANTS.keys()]

    parser.add_argument(
        "--image-type", choices=all_image_types, help="Base image type (default: from config)"
    )
    parser.add_argument(
        "--fedora-version",
        default="43",
        help="Fedora version (default: 43, ignored for Linux bootc distros)",
    )
    parser.add_argument(
        "--enable-plymouth", action="store_true", default=True, help="Enable Plymouth"
    )
    parser.add_argument("--disable-plymouth", action="store_true", help="Disable Plymouth")
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
        distro=distro,
        desktop_environment=desktop_environment,
        window_manager=window_manager,
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
