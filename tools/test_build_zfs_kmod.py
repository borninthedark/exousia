#!/usr/bin/env python3
"""
Unit tests for build-zfs-kmod script
=====================================

Tests the ZFS kernel module build script located at
overlays/base/tools/build-zfs-kmod. Since the script has no .py extension,
we import it via importlib.
"""

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import build-zfs-kmod as a module (no .py extension, needs explicit loader)
_script_path = str(Path(__file__).parent.parent / "overlays" / "base" / "tools" / "build-zfs-kmod")
_loader = importlib.machinery.SourceFileLoader("build_zfs_kmod", _script_path)
_spec = importlib.util.spec_from_loader("build_zfs_kmod", _loader)
assert _spec is not None, "Failed to create module spec for build-zfs-kmod"
assert _spec.loader is not None, "Module spec has no loader"
build_zfs_kmod: types.ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_zfs_kmod)
sys.modules["build_zfs_kmod"] = build_zfs_kmod


def _make_path_mock(match_path: str | None = None) -> MagicMock:
    """Create a MagicMock that simulates Path with / operator and str()."""
    instances: dict[str, MagicMock] = {}

    def factory(p: str) -> MagicMock:
        if p not in instances:
            m = MagicMock(
                **{
                    "__truediv__": MagicMock(side_effect=lambda other: factory(f"{p}/{other}")),
                    "__str__": MagicMock(return_value=p),
                },
            )
            m.exists.return_value = p == match_path if match_path else False
            instances[p] = m
        return instances[p]

    return MagicMock(side_effect=factory)


class TestDetectKernelVersion:
    """Tests for detect_kernel_version()."""

    @patch("build_zfs_kmod.Path")
    def test_returns_latest_kernel(self, mock_path_cls: MagicMock) -> None:
        """Should return the highest version directory name."""
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        mock_path_cls.return_value = mock_dir

        subdirs = []
        for name in ["6.12.1-200.fc41.x86_64", "6.12.5-200.fc41.x86_64", "6.11.0-100.fc41.x86_64"]:
            d = MagicMock()
            d.name = name
            d.is_dir.return_value = True
            subdirs.append(d)

        mock_dir.iterdir.return_value = subdirs

        result = build_zfs_kmod.detect_kernel_version()
        assert result == "6.12.5-200.fc41.x86_64"

    @patch("build_zfs_kmod.Path")
    def test_dies_when_no_modules_dir(self, mock_path_cls: MagicMock) -> None:
        """Should exit when /usr/lib/modules does not exist."""
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = False
        mock_path_cls.return_value = mock_dir

        with pytest.raises(SystemExit):
            build_zfs_kmod.detect_kernel_version()

    @patch("build_zfs_kmod.Path")
    def test_dies_when_no_kernel_dirs(self, mock_path_cls: MagicMock) -> None:
        """Should exit when modules dir exists but has no subdirectories."""
        mock_dir = MagicMock()
        mock_dir.is_dir.return_value = True
        mock_dir.iterdir.return_value = []
        mock_path_cls.return_value = mock_dir

        with pytest.raises(SystemExit):
            build_zfs_kmod.detect_kernel_version()


class TestVerifyKernelHeaders:
    """Tests for verify_kernel_headers()."""

    @patch("build_zfs_kmod.Path")
    def test_passes_when_build_dir_exists(self, mock_path_cls: MagicMock) -> None:
        """Should not raise when build dir exists."""
        instances: dict[str, MagicMock] = {}

        def path_side_effect(p: str) -> MagicMock:
            if p not in instances:
                m = MagicMock()
                m.exists.return_value = "/build" in p
                instances[p] = m
            return instances[p]

        mock_path_cls.side_effect = path_side_effect
        build_zfs_kmod.verify_kernel_headers("6.12.5-200.fc41.x86_64")

    @patch("build_zfs_kmod.Path")
    def test_dies_when_no_headers(self, mock_path_cls: MagicMock) -> None:
        """Should exit when neither build nor src dir exists."""
        mock_instance = MagicMock()
        mock_instance.exists.return_value = False
        mock_path_cls.return_value = mock_instance

        with pytest.raises(SystemExit):
            build_zfs_kmod.verify_kernel_headers("6.12.5-200.fc41.x86_64")


class TestAddZfsRepo:
    """Tests for add_zfs_repo()."""

    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.subprocess.run")
    def test_skips_when_already_installed(
        self, mock_subprocess_run: MagicMock, mock_run: MagicMock
    ) -> None:
        """Should skip repo install when zfs-release is already present."""
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        build_zfs_kmod.add_zfs_repo()
        mock_run.assert_not_called()

    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.subprocess.run")
    def test_installs_repo_rpm(self, mock_subprocess_run: MagicMock, mock_run: MagicMock) -> None:
        """Should install the ZFS repo RPM when not present."""
        check_result = MagicMock(returncode=1)
        dist_result = MagicMock(returncode=0, stdout=".fc41\n")

        mock_subprocess_run.side_effect = [check_result, dist_result]

        build_zfs_kmod.add_zfs_repo()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "dnf"
        assert "zfsonlinux.org" in args[-1]
        assert ".fc41" in args[-1]


