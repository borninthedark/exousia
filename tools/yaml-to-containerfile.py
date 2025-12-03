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
from typing import Any, Dict, List

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
    bootc_build_deps: List[str]


# Fedora Atomic Desktop variants
FEDORA_ATOMIC_VARIANTS = {
    "fedora-silverblue": "quay.io/fedora/fedora-silverblue",
    "fedora-kinoite": "quay.io/fedora/fedora-kinoite",
    "fedora-sway-atomic": "quay.io/fedora/fedora-sway-atomic",
    "fedora-onyx": "quay.io/fedora-ostree-desktops/onyx",
    "fedora-budgie": "quay.io/fedora-ostree-desktops/budgie",
    "fedora-cinnamon": "quay.io/fedora-ostree-desktops/cinnamon",
    "fedora-cosmic": "quay.io/fedora-ostree-desktops/cosmic",
    "fedora-deepin": "quay.io/fedora-ostree-desktops/deepin",
    "fedora-lxqt": "quay.io/fedora-ostree-desktops/lxqt",
    "fedora-mate": "quay.io/fedora-ostree-desktops/mate",
    "fedora-xfce": "quay.io/fedora-ostree-desktops/xfce",
}

# Distro configurations for Linux bootc images (formerly called bootcrew)
LINUX_BOOTC_DISTROS = {
    "arch": DistroConfig(
        name="arch",
        base_image_template="docker.io/archlinux/archlinux:latest",
        package_manager="pacman",
        update_command="pacman -Sy",
        install_command="pacman -S --noconfirm",
        clean_command="pacman -S --clean --noconfirm",
        build_deps_install="pacman -S --noconfirm",
        build_deps_remove="pacman -Rns --noconfirm",
        bootc_build_deps=["make", "git", "rust"],
    ),
    "gentoo": DistroConfig(
        name="gentoo",
        base_image_template="docker.io/gentoo/stage3:latest",
        package_manager="emerge",
        update_command="emerge --sync --quiet",
        install_command="emerge --verbose",
        clean_command="rm -rf /var/db",
        build_deps_install="emerge --verbose",
        build_deps_remove="",  # Gentoo doesn't remove build deps in single-stage build
        bootc_build_deps=[],  # Build deps installed with system deps in Gentoo
    ),
    "debian": DistroConfig(
        name="debian",
        base_image_template="debian:unstable",
        package_manager="apt",
        update_command="apt update -y",
        install_command="apt install -y",
        clean_command="rm -rf /var/lib/apt/lists/* && apt clean -y",
        build_deps_install="apt install -y",
        build_deps_remove="apt purge -y",
        bootc_build_deps=["libzstd-dev", "libssl-dev", "pkg-config", "curl", "git", "build-essential", "meson", "libfuse3-dev", "go-md2man", "dracut"],
    ),
    "ubuntu": DistroConfig(
        name="ubuntu",
        base_image_template="ubuntu:mantic",
        package_manager="apt",
        update_command="apt update -y",
        install_command="apt install -y",
        clean_command="rm -rf /var/lib/apt/lists/* && apt clean -y",
        build_deps_install="apt install -y",
        build_deps_remove="apt purge -y",
        bootc_build_deps=["libzstd-dev", "libssl-dev", "pkg-config", "curl", "git", "build-essential", "meson", "libfuse3-dev", "go-md2man", "dracut"],
    ),
    "opensuse": DistroConfig(
        name="opensuse",
        base_image_template="registry.opensuse.org/opensuse/tumbleweed:latest",
        package_manager="zypper",
        update_command="zypper refresh",
        install_command="zypper install -y",
        clean_command="zypper clean -a",
        build_deps_install="zypper install -y",
        build_deps_remove="zypper remove -y",
        bootc_build_deps=["git", "rust", "make", "cargo", "gcc-devel", "glib2-devel", "libzstd-devel", "openssl-devel", "ostree-devel"],
    ),
    "proxmox": DistroConfig(
        name="proxmox",
        base_image_template="debian:unstable",
        package_manager="apt",
        update_command="apt-get update",
        install_command="apt-get install -y --no-install-recommends",
        clean_command="apt-get clean && rm -rf /var/lib/apt/lists/*",
        build_deps_install="apt-get install -y --no-install-recommends",
        build_deps_remove="apt-get purge -y",
        bootc_build_deps=["git", "cargo", "rustc", "make", "gcc", "pkg-config", "libssl-dev"],
    ),
}


