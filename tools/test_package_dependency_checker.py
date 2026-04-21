import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from package_dependency_checker import (
    DependencyCheckResult,
    FedoraDnfChecker,
    PackageDependency,
    PackageDependencyTranspiler,
    main,
)

# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


class TestPackageDependency:
    def test_defaults(self):
        pd = PackageDependency(name="vim")
        assert pd.name == "vim"
        assert pd.version is None
        assert pd.dependencies == []
        assert pd.provides == []
        assert pd.installed is False
        assert pd.distro == ""

    def test_with_values(self):
        pd = PackageDependency(
            name="sway",
            version="1.9",
            dependencies=["wlroots"],
            provides=["window-manager"],
            installed=True,
            distro="fedora",
        )
        assert pd.installed is True
        assert pd.dependencies == ["wlroots"]


class TestDependencyCheckResult:
    def test_defaults(self):
        r = DependencyCheckResult(package="vim", found=True, installed=True)
        assert r.dependencies == []
        assert r.missing_deps == []
        assert r.errors == []
        assert r.distro == ""


# ---------------------------------------------------------------------------
# FedoraDnfChecker (mocked subprocess)
# ---------------------------------------------------------------------------


class TestFedoraDnfChecker:
    def _checker(self):
        return FedoraDnfChecker()

    def test_distro_name(self):
        assert self._checker().distro_name == "fedora"

    def test_is_available_true(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (0, "/usr/bin/dnf", ""))
        assert checker.is_available() is True

    def test_is_available_false(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (1, "", "not found"))
        assert checker.is_available() is False

    def test_is_installed_true(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (0, "vim-9.0", ""))
        assert checker.is_installed("vim") is True

    def test_is_installed_false(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (1, "", "not installed"))
        assert checker.is_installed("vim") is False

    def test_get_dependencies_success(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(
            checker,
            "run_command",
            lambda cmd: (0, "wlroots\nwayland-protocols\nrpmlib(foo)\n/usr/bin/sh\n", ""),
        )
        deps = checker.get_dependencies("sway")
        assert "wlroots" in deps
        assert "wayland-protocols" in deps
        # rpmlib and path deps should be filtered
        assert not any(d.startswith("rpmlib(") for d in deps)
        assert not any(d.startswith("/") for d in deps)

    def test_get_dependencies_failure(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (1, "", "error"))
        assert checker.get_dependencies("missing") == []

    def test_get_package_info_not_found(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "run_command", lambda cmd: (1, "", "no match"))
        assert checker.get_package_info("nosuchpkg") is None

    def test_get_package_info_success(self, monkeypatch):
        checker = self._checker()
        responses = [
            (0, "vim|9.0|vim-common vim-filesystem", ""),  # repoquery info
            (0, "glibc\n", ""),  # get_dependencies
            (0, "vim-9.0-1.fc43", ""),  # is_installed (rpm -q)
        ]

        def mock_run(cmd):
            return responses.pop(0)

        monkeypatch.setattr(checker, "run_command", mock_run)
        info = checker.get_package_info("vim")
        assert info is not None
        assert info.name == "vim"
        assert info.version == "9.0"
        assert info.installed is True

    def test_check_dependencies_installed_not_found(self, monkeypatch):
        checker = self._checker()
        monkeypatch.setattr(checker, "get_package_info", lambda pkg: None)
        result = checker.check_dependencies_installed("missing")
        assert result.found is False
        assert len(result.errors) == 1

    def test_check_dependencies_installed_with_deps(self, monkeypatch):
        checker = self._checker()
        pkg = PackageDependency(
            name="sway",
            version="1.9",
            dependencies=["wlroots", "missing"],
            installed=True,
            distro="fedora",
        )
        dep_ok = PackageDependency(name="wlroots", installed=True, distro="fedora")

        def mock_info(name):
            if name == "sway":
                return pkg
            if name == "wlroots":
                return dep_ok
            return None

        monkeypatch.setattr(checker, "get_package_info", mock_info)
        result = checker.check_dependencies_installed("sway")
        assert result.found is True
        assert "missing" in result.missing_deps

    def test_run_command_timeout(self, monkeypatch):
        import subprocess

        checker = self._checker()
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *a, **kw: (_ for _ in ()).throw(
                subprocess.TimeoutExpired(cmd="test", timeout=30)
            ),
        )
        rc, out, err = checker.run_command(["sleep", "999"])
        assert rc == -1
        assert "timed out" in err.lower()


