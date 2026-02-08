import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from package_dependency_checker import DependencyCheckResult, PackageDependencyTranspiler


def _mock_run_command_factory(
    responses: list[tuple[int, str, str]], commands: list[list[str]]
) -> object:
    def _runner(cmd: list[str], check: bool = False) -> tuple[int, str, str]:
        commands.append(cmd)
        if responses:
            return responses.pop(0)
        raise AssertionError(f"No response configured for command: {cmd}")

    return _runner


def test_transpiler_check_packages_uses_checker(monkeypatch):
    transpiler = PackageDependencyTranspiler(distro="fedora")
    mock_result = DependencyCheckResult(
        package="hello",
        found=True,
        installed=True,
        dependencies=[],
        distro="fedora",
    )
    monkeypatch.setattr(transpiler.checker, "check_dependencies_installed", lambda pkg: mock_result)

    results = transpiler.check_packages(["hello"])

    assert "hello" in results
    assert results["hello"].distro == "fedora"


def test_transpiler_verify_installation_reports_missing(monkeypatch):
    transpiler = PackageDependencyTranspiler(distro="fedora")
    monkeypatch.setattr(transpiler.checker, "is_installed", lambda pkg: pkg == "present")

    all_installed, missing = transpiler.verify_installation(["present", "absent"])

    assert all_installed is False
    assert missing == ["absent"]


def test_transpiler_unknown_distro_raises():
    with pytest.raises(ValueError):
        PackageDependencyTranspiler(distro="unknown")
