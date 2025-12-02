import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from package_dependency_checker import (
    DependencyCheckResult,
    PackageDependency,
    PackageDependencyTranspiler,
    DebianAptChecker,
    OpenSUSEZypperChecker,
    GentooPortageChecker,
    FreeBSDPkgChecker,
)


def _mock_run_command_factory(responses, commands):
    def _runner(cmd, check=False):
        commands.append(cmd)
        if responses:
            return responses.pop(0)
        raise AssertionError(f"No response configured for command: {cmd}")

    return _runner


def test_debian_get_package_info_parses_dependencies(monkeypatch):
    checker = DebianAptChecker()
    commands = []
    responses = [
        (
            0,
            "\n".join(
                [
                    "Package: hello",
                    "Version: 1.0-1",
                    "Depends: libc6 (>= 2.0), libfoo | libbar",
                    "Provides: hello-bin, hello-app",
                ]
            ),
            "",
        ),
        (0, "install ok installed", ""),
    ]
    monkeypatch.setattr(checker, "run_command", _mock_run_command_factory(responses, commands))

    info = checker.get_package_info("hello")

    assert info.name == "hello"
    assert info.version == "1.0-1"
    assert info.dependencies == ["libc6", "libfoo"]
    assert info.provides == ["hello-bin", "hello-app"]
    assert info.installed is True
    assert commands[0][0] == "apt-cache"


def test_debian_get_dependencies_strips_versions(monkeypatch):
    checker = DebianAptChecker()
    commands = []
    responses = [
        (
            0,
            "\n".join([
                " Depends: libalpha",
                " Depends: libbeta (>= 2.1)",
                " Depends: libgamma | libdelta",
            ]),
            "",
        )
    ]
    monkeypatch.setattr(checker, "run_command", _mock_run_command_factory(responses, commands))

    deps = checker.get_dependencies("hello")

    assert deps == ["libalpha", "libbeta", "libgamma"]
    assert commands[0][0:2] == ["apt-cache", "depends"]


def test_opensuse_get_package_info_filters_rpmlib(monkeypatch):
    checker = OpenSUSEZypperChecker()
    commands = []
    responses = [
        (
            0,
            "\n".join(
                [
                    "Name: hello",
                    "Version: 2.0",
                    "Requires: rpmlib(PayloadIsXz) bash>=5.0 coreutils=9.0",
                ]
            ),
            "",
        ),
        (0, "", ""),
    ]
    monkeypatch.setattr(checker, "run_command", _mock_run_command_factory(responses, commands))

    info = checker.get_package_info("hello")

    assert info.name == "hello"
    assert info.version == "2.0"
    assert "rpmlib(PayloadIsXz)" not in info.dependencies
    assert info.dependencies == ["bash", "coreutils"]
    assert info.distro == "opensuse"


def test_opensuse_check_dependencies_identifies_missing(monkeypatch):
    checker = OpenSUSEZypperChecker()

    def fake_get_package_info(name):
        if name == "hello":
            return PackageDependency(name="hello", dependencies=["bash"], installed=True, distro="opensuse")
        if name == "bash":
            return PackageDependency(name="bash", dependencies=[], installed=False, distro="opensuse")
        return None

    monkeypatch.setattr(checker, "get_package_info", fake_get_package_info)

    result = checker.check_dependencies_installed("hello")

    assert result.found is True
    assert result.installed is True
    assert result.missing_deps == ["bash"]
    assert result.dependencies[0].name == "bash"


def test_gentoo_get_package_info_collects_dependencies(monkeypatch):
    checker = GentooPortageChecker()
    commands = []
    responses = [
        (0, "dev-libs/hello-1.0\n", ""),
        (0, "dev-libs/foo\ndev-util/bar\n", ""),
        (0, "", ""),
    ]
    monkeypatch.setattr(checker, "run_command", _mock_run_command_factory(responses, commands))

    info = checker.get_package_info("hello")

    assert info.name == "dev-libs/hello-1.0"
    assert info.dependencies == ["dev-libs/foo", "dev-util/bar"]
    assert info.installed is True


def test_freebsd_get_package_info_reads_dependencies(monkeypatch):
    checker = FreeBSDPkgChecker()
    commands = []
    responses = [
        (
            0,
            "\n".join(["Name : hello", "Version : 1.0"]),
            "",
        ),
        (
            0,
            "Depends on:\n  depone-1.0\n  deptwo-2.0\n",
            "",
        ),
        (0, "", ""),
    ]
    monkeypatch.setattr(checker, "run_command", _mock_run_command_factory(responses, commands))

    info = checker.get_package_info("hello")

    assert info.name == "hello"
    assert info.dependencies == ["depone", "deptwo"]
    assert info.installed is True
    assert commands[0][0] == "pkg"


def test_transpiler_check_packages_uses_checker(monkeypatch):
    transpiler = PackageDependencyTranspiler(distro="debian")
    mock_result = DependencyCheckResult(
        package="hello",
        found=True,
        installed=True,
        dependencies=[],
        distro="debian",
    )
    monkeypatch.setattr(transpiler.checker, "check_dependencies_installed", lambda pkg: mock_result)

    results = transpiler.check_packages(["hello"])

    assert "hello" in results
    assert results["hello"].distro == "debian"


def test_transpiler_verify_installation_reports_missing(monkeypatch):
    transpiler = PackageDependencyTranspiler(distro="debian")
    monkeypatch.setattr(transpiler.checker, "is_installed", lambda pkg: pkg == "present")

    all_installed, missing = transpiler.verify_installation(["present", "absent"])

    assert all_installed is False
    assert missing == ["absent"]


def test_transpiler_unknown_distro_raises():
    with pytest.raises(ValueError):
        PackageDependencyTranspiler(distro="unknown")