@dataclass
class BuildContext:
    """Build context for evaluating conditions and generating Containerfile."""
    image_type: str
    fedora_version: str  # For Fedora-based images; can be empty for Linux bootc
    enable_plymouth: bool
    base_image: str
    distro: str = "fedora"  # fedora, arch, gentoo, debian, ubuntu, opensuse, proxmox


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
        self._add_shell()
        self._add_labels()
        self._add_environment()
        self._process_modules()
        return "\n".join(self.lines)

    def _load_common_remove_packages(self) -> List[str]:
        """Load the shared removal list from packages/common/remove.yml."""
        try:
            from package_loader import PackageLoader

            loader = PackageLoader()
            return loader.load_remove()
        except Exception:
            return []

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

    def _add_shell(self):
        """Ensure RUN commands use bash so pipefail is available."""
        self.lines.extend([
            "# Use bash for RUN instructions",
            'SHELL ["/bin/bash", "-o", "pipefail", "-c"]',
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
            self.lines.append(f"ENV ENABLE_PLYMOUTH={plymouth_val}")
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
            elif module_type == "package-loader":
                self._process_package_loader_module(module)
            elif module_type == "systemd":
                self._process_systemd_module(module)
            elif module_type == "bootcrew-setup":
                self._process_bootcrew_setup_module(module)
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

    def _render_script_lines(self, lines: List[str], set_command: str):
        """Render a sequence of shell lines as a single RUN instruction."""

        SHELL_KEYWORDS = {'if', 'then', 'else', 'elif', 'fi', 'do', 'done', 'case', 'esac'}

        self.lines.append(f"RUN {set_command}; \\")

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

    def _process_script_module(self, module: Dict[str, Any]):
        """Process script module (RUN instructions)."""
        scripts = module.get("scripts", [])

        if not scripts:
            return

        def collect_lines(script_block: str) -> List[str]:
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
            lines: List[str] = []
            for script in scripts:
                if "\n" in script:
                    lines.extend(collect_lines(script))
                else:
                    stripped = script.strip()
                    if stripped:
                        lines.append(stripped)

            if lines:
                self._render_script_lines(lines, "set -euxo pipefail")

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
                    pkg_list = " ".join(packages)
                    self.lines.append(
                        f'    echo "==> Installing {len(packages)} conditional packages..."; \\'
                    )
                    self.lines.append(
                        f'    dnf install -y --skip-unavailable {pkg_list}; \\'
                    )

        # Regular package installation
        install_packages = module.get("install", [])
        if install_packages:
            pkg_list = " ".join(install_packages)
            self.lines.append(
                f'    echo "==> Installing {len(install_packages)} custom packages..."; \\'
            )
            self.lines.append(f'    dnf install -y {pkg_list}; \\')

        # Package removal
        remove_packages = list(dict.fromkeys(module.get("remove", [])))

        # Always honor the shared removal list so common removals are consistent
        for pkg in self._load_common_remove_packages():
            if pkg not in remove_packages:
                remove_packages.append(pkg)

        if remove_packages:
            pkg_list = " ".join(remove_packages)
            self.lines.append(
                f'    echo "==> Removing {len(remove_packages)} packages..."; \\'
            )
            self.lines.append(f'    dnf remove -y {pkg_list}; \\')

        # Upgrade and cleanup
        self.lines.append("    dnf upgrade -y; \\")
        self.lines.append("    dnf clean all")

    def _process_package_loader_module(self, module: Dict[str, Any]):
        """Process package-loader module (new YAML-based package management)."""
        from pathlib import Path
        import sys

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
            self.lines.append("    dnf install -y https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${FEDORA_VERSION}.noarch.rpm; \\")
            self.lines.append("    dnf install -y https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${FEDORA_VERSION}.noarch.rpm; \\")
            self.lines.append("    dnf config-manager setopt fedora-cisco-openh264.enabled=1; \\")

        # Install package groups (for Fedora-based distros)
        # Groups are only supported on Fedora/DNF-based systems
        if groups and self.context.distro == "fedora":
            for group in groups:
                self.lines.append(f"    dnf install -y @{group}; \\")

        # Install individual packages
        if install_packages:
            # Split packages into chunks to avoid command line length issues
            chunk_size = 50
            chunks = [install_packages[i:i + chunk_size] for i in range(0, len(install_packages), chunk_size)]

            for i, chunk in enumerate(chunks):
                packages_str = " ".join(chunk)
                if i == len(chunks) - 1 and not remove_packages:
                    # Last chunk, no remove packages
                    self.lines.append(f"    dnf install -y --skip-unavailable {packages_str}; \\")
                else:
                    self.lines.append(f"    dnf install -y --skip-unavailable {packages_str}; \\")

        # Remove packages
        if remove_packages:
            packages_str = " ".join(remove_packages)
            self.lines.append(f"    dnf remove -y {packages_str} || true; \\")

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

    def _process_bootcrew_setup_module(self, module: Dict[str, Any]):
        """Process bootcrew-setup module (build bootc from source and configure for bootcrew distros)."""
        if self.context.distro not in LINUX_BOOTC_DISTROS:
            self.lines.append(f"# WARNING: bootcrew-setup not applicable for {self.context.distro}")
            return

        distro = self.context.distro

        # Call distro-specific implementation
        if distro == "arch":
            self._process_bootcrew_arch(module)
        elif distro in ["debian", "ubuntu"]:
            self._process_bootcrew_debian(module)
        elif distro == "gentoo":
            self._process_bootcrew_gentoo(module)
        elif distro == "opensuse":
            self._process_bootcrew_opensuse(module)
        elif distro == "proxmox":
            self._process_bootcrew_debian(module)  # Proxmox uses Debian-based setup
        else:
            self.lines.append(f"# WARNING: No bootcrew-setup implementation for {distro}")

    def _process_bootcrew_arch(self, module: Dict[str, Any]):
        """Arch Linux bootc setup following bootcrew/arch-bootc pattern."""
        # Step 1: Move /var to /usr/lib/sysimage for pacman compatibility
        self.lines.append("# Move everything from `/var` to `/usr/lib/sysimage` so behavior around pacman remains the same on `bootc usroverlay`'d systems")
        self.lines.append('RUN grep "= */var" /etc/pacman.conf | sed "/= *\\/var/s/.*=// ; s/ //" | xargs -n1 sh -c \'mkdir -p "/usr/lib/sysimage/$(dirname $(echo $1 | sed "s@/var/@@"))" && mv -v "$1" "/usr/lib/sysimage/$(echo "$1" | sed "s@/var/@@")"\' \'\' && \\')
        self.lines.append('    sed -i -e "/= *\\/var/ s/^#//" -e "s@= */var@= /usr/lib/sysimage@g" -e "/DownloadUser/d" /etc/pacman.conf')
        self.lines.append("")

        # Step 2: Install system dependencies
        deps = module.get("system-deps", [])
        if deps:
            self.lines.append("# Install system dependencies")
            deps_str = " ".join(deps)
            self.lines.append(f"RUN pacman -Sy --noconfirm {deps_str} && pacman -S --clean --noconfirm")
            self.lines.append("")

        # Step 3: Build bootc from source (with tmpfs mounts)
        self.lines.append("# https://github.com/bootc-dev/bootc/issues/1801")
        self.lines.append("RUN --mount=type=tmpfs,dst=/tmp --mount=type=tmpfs,dst=/root \\")
        self.lines.append("    pacman -S --noconfirm make git rust && \\")
        self.lines.append('    git clone "https://github.com/bootc-dev/bootc.git" /tmp/bootc && \\')
        self.lines.append('    make -C /tmp/bootc bin install-all && \\')
        self.lines.append('    printf "systemdsystemconfdir=/etc/systemd/system\\nsystemdsystemunitdir=/usr/lib/systemd/system\\n" | tee /usr/lib/dracut/dracut.conf.d/30-bootcrew-fix-bootc-module.conf && \\')
        self.lines.append('    printf \'reproducible=yes\\nhostonly=no\\ncompress=zstd\\nadd_dracutmodules+=" ostree bootc "\' | tee "/usr/lib/dracut/dracut.conf.d/30-bootcrew-bootc-container-build.conf" && \\')
        self.lines.append('    dracut --force "$(find /usr/lib/modules -maxdepth 1 -type d | grep -v -E "*.img" | tail -n 1)/initramfs.img" && \\')
        self.lines.append('    pacman -Rns --noconfirm make git rust && \\')
        self.lines.append('    pacman -S --clean --noconfirm')
        self.lines.append("")

        # Step 4: Restructure filesystem for ostree/bootc
        self.lines.append("# Necessary for general behavior expected by image-based systems")
        self.lines.append('RUN sed -i \'s|^HOME=.*|HOME=/var/home|\' "/etc/default/useradd" && \\')
        self.lines.append('    rm -rf /boot /home /root /usr/local /srv /var /usr/lib/sysimage/log /usr/lib/sysimage/cache/pacman/pkg && \\')
        self.lines.append('    mkdir -p /sysroot /boot /usr/lib/ostree /var && \\')
        self.lines.append('    ln -s sysroot/ostree /ostree && ln -s var/roothome /root && ln -s var/srv /srv && ln -s var/opt /opt && ln -s var/mnt /mnt && ln -s var/home /home && \\')
        self.lines.append('    echo "$(for dir in opt home srv mnt usrlocal ; do echo "d /var/$dir 0755 root root -" ; done)" | tee -a "/usr/lib/tmpfiles.d/bootc-base-dirs.conf" && \\')
        self.lines.append('    printf "d /var/roothome 0700 root root -\\nd /run/media 0755 root root -" | tee -a "/usr/lib/tmpfiles.d/bootc-base-dirs.conf" && \\')
        self.lines.append('    printf \'[composefs]\\nenabled = yes\\n[sysroot]\\nreadonly = true\\n\' | tee "/usr/lib/ostree/prepare-root.conf"')
        self.lines.append("")

        # Step 5: Validate
        self.lines.append("RUN bootc container lint")
        self.lines.append("")
        self.lines.append("LABEL containers.bootc 1")

    def _process_bootcrew_debian(self, module: Dict[str, Any]):
        """Debian/Ubuntu bootc setup following bootcrew/debian-bootc pattern."""
        # Step 1: Set DEBIAN_FRONTEND
        self.lines.append("ARG DEBIAN_FRONTEND=noninteractive")
        self.lines.append("")

        # Step 2: Install system dependencies
        deps = module.get("system-deps", [])
        if deps:
            self.lines.append("# Install system dependencies")
            deps_str = " ".join(deps)
            self.lines.append(f"RUN apt update -y && \\")
            self.lines.append(f"    apt install -y {deps_str} && \\")
            self.lines.append("    rm -rf /var/lib/apt/lists/* && \\")
            self.lines.append("    apt clean -y")
            self.lines.append("")

        # Step 3: Fix dracut regression
        self.lines.append("# Regression with newer dracut broke this")
        self.lines.append("RUN mkdir -p /etc/dracut.conf.d && \\")
        self.lines.append('    printf "systemdsystemconfdir=/etc/systemd/system\\nsystemdsystemunitdir=/usr/lib/systemd/system\\n" | tee /etc/dracut.conf.d/fix-bootc.conf')
        self.lines.append("")

        # Step 4: Build bootc from source with Rustup
        self.lines.append("# Build bootc from source with Rustup")
        self.lines.append("ENV CARGO_HOME=/tmp/rust")
        self.lines.append("ENV RUSTUP_HOME=/tmp/rust")
        self.lines.append('ENV DEV_DEPS="libzstd-dev libssl-dev pkg-config curl git build-essential meson libfuse3-dev go-md2man dracut"')
        self.lines.append("RUN --mount=type=tmpfs,dst=/tmp \\")
        self.lines.append("    apt update -y && \\")
        self.lines.append("    apt install -y $DEV_DEPS libostree-dev ostree && \\")
        self.lines.append('    curl --proto \'=https\' --tlsv1.2 -sSf "https://sh.rustup.rs" | sh -s -- --profile minimal -y && \\')
        self.lines.append('    git clone "https://github.com/bootc-dev/bootc.git" /tmp/bootc && \\')
        self.lines.append('    sh -c ". ${RUSTUP_HOME}/env ; make -C /tmp/bootc bin install-all install-initramfs-dracut" && \\')
        self.lines.append('    sh -c \'export KERNEL_VERSION="$(basename "$(find /usr/lib/modules -maxdepth 1 -type d | grep -v -E "*.img" | tail -n 1)")" && dracut --force --no-hostonly --reproducible --zstd --verbose --kver "$KERNEL_VERSION"  "/usr/lib/modules/$KERNEL_VERSION/initramfs.img" && cp /boot/vmlinuz-$KERNEL_VERSION "/usr/lib/modules/$KERNEL_VERSION/vmlinuz"\' && \\')
        self.lines.append("    apt purge -y $DEV_DEPS && \\")
        self.lines.append("    apt autoremove -y && \\")
        self.lines.append("    rm -rf /var/lib/apt/lists/* && \\")
        self.lines.append("    apt clean -y")
        self.lines.append("")

        # Step 5: Restructure filesystem
        self.lines.append("# Necessary for general behavior expected by image-based systems")
        self.lines.append('RUN echo "HOME=/var/home" | tee -a "/etc/default/useradd" && \\')
        self.lines.append('    rm -rf /boot /home /root /usr/local /srv && \\')
        self.lines.append('    mkdir -p /var /sysroot /boot /usr/lib/ostree && \\')
        self.lines.append('    ln -s var/opt /opt && \\')
        self.lines.append('    ln -s var/roothome /root && \\')
        self.lines.append('    ln -s var/home /home && \\')
        self.lines.append('    ln -s sysroot/ostree /ostree && \\')
        self.lines.append('    echo "$(for dir in opt usrlocal home srv mnt ; do echo "d /var/$dir 0755 root root -" ; done)" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /var/roothome 0700 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /run/media 0755 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    printf "[composefs]\\nenabled = yes\\n[sysroot]\\nreadonly = true\\n" | tee "/usr/lib/ostree/prepare-root.conf"')
        self.lines.append("")

        # Step 6: Validate
        self.lines.append("RUN bootc container lint")
        self.lines.append("")
        self.lines.append("LABEL containers.bootc 1")

    def _process_bootcrew_gentoo(self, module: Dict[str, Any]):
        """Gentoo bootc setup following bootcrew/gentoo-bootc pattern."""
        # Step 1: Sync sources and select systemd-based profile
        self.lines.append("# Sync sources and select systemd-based profile")
        self.lines.append("RUN --mount=type=tmpfs,dst=/tmp emerge --sync --quiet && \\")
        self.lines.append('    eselect profile list | grep -E -e "default.*[[:digit:]]/systemd" | grep -v 32  | awk \'{ print $1 }\' | grep -o [[:digit:]] | xargs eselect profile set && \\')
        self.lines.append('    echo -e \'FEATURES="-ipc-sandbox -network-sandbox -pid-sandbox"\\nACCEPT_LICENSE="*"\\nUSE="dracut nftables"\' | tee -a /etc/portage/make.conf && \\')
        self.lines.append('    echo "sys-apps/systemd boot" | tee -a /etc/portage/package.use/systemd && \\')

        # Step 2: Install system dependencies + build bootc
        deps = module.get("system-deps", [])
        if deps:
            deps_str = " ".join(deps)
            self.lines.append(f"    emerge --verbose --deep --newuse @world && \\")
            self.lines.append(f"    emerge --verbose {deps_str} && \\")
        else:
            self.lines.append("    emerge --verbose --deep --newuse @world && \\")
            self.lines.append("    emerge --verbose app-arch/cpio btrfs-progs dev-vcs/git dosfstools linux-firmware rust skopeo sys-kernel/gentoo-kernel-bin systemd && \\")

        # Step 3: Build custom ostree and bootc
        self.lines.append('    git clone https://github.com/EWouters/gentoo gentoo -b ostree --depth 1 --single-branch && \\')
        self.lines.append('    cd gentoo && ebuild --debug dev-util/ostree/ostree-2025.6.ebuild clean install merge && \\')
        self.lines.append('    git clone "https://github.com/bootc-dev/bootc.git" /tmp/bootc && \\')
        self.lines.append('    make -C /tmp/bootc bin install-all install-initramfs-dracut && \\')
        self.lines.append('    rm -rf /var/db')
        self.lines.append("")

        # Step 4: Generate initramfs and copy vmlinuz
        self.lines.append("# Generate initramfs and copy vmlinuz from kernel sources")
        self.lines.append('RUN echo "$(basename "$(find /usr/lib/modules -maxdepth 1 -type d | grep -v -E "*.img" | tail -n 1)")" > kernel_version.txt && \\')
        self.lines.append('    dracut --force --no-hostonly --reproducible --zstd --verbose --kver "$(cat kernel_version.txt)"  "/usr/lib/modules/$(cat kernel_version.txt)/initramfs.img" && \\')
        self.lines.append('    rm "/usr/lib/modules/$(cat kernel_version.txt)/vmlinuz" && \\')
        self.lines.append('    cp -f /usr/src/linux-$(cat kernel_version.txt)/arch/*/boot/bzImage "/usr/lib/modules/$(cat kernel_version.txt)/vmlinuz" && \\')
        self.lines.append('    rm kernel_version.txt')
        self.lines.append("")

        # Step 5: Restructure filesystem
        self.lines.append("# Necessary for general behavior expected by image-based systems")
        self.lines.append('RUN sed -i \'s|^HOME=.*|HOME=/var/home|\' "/etc/default/useradd" && \\')
        self.lines.append('    rm -rf /boot /home /root /usr/local /srv && \\')
        self.lines.append('    mkdir -p /var /sysroot /boot /usr/lib/ostree && \\')
        self.lines.append('    ln -s var/opt /opt && \\')
        self.lines.append('    ln -s var/roothome /root && \\')
        self.lines.append('    ln -s var/home /home && \\')
        self.lines.append('    ln -s sysroot/ostree /ostree && \\')
        self.lines.append('    echo "$(for dir in opt usrlocal home srv mnt ; do echo "d /var/$dir 0755 root root -" ; done)" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /var/roothome 0700 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /run/media 0755 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    printf "[composefs]\\nenabled = yes\\n[sysroot]\\nreadonly = true\\n" | tee "/usr/lib/ostree/prepare-root.conf"')
        self.lines.append("")

        # Step 6: Validate
        self.lines.append("RUN bootc container lint")
        self.lines.append("")
        self.lines.append("LABEL containers.bootc 1")

    def _process_bootcrew_opensuse(self, module: Dict[str, Any]):
        """OpenSUSE Tumbleweed bootc setup following bootcrew/opensuse-bootc pattern."""
        # Step 1: Install system dependencies
        deps = module.get("system-deps", [])
        if deps:
            self.lines.append("# Install system dependencies")
            deps_str = " ".join(deps)
            self.lines.append(f"RUN zypper install -y \\")
            # Format as multi-line for readability
            deps_list = deps_str.split()
            for i, dep in enumerate(deps_list):
                if i < len(deps_list) - 1:
                    self.lines.append(f"      {dep} \\")
                else:
                    self.lines.append(f"      {dep} && \\")
            self.lines.append("    zypper clean -a")
            self.lines.append("")

        # Step 2: Build bootc from source
        self.lines.append("# Build bootc from source")
        self.lines.append('ENV DEV_DEPS="git rust make cargo gcc-devel glib2-devel libzstd-devel openssl-devel ostree-devel"')
        self.lines.append("RUN --mount=type=tmpfs,dst=/tmp --mount=type=tmpfs,dst=/root \\")
        self.lines.append("    zypper install -y ${DEV_DEPS} && \\")
        self.lines.append('    git clone "https://github.com/bootc-dev/bootc.git" /tmp/bootc && \\')
        self.lines.append('    make -C /tmp/bootc bin install-all install-initramfs-dracut && \\')
        self.lines.append('    sh -c \'export KERNEL_VERSION="$(basename "$(find /usr/lib/modules -maxdepth 1 -type d | grep -v -E "*.img" | tail -n 1)")" && \\')
        self.lines.append('    dracut --force --no-hostonly --force-drivers erofs --reproducible --zstd --verbose --kver "$KERNEL_VERSION"  "/usr/lib/modules/$KERNEL_VERSION/initramfs.img"\' && \\')
        self.lines.append("    zypper remove -y ${DEV_DEPS} && \\")
        self.lines.append("    zypper clean -a")
        self.lines.append('ENV DEV_DEPS=""')
        self.lines.append("")

        # Step 3: Restructure filesystem
        self.lines.append("# Necessary for general behavior expected by image-based systems")
        self.lines.append('RUN echo "HOME=/var/home" | tee "/etc/default/useradd" && \\')
        self.lines.append('    rm -rf /boot /home /root /usr/local /srv && \\')
        self.lines.append('    mkdir -p /var /sysroot /boot /usr/lib/ostree && \\')
        self.lines.append('    ln -s var/opt /opt && \\')
        self.lines.append('    ln -s var/roothome /root && \\')
        self.lines.append('    ln -s var/home /home && \\')
        self.lines.append('    ln -s sysroot/ostree /ostree && \\')
        self.lines.append('    echo "$(for dir in opt usrlocal home srv mnt ; do echo "d /var/$dir 0755 root root -" ; done)" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /var/roothome 0700 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    echo "d /run/media 0755 root root -" | tee -a /usr/lib/tmpfiles.d/bootc-base-dirs.conf && \\')
        self.lines.append('    printf "[composefs]\\nenabled = yes\\n[sysroot]\\nreadonly = true\\n" | tee "/usr/lib/ostree/prepare-root.conf"')
        self.lines.append("")

        # Step 4: Necessary labels
        self.lines.append("LABEL containers.bootc 1")

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against current context."""
        # Simple condition evaluation
        # Supports: image-type == "value", enable_plymouth == true/false, distro == "value"

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
            if left == "distro":
                return self.context.distro == right
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

    # The legacy 'bootcrew' alias referred to non-Fedora bootc builds and is
    # now deprecated. Require callers to migrate to linux-bootc so we don't
    # silently fall back to Fedora defaults.
    if image_type == "bootcrew":
        raise ValueError(
            "image-type 'bootcrew' is deprecated; use 'linux-bootc' with an explicit base-image"
        )

    # Linux bootc distros are explicitly supplied FROM images, not a standalone
    # distro family. Require the caller to set base-image when using the
    # linux-bootc alias to avoid silently falling back to Fedora defaults.
    if image_type == "linux-bootc":
        if not preferred_base:
            raise ValueError(
                "image-type 'linux-bootc' requires base-image to reference the desired bootc distro"
            )
        return ensure_version_tag(preferred_base)

    # Linux bootc distros - use distro configs
    if image_type in LINUX_BOOTC_DISTROS:
        return LINUX_BOOTC_DISTROS[image_type].base_image_template

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
  python3 yaml-to-containerfile.py --config adnyeus.yml --output Containerfile.generated

  # Generate for fedora-bootc with Plymouth enabled
  python3 yaml-to-containerfile.py --config adnyeus.yml --image-type fedora-bootc --enable-plymouth --output Containerfile.bootc.generated

  # Validate only
  python3 yaml-to-containerfile.py --config adnyeus.yml --validate
        """
    )

    parser.add_argument("-c", "--config", type=Path, required=True,
                        help="Path to YAML configuration file")
    parser.add_argument("-o", "--output", type=Path,
                        help="Output Containerfile path (default: stdout)")
    # Build the list of all supported image types dynamically
    all_image_types = (
        ["fedora-bootc", "linux-bootc", "bootcrew"] +
        list(FEDORA_ATOMIC_VARIANTS.keys()) +
        list(LINUX_BOOTC_DISTROS.keys())
    )

    parser.add_argument("--image-type", choices=all_image_types,
                        help="Base image type (default: from config)")
    parser.add_argument("--fedora-version", default="43",
                        help="Fedora version (default: 43, ignored for Linux bootc distros)")
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
    try:
        base_image = determine_base_image(config, image_type, fedora_version)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Determine distro based on image_type
    if image_type in LINUX_BOOTC_DISTROS:
        distro = image_type
    elif image_type == "linux-bootc":
        distro = config.get("distro", "linux-bootc")
    elif image_type == "fedora-bootc" or image_type in FEDORA_ATOMIC_VARIANTS:
        distro = "fedora"
    else:
        distro = config.get("distro", "fedora")

    if args.verbose:
        print("Build context:")
        print(f"  Image type: {image_type}")
        print(f"  Distro: {distro}")
        print(f"  Fedora version: {fedora_version}")
        print(f"  Plymouth: {enable_plymouth}")
        print(f"  Base image: {base_image}")

    context = BuildContext(
        image_type=image_type,
        fedora_version=fedora_version,
        enable_plymouth=enable_plymouth,
        base_image=base_image,
        distro=distro
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
