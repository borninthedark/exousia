from __future__ import annotations

import os
import subprocess
from collections.abc import Iterable
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "custom-scripts" / "rke2-configure-firewall"


def _write_stub_command(bin_dir: Path, name: str, log_file: Path) -> Path:
    """Create an executable stub that logs its invocations for assertions."""
    stub_path = bin_dir / name
    stub_path.write_text(
        f"""#!/usr/bin/env bash
printf "%s %s\\n" "$(basename \"$0\")" "$*" >> "{log_file}"\n"""
    )
    stub_path.chmod(0o755)
    return stub_path


def _run_helper(bin_dir: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_logged(log_file: Path, expected_lines: Iterable[str]) -> None:
    assert log_file.exists(), "Expected stub to be invoked, but log is missing"
    assert log_file.read_text().splitlines() == list(expected_lines)


def test_prefers_firewall_offline_cmd(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "calls.log"

    _write_stub_command(bin_dir, "firewall-offline-cmd", log_file)
    _write_stub_command(bin_dir, "firewall-cmd", log_file)

    result = _run_helper(bin_dir)

    assert result.returncode == 0
    _assert_logged(
        log_file,
        (
            "firewall-offline-cmd --add-port=6443/tcp",
            "firewall-offline-cmd --add-port=9345/tcp",
            "firewall-offline-cmd --add-port=10250/tcp",
            "firewall-offline-cmd --add-port=2379-2380/tcp",
        ),
    )


def test_falls_back_to_firewall_cmd(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "calls.log"

    _write_stub_command(bin_dir, "firewall-cmd", log_file)

    result = _run_helper(bin_dir)

    assert result.returncode == 0
    _assert_logged(
        log_file,
        (
            "firewall-cmd --permanent --add-port=6443/tcp",
            "firewall-cmd --permanent --add-port=9345/tcp",
            "firewall-cmd --permanent --add-port=10250/tcp",
            "firewall-cmd --permanent --add-port=2379-2380/tcp",
        ),
    )


def test_warns_when_firewalld_tools_missing(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    result = _run_helper(bin_dir)

    assert result.returncode == 0
    assert "firewalld utilities not available" in result.stderr
    assert result.stdout == ""