# ---------------------------------------------------------------------------
# PackageDependencyTranspiler
# ---------------------------------------------------------------------------


class TestTranspiler:
    def test_explicit_fedora(self):
        t = PackageDependencyTranspiler(distro="fedora")
        assert t.get_current_distro() == "fedora"

    def test_unknown_distro_raises(self):
        with pytest.raises(ValueError, match="Unknown distro"):
            PackageDependencyTranspiler(distro="gentoo")

    def test_check_packages(self):
        mock_checker = MagicMock()
        t = PackageDependencyTranspiler(checker=mock_checker)
        mock_result = DependencyCheckResult(
            package="vim",
            found=True,
            installed=True,
            distro="fedora",
        )
        mock_checker.check_dependencies_installed.return_value = mock_result
        results = t.check_packages(["vim"])
        assert "vim" in results
        assert results["vim"].found is True

    def test_verify_all_installed(self):
        mock_checker = MagicMock()
        t = PackageDependencyTranspiler(checker=mock_checker)
        mock_checker.is_installed.return_value = True
        ok, missing = t.verify_installation(["a", "b"])
        assert ok is True
        assert missing == []

    def test_verify_some_missing(self):
        mock_checker = MagicMock()
        t = PackageDependencyTranspiler(checker=mock_checker)
        mock_checker.is_installed.side_effect = lambda pkg: pkg != "b"
        ok, missing = t.verify_installation(["a", "b"])
        assert ok is False
        assert missing == ["b"]

    def test_detect_distro_fedora(self, monkeypatch):
        monkeypatch.setattr(
            "builtins.open",
            lambda *a, **kw: StringIO("ID=fedora\nVERSION_ID=43\n"),
        )
        t = PackageDependencyTranspiler()
        assert t.get_current_distro() == "fedora"


# ---------------------------------------------------------------------------
# CLI tests (main)
# ---------------------------------------------------------------------------


class TestPackageDependencyCheckerCLI:
    def test_detect_distro_failure(self, monkeypatch):
        """Test _detect_distro when no supported manager is found."""
        monkeypatch.setattr(
            "builtins.open", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError())
        )

        with patch("package_dependency_checker.FedoraDnfChecker") as mock_fedora:
            mock_fedora.return_value.is_available.return_value = False
            with pytest.raises(RuntimeError, match="No supported package manager found"):
                PackageDependencyTranspiler()

    def test_main_verify_only_success(self, capsys):
        """Test main() with --verify-only and all packages installed."""
        transpiler_mock = MagicMock()
        transpiler_mock.verify_installation.return_value = (True, [])
        transpiler_mock.get_current_distro.return_value = "fedora"

        with patch(
            "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
        ):
            rc = main(argv=["--verify-only", "--distro", "fedora", "pkg1"])
            assert rc == 0
            assert "All packages installed" in capsys.readouterr().out

    def test_main_verify_only_failure(self, capsys):
        """Test main() with --verify-only and missing packages."""
        transpiler_mock = MagicMock()
        transpiler_mock.verify_installation.return_value = (False, ["pkg1"])
        transpiler_mock.get_current_distro.return_value = "fedora"

        with patch(
            "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
        ):
            rc = main(argv=["--verify-only", "pkg1"])
            assert rc == 1
            assert "Missing packages" in capsys.readouterr().out

    def test_main_json_output(self, capsys):
        """Test main() with --json output."""
        result = DependencyCheckResult("pkg1", found=True, installed=True, distro="fedora")
        dep = PackageDependency("dep1", installed=True, version="1.0")
        result.dependencies = [dep]

        transpiler_mock = MagicMock()
        transpiler_mock.check_packages.return_value = {"pkg1": result}

        with patch(
            "package_dependency_checker.PackageDependencyTranspiler", return_value=transpiler_mock
        ):
            rc = main(argv=["--json", "pkg1"])
            assert rc == 0
            output = json.loads(capsys.readouterr().out)
            assert "pkg1" in output
            assert output["pkg1"]["found"] is True

    def test_main_error_handling(self, capsys):
        """Test main() exception handling."""
        with patch(
            "package_dependency_checker.PackageDependencyTranspiler",
            side_effect=Exception("Test Error"),
        ):
            rc = main(argv=["pkg1"])
            assert rc == 1
            assert "Error: Test Error" in capsys.readouterr().err