class TestBuildModules:
    """Tests for build_modules()."""

    @patch("build_zfs_kmod.run")
    def test_calls_dkms_autoinstall(self, mock_run: MagicMock) -> None:
        """Should call dkms autoinstall with the correct kernel version."""
        kver = "6.12.5-200.fc41.x86_64"
        build_zfs_kmod.build_modules(kver)
        mock_run.assert_called_once_with(["dkms", "autoinstall", "-k", kver])


class TestFindZfsModule:
    """Tests for find_zfs_module()."""

    @patch("build_zfs_kmod.Path")
    def test_finds_ko_in_extra_zfs(self, mock_path_cls: MagicMock) -> None:
        """Should find zfs.ko in extra/zfs directory."""
        kver = "6.12.5-200.fc41.x86_64"
        target = f"/usr/lib/modules/{kver}/extra/zfs/zfs.ko"
        mock_path_cls.side_effect = _make_path_mock(target).side_effect

        result = build_zfs_kmod.find_zfs_module(kver)
        assert result is not None
        assert "zfs.ko" in result

    @patch("build_zfs_kmod.Path")
    def test_finds_compressed_module(self, mock_path_cls: MagicMock) -> None:
        """Should find zfs.ko.zst (compressed) when .ko is missing."""
        kver = "6.12.5-200.fc41.x86_64"
        target = f"/usr/lib/modules/{kver}/extra/zfs/zfs.ko.zst"
        mock_path_cls.side_effect = _make_path_mock(target).side_effect

        result = build_zfs_kmod.find_zfs_module(kver)
        assert result is not None
        assert "zfs.ko.zst" in result

    @patch("build_zfs_kmod.Path")
    def test_returns_none_when_not_found(self, mock_path_cls: MagicMock) -> None:
        """Should return None when no module file exists."""
        kver = "6.12.5-200.fc41.x86_64"
        mock_path_cls.side_effect = _make_path_mock(None).side_effect

        result = build_zfs_kmod.find_zfs_module(kver)
        assert result is None


class TestCleanupBuildDeps:
    """Tests for cleanup_build_deps()."""

    @patch("build_zfs_kmod.subprocess.run")
    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.Path")
    def test_removes_build_deps(
        self, mock_path_cls: MagicMock, mock_run: MagicMock, mock_subprocess_run: MagicMock
    ) -> None:
        """Should call dnf remove with build dependency list."""
        mock_dkms = MagicMock()
        mock_dkms.exists.return_value = False
        mock_path_cls.return_value = mock_dkms

        build_zfs_kmod.cleanup_build_deps()

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[:3] == ["dnf", "remove", "-y"]
        assert "gcc" in args
        assert "make" in args


class TestCleanupCaches:
    """Tests for cleanup_caches()."""

    @patch("build_zfs_kmod.subprocess.run")
    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.Path")
    def test_cleans_dnf_caches(
        self, mock_path_cls: MagicMock, mock_run: MagicMock, mock_subprocess_run: MagicMock
    ) -> None:
        """Should call dnf clean all."""
        mock_instance = MagicMock()
        mock_instance.exists.return_value = False
        mock_path_cls.return_value = mock_instance

        build_zfs_kmod.cleanup_caches()

        mock_run.assert_called_once_with(["dnf", "clean", "all"], check=False)


