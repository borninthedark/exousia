from typing import Any

from .context import BuildContext
from .processors import ModuleProcessorsMixin


class ContainerfileGenerator(ModuleProcessorsMixin):
    """Generates Containerfile from YAML configuration."""

    def __init__(self, config: dict[str, Any], context: BuildContext):
        self.config = config
        self.context = context
        self.package_plans: list[dict[str, Any]] = []

    def generate(self) -> str:
        """Generate complete Containerfile from config.

        This method is stateless and can be called multiple times.
        Each call generates a fresh Containerfile.
        """
        self.lines: list[str] = []
        self.package_plans = []
        self._add_header()
        self._add_build_args()
        self._add_from()
        # SHELL directive removed - not supported in OCI format
        # RUN commands use explicit bash with pipefail instead
        self._add_labels()
        self._add_environment()
        self._process_modules()
        return "\n".join(self.lines)

    def get_resolved_package_plan(self) -> dict[str, Any]:
        """Return an aggregated resolved package plan for all package-loader modules."""
        install_sources: dict[str, set[str]] = {}
        remove_sources: dict[str, set[str]] = {}
        group_install_sources: dict[str, set[str]] = {}
        group_remove_sources: dict[str, set[str]] = {}
        bundles: list[dict[str, Any]] = []
        selections: list[dict[str, Any]] = []

        for plan in self.package_plans:
            selections.append(plan.get("selection", {}))
            bundles.extend(plan.get("bundles", []))
            rpm = plan.get("rpm", {})
            groups = rpm.get("groups", {})
            for item in groups.get("install", []):
                group_install_sources.setdefault(item["name"], set()).update(item.get("from", []))
            for item in groups.get("remove", []):
                group_remove_sources.setdefault(item["name"], set()).update(item.get("from", []))

            for item in rpm.get("install", []):
                install_sources.setdefault(item["name"], set()).update(item.get("from", []))
            for item in rpm.get("remove", []):
                remove_sources.setdefault(item["name"], set()).update(item.get("from", []))

        return {
            "image": {
                "name": self.config.get("name"),
                "base_image": self.context.base_image,
                "image_type": self.context.image_type,
                "fedora_version": self.context.fedora_version,
                "desktop_environment": self.context.desktop_environment or None,
                "window_manager": self.context.window_manager or None,
                "enable_plymouth": self.context.enable_plymouth,
                "enable_zfs": self.context.enable_zfs,
            },
            "package_loader_modules": selections,
            "bundles": bundles,
            "rpm": {
                "install": [
                    {"name": pkg, "from": sorted(sources)}
                    for pkg, sources in sorted(install_sources.items())
                ],
                "remove": [
                    {"name": pkg, "from": sorted(sources)}
                    for pkg, sources in sorted(remove_sources.items())
                ],
                "groups": {
                    "install": [
                        {"name": group, "from": sorted(sources)}
                        for group, sources in sorted(group_install_sources.items())
                    ],
                    "remove": [
                        {"name": group, "from": sorted(sources)}
                        for group, sources in sorted(group_remove_sources.items())
                    ],
                },
            },
        }

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

        if self.context.enable_zfs:
            self.lines.append(f"ARG ENABLE_ZFS={str(self.context.enable_zfs).lower()}")

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
            elif module_type == "chezmoi":
                self._process_chezmoi_module(module)
            elif module_type == "git-clone":
                self._process_git_clone_module(module)
            else:
                self.lines.append(f"# WARNING: Unknown module type: {module_type}")

            self.lines.append("")
