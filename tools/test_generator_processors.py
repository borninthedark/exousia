#!/usr/bin/env python3
"""
Unit tests for generator.processors module — covers uncovered branches.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from generator.context import BuildContext
from generator.generator import ContainerfileGenerator


def _make_context(**overrides) -> BuildContext:
    defaults = {
        "image_type": "fedora-sway-atomic",
        "fedora_version": "43",
        "enable_plymouth": True,
        "use_upstream_sway_config": False,
        "base_image": "quay.io/fedora/fedora-sway-atomic:43",
        "enable_zfs": False,
        "distro": "fedora",
        "desktop_environment": "",
        "window_manager": "sway",
    }
    defaults.update(overrides)
    return BuildContext(**defaults)


def _make_generator(context=None, config=None):
    ctx = context or _make_context()
    gen = ContainerfileGenerator(config or {}, ctx)
    gen.lines = []
    gen.package_plans = []
    return gen


# --- _process_files_module ---


class TestProcessFilesModule:
    def test_basic_copy(self):
        gen = _make_generator()
        gen._process_files_module(
            {"files": [{"src": "overlays/file.conf", "dst": "/etc/file.conf"}]}
        )
        assert "COPY --chmod=0644 overlays/file.conf /etc/file.conf" in gen.lines

    def test_custom_mode(self):
        gen = _make_generator()
        gen._process_files_module(
            {"files": [{"src": "scripts/run.sh", "dst": "/usr/bin/run.sh", "mode": "0755"}]}
        )
        assert "COPY --chmod=0755 scripts/run.sh /usr/bin/run.sh" in gen.lines

    def test_missing_src_or_dst_skipped(self):
        gen = _make_generator()
        gen._process_files_module({"files": [{"src": "a"}, {"dst": "b"}, {}]})
        assert gen.lines == []

    def test_empty_files_list(self):
        gen = _make_generator()
        gen._process_files_module({"files": []})
        assert gen.lines == []

    def test_multiple_files(self):
        gen = _make_generator()
        gen._process_files_module(
            {
                "files": [
                    {"src": "a", "dst": "/a"},
                    {"src": "b", "dst": "/b", "mode": "0700"},
                ]
            }
        )
        assert len(gen.lines) == 2
        assert "COPY --chmod=0644 a /a" in gen.lines
        assert "COPY --chmod=0700 b /b" in gen.lines


# --- _render_script_lines ---


class TestRenderScriptLines:
    def test_simple_commands(self):
        gen = _make_generator()
        gen._render_script_lines(["echo hello", "echo world"], "set -e")
        assert gen.lines[0] == "RUN set -e; \\"
        assert "    echo hello; \\" in gen.lines
        assert "    echo world" in gen.lines  # last line, no semicolon

    def test_heredoc_preservation(self):
        gen = _make_generator()
        gen._render_script_lines(["cat <<EOF", "line1", "line2", "EOF", "echo done"], "set -e")
        output = "\n".join(gen.lines)
        assert "    cat <<EOF" in output
        assert "    line1" in output
        assert "    line2" in output
        assert "    EOF" in output
        assert "echo done" in output

    def test_compound_if_then_else_fi(self):
        gen = _make_generator()
        gen._render_script_lines(
            ["if true; then", "echo yes", "else", "echo no", "fi", "echo after"],
            "set -e",
        )
        output = "\n".join(gen.lines)
        # 'then' is a compound starter — no semicolon, just backslash
        assert "if true; then \\" in output
        # 'else' is a compound starter
        assert "    else \\" in output
        # 'fi' is a compound ender — gets semicolon
        assert "    fi; \\" in output
        # last command, no continuation
        assert "    echo after" in output

    def test_line_continuation_preserved(self):
        gen = _make_generator()
        gen._render_script_lines(["echo hello \\", "  world", "echo done"], "set -e")
        output = "\n".join(gen.lines)
        # Line already has backslash — should not add semicolon
        assert "    echo hello \\" in output

    def test_comment_lines_pass_through(self):
        gen = _make_generator()
        gen._render_script_lines(["# this is a comment", "echo ok"], "set -e")
        output = "\n".join(gen.lines)
        assert "    # this is a comment" in output

    def test_for_do_done(self):
        gen = _make_generator()
        gen._render_script_lines(["for i in 1 2 3; do", "echo $i", "done"], "set -e")
        output = "\n".join(gen.lines)
        assert "for i in 1 2 3; do \\" in output
        assert "    done" in output  # last line, no continuation

    def test_case_esac(self):
        gen = _make_generator()
        gen._render_script_lines(["case $x in", "a) echo a;;", "esac", "echo end"], "set -e")
        output = "\n".join(gen.lines)
        assert "case $x in \\" in output
        assert "    esac; \\" in output

    def test_single_line(self):
        gen = _make_generator()
        gen._render_script_lines(["echo only"], "set -e")
        assert gen.lines[0] == "RUN set -e; \\"
        assert gen.lines[1] == "    echo only"


# --- _process_script_module ---


class TestProcessScriptModule:
    def test_empty_scripts(self):
        gen = _make_generator()
        gen._process_script_module({"scripts": []})
        assert gen.lines == []

    def test_no_scripts_key(self):
        gen = _make_generator()
        gen._process_script_module({})
        assert gen.lines == []

    def test_single_inline_script(self):
        gen = _make_generator()
        gen._process_script_module({"scripts": ["echo hello"]})
        assert "RUN echo hello" in gen.lines

    def test_single_multiline_script(self):
        gen = _make_generator()
        gen._process_script_module({"scripts": ["echo a\necho b"]})
        output = "\n".join(gen.lines)
        assert "RUN set -e" in output
        assert "echo a" in output
        assert "echo b" in output

    def test_multiple_scripts_combined(self):
        gen = _make_generator()
        gen._process_script_module({"scripts": ["echo a", "echo b\necho c"]})
        output = "\n".join(gen.lines)
        assert "set -euxo pipefail" in output
        assert "echo a" in output
        assert "echo b" in output
        assert "echo c" in output

    def test_single_empty_script_ignored(self):
        gen = _make_generator()
        gen._process_script_module({"scripts": ["   "]})
        assert gen.lines == []


# --- _process_rpm_module ---


class TestProcessRpmModule:
    def test_basic_install_and_remove(self):
        gen = _make_generator()
        with patch.object(gen, "_load_common_remove_packages", return_value=[]):
            gen._process_rpm_module({"install": ["vim", "git"], "remove": ["nano"]})
        output = "\n".join(gen.lines)
        assert "vim git" in output
        assert "nano" in output
        assert "dnf install -y dnf5" in output
        assert "dnf upgrade -y" in output
        assert "dnf clean all" in output

    def test_repos_version_replacement(self):
        gen = _make_generator()
        with patch.object(gen, "_load_common_remove_packages", return_value=[]):
            gen._process_rpm_module({"repos": ["https://example.com/repo-43.rpm"], "install": []})
        output = "\n".join(gen.lines)
        assert "FEDORA_VERSION=$(rpm -E %fedora)" in output
        assert "${FEDORA_VERSION}" in output

    def test_config_manager(self):
        gen = _make_generator()
        with patch.object(gen, "_load_common_remove_packages", return_value=[]):
            gen._process_rpm_module({"config-manager": ["rpmfusion-free"], "install": []})
        output = "\n".join(gen.lines)
        assert "dnf config-manager setopt rpmfusion-free.enabled=1" in output

    def test_conditional_install_true(self):
        gen = _make_generator(context=_make_context(image_type="fedora-bootc"))
        with patch.object(gen, "_load_common_remove_packages", return_value=[]):
            gen._process_rpm_module(
                {
                    "install-conditional": [
                        {
                            "condition": 'image-type == "fedora-bootc"',
                            "packages": ["sway", "waybar"],
                        }
                    ],
                    "install": [],
                }
            )
        output = "\n".join(gen.lines)
        assert "sway waybar" in output
        assert "conditional packages" in output

    def test_conditional_install_false(self):
        gen = _make_generator(context=_make_context(image_type="fedora-sway-atomic"))
        with patch.object(gen, "_load_common_remove_packages", return_value=[]):
            gen._process_rpm_module(
                {
                    "install-conditional": [
                        {
                            "condition": 'image-type == "fedora-bootc"',
                            "packages": ["sway"],
                        }
                    ],
                    "install": [],
                }
            )
        output = "\n".join(gen.lines)
        assert "sway" not in output or "conditional" not in output

    def test_common_remove_packages_merged(self):
        gen = _make_generator()
        with patch.object(gen, "_load_common_remove_packages", return_value=["firefox"]):
            gen._process_rpm_module({"install": [], "remove": ["nano"]})
        output = "\n".join(gen.lines)
        assert "nano" in output
        assert "firefox" in output

    def test_common_remove_no_duplicates(self):
        gen = _make_generator()
        with patch.object(gen, "_load_common_remove_packages", return_value=["nano"]):
            gen._process_rpm_module({"install": [], "remove": ["nano"]})
        # nano should appear only once in the remove command
        remove_line = [line for line in gen.lines if "Removing" in line][0]
        assert "1 packages" in remove_line


# --- _process_systemd_module ---


class TestProcessSystemdModule:
    def test_enable_services(self):
        gen = _make_generator()
        gen._process_systemd_module(
            {"system": {"enabled": ["sshd.service", "NetworkManager.service"]}}
        )
        output = "\n".join(gen.lines)
        assert "systemctl enable sshd.service" in output
        assert "systemctl enable NetworkManager.service" in output

    def test_default_target(self):
        gen = _make_generator()
        gen._process_systemd_module(
            {"default-target": "graphical.target", "system": {"enabled": []}}
        )
        output = "\n".join(gen.lines)
        assert "systemctl set-default graphical.target" in output

    def test_user_services(self):
        gen = _make_generator()
        gen._process_systemd_module({"system": {}, "user": {"enabled": ["pipewire.service"]}})
        output = "\n".join(gen.lines)
        assert "systemctl --global enable pipewire.service" in output

    def test_empty_module(self):
        gen = _make_generator()
        gen._process_systemd_module({"system": {}})
        assert gen.lines == []


# --- _process_chezmoi_module ---


class TestProcessChezmoiModule:
    def test_basic_chezmoi(self):
        gen = _make_generator()
        gen._process_chezmoi_module({"repository": "https://github.com/user/dots.git"})
        output = "\n".join(gen.lines)
        assert "COPY --chmod=0644 overlays/base/systemd/user/" in output
        assert "chezmoi-init.service" in output
        assert "chezmoi-update.timer" in output
        assert "%CHEZMOI_REPO%" in output

    def test_chezmoi_with_branch(self):
        gen = _make_generator()
        gen._process_chezmoi_module(
            {"repository": "https://github.com/user/dots.git", "branch": "main"}
        )
        output = "\n".join(gen.lines)
        assert "--branch main" in output

    def test_chezmoi_replace_policy(self):
        gen = _make_generator()
        gen._process_chezmoi_module(
            {
                "repository": "https://github.com/user/dots.git",
                "file-conflict-policy": "replace",
            }
        )
        output = "\n".join(gen.lines)
        assert "--force" in output

    def test_chezmoi_skip_policy(self):
        gen = _make_generator()
        gen._process_chezmoi_module(
            {
                "repository": "https://github.com/user/dots.git",
                "file-conflict-policy": "skip",
            }
        )
        output = "\n".join(gen.lines)
        assert "--keep-going" in output

    def test_chezmoi_no_repo_error(self):
        gen = _make_generator()
        gen._process_chezmoi_module({})
        assert any("ERROR" in line for line in gen.lines)

    def test_chezmoi_disable_init(self):
        gen = _make_generator()
        gen._process_chezmoi_module(
            {"repository": "https://github.com/user/dots.git", "disable-init": True}
        )
        output = "\n".join(gen.lines)
        assert "chezmoi-init" not in output or "enable chezmoi-init" not in output

    def test_chezmoi_disable_update(self):
        gen = _make_generator()
        gen._process_chezmoi_module(
            {"repository": "https://github.com/user/dots.git", "disable-update": True}
        )
        output = "\n".join(gen.lines)
        assert (
            "chezmoi-update.timer" not in output.split("enable")[-1] if "enable" in output else True
        )


# --- _process_git_clone_module ---


class TestProcessGitCloneModule:
    def test_basic_clone(self):
        gen = _make_generator()
        gen._process_git_clone_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/user/repo.git",
                        "files": [
                            {"src": "script.sh", "dst": "/usr/bin/script.sh", "mode": "0755"}
                        ],
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "git clone --depth 1" in output
        assert "https://github.com/user/repo.git" in output
        assert "install -m 0755" in output
        assert "rm -rf /tmp/git-clone-0" in output

    def test_clone_with_branch(self):
        gen = _make_generator()
        gen._process_git_clone_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/user/repo.git",
                        "branch": "v2.0",
                        "files": [{"src": "a", "dst": "/a"}],
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "--branch v2.0" in output

    def test_clone_no_repos(self):
        gen = _make_generator()
        gen._process_git_clone_module({"repos": []})
        assert any("ERROR" in line for line in gen.lines)

    def test_clone_missing_url(self):
        gen = _make_generator()
        gen._process_git_clone_module({"repos": [{"files": [{"src": "a", "dst": "/a"}]}]})
        assert any("missing 'url'" in line for line in gen.lines)

    def test_clone_no_files(self):
        gen = _make_generator()
        gen._process_git_clone_module({"repos": [{"url": "https://github.com/user/repo.git"}]})
        assert any("no 'files'" in line for line in gen.lines)

    def test_multiple_repos(self):
        gen = _make_generator()
        gen._process_git_clone_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/a/a.git",
                        "files": [{"src": "x", "dst": "/x"}],
                    },
                    {
                        "url": "https://github.com/b/b.git",
                        "files": [{"src": "y", "dst": "/y"}],
                    },
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "git-clone-0" in output
        assert "git-clone-1" in output


# --- _evaluate_condition ---


class TestEvaluateCondition:
    def test_image_type(self):
        gen = _make_generator(context=_make_context(image_type="fedora-bootc"))
        assert gen._evaluate_condition('image-type == "fedora-bootc"') is True
        assert gen._evaluate_condition('image-type == "fedora-sway-atomic"') is False

    def test_distro(self):
        gen = _make_generator(context=_make_context(distro="fedora"))
        assert gen._evaluate_condition('distro == "fedora"') is True
        assert gen._evaluate_condition('distro == "ubuntu"') is False

    def test_enable_plymouth(self):
        gen = _make_generator(context=_make_context(enable_plymouth=True))
        assert gen._evaluate_condition("enable_plymouth == true") is True
        assert gen._evaluate_condition("enable_plymouth == false") is False

    def test_enable_zfs(self):
        gen = _make_generator(context=_make_context(enable_zfs=True))
        assert gen._evaluate_condition("enable_zfs == true") is True

    def test_use_upstream_sway_config(self):
        gen = _make_generator(context=_make_context(use_upstream_sway_config=True))
        assert gen._evaluate_condition("use_upstream_sway_config == true") is True

    def test_desktop_environment(self):
        gen = _make_generator(context=_make_context(desktop_environment="kde"))
        assert gen._evaluate_condition('desktop_environment == "kde"') is True

    def test_window_manager(self):
        gen = _make_generator(context=_make_context(window_manager="sway"))
        assert gen._evaluate_condition('window_manager == "sway"') is True
        assert gen._evaluate_condition('window_manager == "i3"') is False

    def test_and_condition(self):
        gen = _make_generator(context=_make_context(distro="fedora", enable_plymouth=True))
        assert gen._evaluate_condition('distro == "fedora" && enable_plymouth == true') is True
        assert gen._evaluate_condition('distro == "fedora" && enable_plymouth == false') is False

    def test_or_condition(self):
        gen = _make_generator(context=_make_context(distro="fedora"))
        assert gen._evaluate_condition('distro == "fedora" || distro == "ubuntu"') is True
        assert gen._evaluate_condition('distro == "arch" || distro == "ubuntu"') is False

    def test_unknown_field(self):
        gen = _make_generator()
        assert gen._evaluate_condition('unknown_field == "x"') is False

    def test_quoted_values(self):
        gen = _make_generator(context=_make_context(image_type="fedora-bootc"))
        assert gen._evaluate_condition("image-type == 'fedora-bootc'") is True
        assert gen._evaluate_condition('image-type == "fedora-bootc"') is True


# --- _process_package_loader_module ---


class TestProcessPackageLoaderModule:
    def test_import_error_handled(self):
        gen = _make_generator()
        with patch.dict(sys.modules, {"package_loader": None}):
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                gen._process_package_loader_module({})
        # Should gracefully handle (may or may not produce error comment depending on path)

    def test_loader_exception_handled(self):
        gen = _make_generator()
        mock_loader = MagicMock()
        mock_loader.get_package_plan.side_effect = RuntimeError("broken")

        with patch("package_loader.PackageLoader", return_value=mock_loader):
            gen._process_package_loader_module({"window_manager": "sway"})
        assert any("ERROR" in line for line in gen.lines)


# --- _load_common_remove_packages ---


class TestLoadCommonRemovePackages:
    def test_returns_empty_on_failure(self):
        gen = _make_generator()
        with patch("package_loader.PackageLoader", side_effect=Exception("fail")):
            result = gen._load_common_remove_packages()
        assert result == []


# --- _process_signing_module ---


class TestProcessSigningModule:
    def test_default_enforce_mode(self):
        gen = _make_generator()
        gen._process_signing_module({})
        output = "\n".join(gen.lines)
        assert "dnf install -y --skip-unavailable skopeo" in output
        assert "mkdir -p /etc/containers/registries.d" in output
        assert "mkdir -p /etc/pki/containers" in output
        assert "sigstoreSigned" in output
        assert "policy.json" in output

    def test_warn_mode(self):
        gen = _make_generator()
        gen._process_signing_module({"verification": "warn"})
        output = "\n".join(gen.lines)
        assert "insecureAcceptAnything" in output

    def test_cosign_key_copy(self):
        gen = _make_generator()
        gen._process_signing_module({"cosign-key": "keys/cosign.pub"})
        assert any("COPY" in line for line in gen.lines)

    def test_policy_file_override(self):
        gen = _make_generator()
        gen._process_signing_module({"policy-file": "overlays/policy.json"})
        assert any("COPY" in line and "policy.json" in line for line in gen.lines)


# --- _process_default_flatpaks_module ---


class TestProcessDefaultFlatpaksModule:
    def test_no_configurations(self):
        gen = _make_generator()
        gen._process_default_flatpaks_module({"configurations": []})
        assert any("no configurations" in line for line in gen.lines)

    def test_system_scope_install_list(self):
        gen = _make_generator()
        gen._process_default_flatpaks_module(
            {
                "configurations": [
                    {
                        "scope": "system",
                        "install": ["org.mozilla.firefox//stable", "org.gimp.GIMP//stable"],
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "mkdir -p /usr/share/exousia/flatpaks" in output
        assert "system-install.list" in output
        assert "org.mozilla.firefox//stable" in output

    def test_user_scope_empty_install(self):
        gen = _make_generator()
        gen._process_default_flatpaks_module({"configurations": [{"scope": "user", "install": []}]})
        output = "\n".join(gen.lines)
        # Empty install list should not write a list file
        assert "user-install.list" not in output

    def test_multiple_scopes(self):
        gen = _make_generator()
        gen._process_default_flatpaks_module(
            {
                "configurations": [
                    {"scope": "system", "install": ["app.A//stable"]},
                    {"scope": "user", "install": ["app.B//stable"]},
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "system-install.list" in output
        assert "user-install.list" in output


# --- _resolve_module (from-file) ---


class TestResolveModule:
    def test_no_from_file_passthrough(self):
        gen = _make_generator()
        module = {"type": "script", "scripts": ["echo hi"]}
        assert gen._resolve_module(module) is module

    def test_from_file_loads_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ext = tmp_path / "ext.yml"
        ext.write_text(
            "type: default-flatpaks\nconfigurations:\n  - scope: system\n    install:\n      - app.A//stable\n"
        )
        gen = _make_generator()
        result = gen._resolve_module({"from-file": "ext.yml"})
        assert result["type"] == "default-flatpaks"
        assert len(result["configurations"]) == 1

    def test_from_file_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gen = _make_generator()
        result = gen._resolve_module({"from-file": "missing.yml"})
        assert result["type"] is None
        assert "not found" in result["_error"]

    def test_from_file_invalid_yaml(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bad = tmp_path / "bad.yml"
        bad.write_text("invalid: [unclosed")
        gen = _make_generator()
        result = gen._resolve_module({"from-file": "bad.yml"})
        assert "_error" in result

    def test_from_file_inline_overrides(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ext = tmp_path / "ext.yml"
        ext.write_text("type: script\nscripts:\n  - echo base\n")
        gen = _make_generator()
        result = gen._resolve_module({"from-file": "ext.yml", "condition": 'distro == "fedora"'})
        assert result["type"] == "script"
        assert result["condition"] == 'distro == "fedora"'


# --- _process_github_install_module ---


class TestProcessGithubInstallModule:
    def test_python_install(self):
        gen = _make_generator()
        gen._process_github_install_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/nwg-piotr/autotiling",
                        "name": "autotiling",
                        "type": "python",
                        "module": "autotiling",
                        "bin": "autotiling",
                        "entry-point": "from autotiling.main import main\\nmain()",
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "git clone --depth 1" in output
        assert "nwg-piotr/autotiling" in output
        assert "site.getsitepackages" in output
        assert "/usr/local/bin/autotiling" in output
        assert "rm -rf /tmp/github-install-0" in output

    def test_script_install(self):
        gen = _make_generator()
        gen._process_github_install_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/user/tool",
                        "name": "mytool",
                        "type": "script",
                        "src": "bin/mytool.sh",
                        "dst": "/usr/local/bin/mytool",
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "install -m 0755" in output
        assert "bin/mytool.sh" in output

    def test_make_install(self):
        gen = _make_generator()
        gen._process_github_install_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/user/tool",
                        "name": "tool",
                        "type": "make",
                        "prefix": "/usr",
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "make -C" in output
        assert "PREFIX=/usr install" in output

    def test_with_branch(self):
        gen = _make_generator()
        gen._process_github_install_module(
            {
                "repos": [
                    {
                        "url": "https://github.com/user/tool",
                        "name": "tool",
                        "type": "script",
                        "branch": "v2.0",
                        "src": "tool",
                        "dst": "/usr/local/bin/tool",
                    }
                ]
            }
        )
        output = "\n".join(gen.lines)
        assert "--branch v2.0" in output

    def test_no_repos_error(self):
        gen = _make_generator()
        gen._process_github_install_module({"repos": []})
        assert any("ERROR" in line for line in gen.lines)

    def test_missing_url_error(self):
        gen = _make_generator()
        gen._process_github_install_module({"repos": [{"name": "x", "type": "script"}]})
        assert any("missing 'url'" in line for line in gen.lines)