class TestMain:
    """Tests for the main() entry point."""

    @patch("build_zfs_kmod.cleanup_caches")
    @patch("build_zfs_kmod.cleanup_build_deps")
    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.find_zfs_module")
    @patch("build_zfs_kmod.build_modules")
    @patch("build_zfs_kmod.install_zfs")
    @patch("build_zfs_kmod.add_zfs_repo")
    @patch("build_zfs_kmod.verify_kernel_headers")
    @patch("build_zfs_kmod.detect_kernel_version")
    def test_full_pipeline(
        self,
        mock_detect: MagicMock,
        mock_verify: MagicMock,
        mock_add_repo: MagicMock,
        mock_install: MagicMock,
        mock_build: MagicMock,
        mock_find: MagicMock,
        mock_run: MagicMock,
        mock_cleanup_deps: MagicMock,
        mock_cleanup_caches: MagicMock,
    ) -> None:
        """Should execute the full build pipeline in order."""
        mock_detect.return_value = "6.12.5-200.fc41.x86_64"
        mock_find.return_value = "/usr/lib/modules/6.12.5-200.fc41.x86_64/extra/zfs/zfs.ko"

        with patch("sys.argv", ["build-zfs-kmod"]), patch.dict("os.environ", {}, clear=False):
            result = build_zfs_kmod.main()

        assert result == 0
        mock_detect.assert_called_once()
        mock_verify.assert_called_once_with("6.12.5-200.fc41.x86_64")
        mock_add_repo.assert_called_once()
        mock_install.assert_called_once()
        mock_build.assert_called_once_with("6.12.5-200.fc41.x86_64")
        mock_find.assert_called_once()
        mock_run.assert_called_once_with(["depmod", "-a", "6.12.5-200.fc41.x86_64"])
        mock_cleanup_deps.assert_called_once()
        mock_cleanup_caches.assert_called_once()

    @patch("build_zfs_kmod.cleanup_caches")
    @patch("build_zfs_kmod.cleanup_build_deps")
    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.find_zfs_module")
    @patch("build_zfs_kmod.build_modules")
    @patch("build_zfs_kmod.install_zfs")
    @patch("build_zfs_kmod.add_zfs_repo")
    @patch("build_zfs_kmod.verify_kernel_headers")
    @patch("build_zfs_kmod.detect_kernel_version")
    def test_keep_build_deps_flag(
        self,
        mock_detect: MagicMock,
        mock_verify: MagicMock,
        mock_add_repo: MagicMock,
        mock_install: MagicMock,
        mock_build: MagicMock,
        mock_find: MagicMock,
        mock_run: MagicMock,
        mock_cleanup_deps: MagicMock,
        mock_cleanup_caches: MagicMock,
    ) -> None:
        """Should skip cleanup when --keep-build-deps is set."""
        mock_detect.return_value = "6.12.5-200.fc41.x86_64"
        mock_find.return_value = "/usr/lib/modules/6.12.5-200.fc41.x86_64/extra/zfs/zfs.ko"

        with (
            patch("sys.argv", ["build-zfs-kmod", "--keep-build-deps"]),
            patch.dict("os.environ", {}, clear=False),
        ):
            result = build_zfs_kmod.main()

        assert result == 0
        mock_cleanup_deps.assert_not_called()
        mock_cleanup_caches.assert_called_once()

    @patch("build_zfs_kmod.show_build_log")
    @patch("build_zfs_kmod.find_zfs_module")
    @patch("build_zfs_kmod.build_modules")
    @patch("build_zfs_kmod.install_zfs")
    @patch("build_zfs_kmod.add_zfs_repo")
    @patch("build_zfs_kmod.verify_kernel_headers")
    @patch("build_zfs_kmod.detect_kernel_version")
    def test_dies_when_module_not_found(
        self,
        mock_detect: MagicMock,
        mock_verify: MagicMock,
        mock_add_repo: MagicMock,
        mock_install: MagicMock,
        mock_build: MagicMock,
        mock_find: MagicMock,
        mock_show_log: MagicMock,
    ) -> None:
        """Should exit with error when ZFS module is not found after build."""
        mock_detect.return_value = "6.12.5-200.fc41.x86_64"
        mock_find.return_value = None

        with patch("sys.argv", ["build-zfs-kmod"]), patch.dict("os.environ", {}, clear=False):
            with pytest.raises(SystemExit):
                build_zfs_kmod.main()

        mock_show_log.assert_called_once()

    @patch("build_zfs_kmod.cleanup_caches")
    @patch("build_zfs_kmod.cleanup_build_deps")
    @patch("build_zfs_kmod.run")
    @patch("build_zfs_kmod.find_zfs_module")
    @patch("build_zfs_kmod.build_modules")
    @patch("build_zfs_kmod.install_zfs")
    @patch("build_zfs_kmod.add_zfs_repo")
    @patch("build_zfs_kmod.verify_kernel_headers")
    def test_uses_kver_env_variable(
        self,
        mock_verify: MagicMock,
        mock_add_repo: MagicMock,
        mock_install: MagicMock,
        mock_build: MagicMock,
        mock_find: MagicMock,
        mock_run: MagicMock,
        mock_cleanup_deps: MagicMock,
        mock_cleanup_caches: MagicMock,
    ) -> None:
        """Should use KVER env variable when set instead of auto-detecting."""
        mock_find.return_value = "/usr/lib/modules/6.99.0/extra/zfs/zfs.ko"

        with (
            patch("sys.argv", ["build-zfs-kmod"]),
            patch.dict("os.environ", {"KVER": "6.99.0-custom"}, clear=False),
        ):
            result = build_zfs_kmod.main()

        assert result == 0
        mock_verify.assert_called_once_with("6.99.0-custom")
        mock_build.assert_called_once_with("6.99.0-custom")


class TestBuildDeps:
    """Tests for the BUILD_DEPS constant."""

    def test_build_deps_is_list(self) -> None:
        """BUILD_DEPS should be a non-empty list of strings."""
        assert isinstance(build_zfs_kmod.BUILD_DEPS, list)
        assert len(build_zfs_kmod.BUILD_DEPS) > 0
        assert all(isinstance(dep, str) for dep in build_zfs_kmod.BUILD_DEPS)

    def test_build_deps_contains_compiler(self) -> None:
        """BUILD_DEPS should include gcc and make."""
        assert "gcc" in build_zfs_kmod.BUILD_DEPS
        assert "make" in build_zfs_kmod.BUILD_DEPS
