"""Shared utilities for pre-commit check tools (dry-check, konso-check)."""

from __future__ import annotations

from pathlib import Path

DEFAULT_EXCLUDE_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".pytest_cache",
        ".mypy_cache",
    }
)


def find_python_files(
    root: Path,
    exclude_dirs: frozenset[str] | None = None,
) -> list[Path]:
    """Recursively find ``*.py`` files under *root*, skipping excluded dirs."""
    if exclude_dirs is None:
        exclude_dirs = DEFAULT_EXCLUDE_DIRS

    return sorted(
        p for p in root.rglob("*.py") if not any(excluded in p.parts for excluded in exclude_dirs)
    )
