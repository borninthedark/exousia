#!/usr/bin/env python3
"""Konsō Check (魂葬) — dead code detection for Python files.

Performs Soul Burial on dead code: unreachable statements, dead conditional
branches, and constant guards that can never trigger. Designed as a
pre-commit hook to catch dead code before it lands.

Named after the Konsō ritual from Bleach — sending departed souls to rest.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

from check_utils import find_python_files


@dataclass
class DeadCodeIssue:
    """A single dead code finding."""

    file_path: Path
    line: int
    kind: str
    description: str

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line}: [{self.kind}] {self.description}"


@dataclass
class KonsoDetector:
    """AST-based dead code detector for Python files."""

    issues: list[DeadCodeIssue] = field(default_factory=list)
    files_scanned: int = 0
    functions_scanned: int = 0
    branches_scanned: int = 0

    def scan_file(self, file_path: Path) -> list[DeadCodeIssue]:
        """Scan a single Python file for dead code patterns."""
        try:
            source = file_path.read_text()
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, OSError):
            return []

        self.files_scanned += 1
        lines = source.splitlines()
        file_issues: list[DeadCodeIssue] = []

        for node in ast.walk(tree):
            file_issues.extend(self._check_unreachable_after_return(node, file_path))
            file_issues.extend(self._check_dead_conditionals(node, file_path, lines))

        self.issues.extend(file_issues)
        return file_issues

    def _check_unreachable_after_return(
        self, node: ast.AST, file_path: Path
    ) -> list[DeadCodeIssue]:
        """Detect statements after return/raise/break/continue in a block."""
        issues: list[DeadCodeIssue] = []

        body: list[ast.stmt] | None = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            self.functions_scanned += 1
        elif isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            body = node.body

        if body:
            issues.extend(self._scan_block(body, file_path))

        if hasattr(node, "orelse") and isinstance(node.orelse, list) and node.orelse:
            issues.extend(self._scan_block(node.orelse, file_path))
        if hasattr(node, "finalbody") and isinstance(node.finalbody, list) and node.finalbody:
            issues.extend(self._scan_block(node.finalbody, file_path))
        if hasattr(node, "handlers") and isinstance(node.handlers, list):
            for handler in node.handlers:
                if isinstance(handler.body, list):
                    issues.extend(self._scan_block(handler.body, file_path))

        return issues

    def _scan_block(self, stmts: list[ast.stmt], file_path: Path) -> list[DeadCodeIssue]:
        """Find statements after an unconditional exit in a block."""
        issues: list[DeadCodeIssue] = []
        for i, stmt in enumerate(stmts):
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                for dead in stmts[i + 1 :]:
                    issues.append(
                        DeadCodeIssue(
                            file_path=file_path,
                            line=dead.lineno,
                            kind="unreachable",
                            description=(
                                f"unreachable code after "
                                f"{type(stmt).__name__.lower()} on line {stmt.lineno}"
                            ),
                        )
                    )
                break
        return issues

    def _check_dead_conditionals(
        self, node: ast.AST, file_path: Path, lines: list[str]
    ) -> list[DeadCodeIssue]:
        """Detect if/elif with constant conditions (always true/false)."""
        issues: list[DeadCodeIssue] = []

        if not isinstance(node, ast.If):
            return issues

        self.branches_scanned += 1

        const_val = self._eval_constant(node.test)
        if const_val is None:
            return issues

        if const_val:
            if node.orelse:
                first_else = node.orelse[0]
                issues.append(
                    DeadCodeIssue(
                        file_path=file_path,
                        line=first_else.lineno,
                        kind="dead-branch",
                        description=(
                            f"else/elif block is dead — "
                            f"condition on line {node.lineno} is always True"
                        ),
                    )
                )
        else:
            issues.append(
                DeadCodeIssue(
                    file_path=file_path,
                    line=node.lineno,
                    kind="dead-branch",
                    description="if block is dead — condition is always False",
                )
            )

        return issues

    @staticmethod
    def _eval_constant(node: ast.AST) -> bool | None:
        """Evaluate a constant boolean expression, or return None if dynamic."""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            inner = KonsoDetector._eval_constant(node.operand)
            if inner is not None:
                return not inner
        return None

    def report_lines(self) -> list[str]:
        """Return the dead code report as a list of plain-text lines."""
        lines: list[str] = []

        lines.append(
            f"konso-check: scanned {self.files_scanned} files, "
            f"{self.functions_scanned} functions, "
            f"{self.branches_scanned} branches"
        )

        if not self.issues:
            lines.append("konso-check: no dead code found — all souls at rest")
            return lines

        lines.append("")
        lines.append("=" * 80)
        lines.append("KONSŌ — DEAD CODE REPORT")
        lines.append("=" * 80)

        sorted_issues = sorted(self.issues, key=lambda i: (str(i.file_path), i.line))
        for idx, issue in enumerate(sorted_issues, 1):
            lines.append(f"\n{idx}. {issue}")

        lines.append("")
        lines.append("=" * 80)
        lines.append(f"TOTAL: {len(self.issues)} souls awaiting burial")
        lines.append("=" * 80)

        return lines


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 on clean, 1 if dead code found."""
    parser = argparse.ArgumentParser(description="Konsō — dead code detection for Python files")
    parser.add_argument("--path", type=str, help="Root directory to scan")

    args = parser.parse_args(argv)

    root = Path(args.path).resolve() if args.path else Path(__file__).resolve().parent.parent

    files = find_python_files(root)
    if not files:
        print("konso-check: no Python files found")
        return 1

    detector = KonsoDetector()
    for f in files:
        detector.scan_file(f)

    for line in detector.report_lines():
        print(line)

    return 1 if detector.issues else 0


if __name__ == "__main__":
    sys.exit(main())
