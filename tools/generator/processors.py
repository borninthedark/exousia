import sys
from pathlib import Path
from typing import Any, Protocol


class BuildContextLike(Protocol):
    """Typed subset of build context used by the processing mixin."""

    image_type: str
    distro: str
    base_image: str
    enable_plymouth: bool
    enable_zfs: bool
    use_upstream_sway_config: bool
    desktop_environment: str
    window_manager: str
    fedora_version: str


class ModuleProcessorsMixin:
    """Mixin containing module processing logic for ContainerfileGenerator."""

    lines: list[str]
    context: BuildContextLike
    package_plans: list[dict[str, Any]]

    def _load_common_remove_packages(self) -> list[str]:
        """Load the shared removal list from packages/common/remove.yml."""
        try:
            # Root directory of tools
            tools_dir = Path(__file__).parent.parent
            if str(tools_dir) not in sys.path:
                sys.path.insert(0, str(tools_dir))

            from package_loader import PackageLoader

            loader = PackageLoader()
            return list(loader.load_remove())
        except Exception:
            return []

    def _process_files_module(self, module: dict[str, Any]):
        """Process files module (COPY instructions)."""
        files = module.get("files", [])

        for file_spec in files:
            src = file_spec.get("src")
            dst = file_spec.get("dst")
            mode = file_spec.get("mode", "0644")

            if src and dst:
                # Handle directory copies (trailing /)
                self.lines.append(f"COPY --chmod={mode} {src} {dst}")

    def _render_script_lines(self, lines: list[str], set_command: str):
        """Render a sequence of shell lines as a single RUN instruction."""

        # Keywords that start or are in the middle of compound statements (no semicolon needed)
        COMPOUND_STARTERS = {"if", "then", "else", "elif", "do", "case", "for", "while", "in"}
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
                repo_url = repo.replace(self.context.fedora_version, "${FEDORA_VERSION}")
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
        # Root directory of tools
        tools_dir = Path(__file__).parent.parent
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))

        try:
            from package_loader import PackageLoader
        except ImportError:
            self.lines.append("# ERROR: package_loader module not found")
            return

        loader = PackageLoader()

        wm = module.get("window_manager")
        de = module.get("desktop_environment")
        common_bundles = module.get("common_bundles")
        feature_bundles = module.get("feature_bundles")
        include_common = module.get("include_common", True) if common_bundles is None else False
        extras = module.get("extras", []) if feature_bundles is None else None

        # Load packages
        try:
            package_plan = loader.get_package_plan(
                wm=wm,
                de=de,
                include_common=include_common,
                extras=extras,
                common_bundles=common_bundles,
                feature_bundles=feature_bundles,
            )
        except Exception as e:
            self.lines.append(f"# ERROR loading packages: {e}")
            return

        self.package_plans.append(package_plan)

        install_packages = [item["name"] for item in package_plan["rpm"]["install"]]
        remove_packages = [item["name"] for item in package_plan["rpm"]["remove"]]
        group_installs = [item["name"] for item in package_plan["rpm"]["groups"].get("install", [])]
        group_removals = [item["name"] for item in package_plan["rpm"]["groups"].get("remove", [])]

        # RPM overrides: COPY RPMs from OCI images before the main install
        rpm_overrides = loader.load_rpm_overrides()
        override_packages = set()
        for idx, override in enumerate(rpm_overrides):
            image = override["image"]
            stage = f"rpm-override-{idx}"
            self.lines.append(f"# RPM override: {override.get('reason', image)}")
            self.lines.append(f"COPY --from={image} /rpms/ /tmp/{stage}/")
            override_packages.add(stage)

        # Filter version-constrained packages from dnf install (handled by overrides)
        if override_packages:
            install_packages = [pkg for pkg in install_packages if not any(c in pkg for c in "><=")]

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
        if group_removals and self.context.distro == "fedora":
            for group in group_removals:
                self.lines.append(f"    dnf group remove -y '{group}' || true; \\")

        if group_installs and self.context.distro == "fedora":
            for group in group_installs:
                self.lines.append(f"    dnf group install -y '{group}'; \\")

        # Remove conflicting packages FIRST
        if remove_packages:
            packages_str = " ".join(remove_packages)
            self.lines.append(f"    dnf remove -y {packages_str} || true; \\")

        # Install individual packages
        if install_packages:
            exclude_flags = ""
            if remove_packages:
                exclude_flags = " ".join(f"--exclude={pkg}" for pkg in remove_packages) + " "

            chunk_size = 50
            chunks = [
                install_packages[i : i + chunk_size]
                for i in range(0, len(install_packages), chunk_size)
            ]

            for _i, chunk in enumerate(chunks):
                packages_str = " ".join(
                    f"'{pkg}'" if any(c in pkg for c in "><=") else pkg for pkg in chunk
                )
                self.lines.append(
                    f"    dnf install -y --skip-unavailable {exclude_flags}{packages_str}; \\"
                )

        # Install RPM overrides
        for idx in range(len(rpm_overrides)):
            stage = f"rpm-override-{idx}"
            self.lines.append(f"    dnf install -y /tmp/{stage}/*.rpm && rm -rf /tmp/{stage}; \\")

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
        user = module.get("user", {})
        user_enabled = user.get("enabled", [])
        for service in user_enabled:
            commands.append(f"systemctl --global enable {service}")
        if commands:
            self.lines.append("RUN " + " && \\\n    ".join(commands))

    def _process_chezmoi_module(self, module: dict[str, Any]):
        """Process chezmoi module."""
        repository = module.get("repository", "")
        branch = module.get("branch", "")
        all_users = module.get("all-users", True)
        conflict_policy = module.get("file-conflict-policy", "skip")
        run_every = module.get("run-every", "1d")
        wait_after_boot = module.get("wait-after-boot", "5m")
        disable_init = module.get("disable-init", False)
        disable_update = module.get("disable-update", False)

        if not repository and not disable_init:
            self.lines.append("# ERROR: chezmoi module requires 'repository' when init is enabled")
            return

        self.lines.append("COPY --chmod=0644 overlays/base/systemd/user/ /usr/lib/systemd/user/")
        repo_arg = repository
        if branch:
            repo_arg = f"{repository} --branch {branch}"
        update_args = "--force" if conflict_policy == "replace" else "--keep-going"

        sed_commands = [
            f"sed -i 's|%CHEZMOI_REPO%|{repo_arg}|g' /usr/lib/systemd/user/chezmoi-init.service",
            f"sed -i 's|%CHEZMOI_REPO%|{repository}|g' /usr/lib/systemd/user/chezmoi-update.service",
            f"sed -i 's|%CHEZMOI_UPDATE_ARGS%|{update_args}|g' /usr/lib/systemd/user/chezmoi-update.service",
            f"sed -i 's|%CHEZMOI_WAIT_AFTER_BOOT%|{wait_after_boot}|g' /usr/lib/systemd/user/chezmoi-update.timer",
            f"sed -i 's|%CHEZMOI_RUN_EVERY%|{run_every}|g' /usr/lib/systemd/user/chezmoi-update.timer",
        ]
        self._render_script_lines(sed_commands, "set -euxo pipefail")

        if all_users:
            enable_commands = []
            if not disable_init:
                enable_commands.append("systemctl --global enable chezmoi-init.service")
            if not disable_update:
                enable_commands.append("systemctl --global enable chezmoi-update.timer")
            if enable_commands:
                self.lines.append("RUN " + " && \\\n    ".join(enable_commands))

    def _process_git_clone_module(self, module: dict[str, Any]):
        """Process git-clone module."""
        repos = module.get("repos", [])
        if not repos:
            self.lines.append("# ERROR: git-clone module has no repos defined")
            return
        commands: list[str] = []
        for idx, repo in enumerate(repos):
            url = repo.get("url")
            if not url:
                self.lines.append(f"# ERROR: git-clone repo entry {idx} missing 'url'")
                continue
            files = repo.get("files", [])
            if not files:
                self.lines.append(f"# ERROR: git-clone repo {url} has no 'files' defined")
                continue
            clone_dir = f"/tmp/git-clone-{idx}"  # nosec B108
            branch = repo.get("branch")
            clone_cmd = "git clone --depth 1"
            if branch:
                clone_cmd += f" --branch {branch}"
            clone_cmd += f" {url} {clone_dir}"
            commands.append(clone_cmd)
            for file_spec in files:
                src, dst = file_spec.get("src", ""), file_spec.get("dst", "")
                mode = file_spec.get("mode", "0644")
                if src and dst:
                    commands.append(f"install -m {mode} {clone_dir}/{src} {dst}")
            commands.append(f"rm -rf {clone_dir}")
        if commands:
            self._render_script_lines(commands, "set -euxo pipefail")

    def _process_github_install_module(self, module: dict[str, Any]):
        """Process github-install module (install packages from GitHub repos).

        Supports Python packages and standalone scripts from GitHub repositories.
        Clones the repo at build time, installs the package, and cleans up.
        """
        repos = module.get("repos", [])
        if not repos:
            self.lines.append("# ERROR: github-install module has no repos defined")
            return

        commands: list[str] = []
        for idx, repo in enumerate(repos):
            url = repo.get("url")
            if not url:
                self.lines.append(f"# ERROR: github-install repo entry {idx} missing 'url'")
                continue

            branch = repo.get("branch")
            install_type = repo.get("type", "python")
            name = repo.get("name", f"github-pkg-{idx}")
            bin_name = repo.get("bin", name)
            clone_dir = f"/tmp/github-install-{idx}"  # nosec B108

            # Clone
            clone_cmd = "git clone --depth 1"
            if branch:
                clone_cmd += f" --branch {branch}"
            clone_cmd += f" {url} {clone_dir}"
            commands.append(clone_cmd)

            if install_type == "python":
                # Install Python package: copy module + create entry point
                module_name = repo.get("module", name.replace("-", "_"))
                entry_point = module.get(
                    "entry-point", f"from {module_name}.main import main\\nmain()"
                )
                site_pkg = '$(python3 -c "import site; print(site.getsitepackages()[0])")'
                commands.append(f"mkdir -p {site_pkg}")
                commands.append(
                    f"cp -r {clone_dir}/{module_name} " f'"{site_pkg}"' f"/{module_name}"
                )
                commands.append(
                    f"printf '#!/usr/bin/python3\\n{entry_point}\\n' > /usr/local/bin/{bin_name}"
                )
                commands.append(f"chmod 0755 /usr/local/bin/{bin_name}")
            elif install_type == "script":
                # Install standalone script(s)
                src = repo.get("src", bin_name)
                dst = repo.get("dst", f"/usr/local/bin/{bin_name}")
                commands.append(f"install -m 0755 {clone_dir}/{src} {dst}")
            elif install_type == "make":
                # Run make install
                prefix = repo.get("prefix", "/usr/local")
                commands.append(f"make -C {clone_dir} PREFIX={prefix} install")

            commands.append(f"rm -rf {clone_dir}")

        if commands:
            self._render_script_lines(commands, "set -euxo pipefail")

    def _process_signing_module(self, module: dict[str, Any]):
        """Process signing module (image signature verification policy).

        Configures the built image to verify container signatures using
        cosign/sigstore. This embeds the public key and policy so the
        running system can verify its own image provenance.
        """
        cosign_key = module.get("cosign-key")
        policy_file = module.get("policy-file")
        verification_mode = module.get("verification", "enforce")

        commands: list[str] = []

        # Install signing verification tools
        commands.append("dnf install -y --skip-unavailable skopeo")
        commands.append("dnf clean all")

        # Set up containers policy directory
        commands.append("mkdir -p /etc/containers/registries.d")
        commands.append("mkdir -p /etc/pki/containers")

        if cosign_key:
            # Copy the cosign public key into the image
            self.lines.append(f"COPY --chmod=0644 {cosign_key} /etc/pki/containers/cosign.pub")

        # Configure signature verification policy
        if verification_mode == "enforce":
            policy_content = (
                '{"default":[{"type":"reject"}],'
                '"transports":{"docker":{"ghcr.io/borninthedark":'
                '[{"type":"sigstoreSigned","keyPath":"/etc/pki/containers/cosign.pub"}]}}}'
            )
        else:
            # warn mode — accept all but log
            policy_content = '{"default":[{"type":"insecureAcceptAnything"}]}'

        commands.append(f"echo '{policy_content}' > /etc/containers/policy.json")

        if policy_file:
            # Override with user-provided policy
            self.lines.append(f"COPY --chmod=0644 {policy_file} /etc/containers/policy.json")

        if commands:
            self._render_script_lines(commands, "set -euxo pipefail")

    def _process_default_flatpaks_module(self, module: dict[str, Any]):
        """Process default-flatpaks module (first-boot flatpak installation).

        Generates a systemd service and flatpak list that installs configured
        flatpak applications on first boot.
        """
        configurations = module.get("configurations", [])
        if not configurations:
            self.lines.append("# default-flatpaks: no configurations defined")
            return

        # Generate flatpak install lists for each scope
        commands: list[str] = []
        commands.append("mkdir -p /usr/share/exousia/flatpaks")

        for config in configurations:
            scope = config.get("scope", "system")
            install_list = config.get("install", [])

            if install_list:
                # Write the flatpak list file
                list_content = "\\n".join(install_list)
                commands.append(
                    f"printf '%b\\n' '{list_content}' > /usr/share/exousia/flatpaks/{scope}-install.list"
                )

        if commands:
            self._render_script_lines(commands, "set -euxo pipefail")

    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition string against current context."""
        condition = condition.strip()
        if " && " in condition:
            parts = condition.split(" && ")
            return all(self._evaluate_condition(part.strip()) for part in parts)
        if " || " in condition:
            parts = condition.split(" || ")
            return any(self._evaluate_condition(part.strip()) for part in parts)
        if "==" in condition:
            left, right = [x.strip() for x in condition.split("==", 1)]
            right = right.strip("\"'")
            if left == "image-type":
                return self.context.image_type == right
            if left == "distro":
                return self.context.distro == right
            if left == "enable_plymouth":
                return self.context.enable_plymouth == (right.lower() == "true")
            if left == "enable_zfs":
                return self.context.enable_zfs == (right.lower() == "true")
            if left == "use_upstream_sway_config":
                return self.context.use_upstream_sway_config == (right.lower() == "true")
            if left == "desktop_environment":
                return self.context.desktop_environment == right
            if left == "window_manager":
                return self.context.window_manager == right
        return False
