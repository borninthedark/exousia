#!/usr/bin/env python3
"""DRY (Don't Repeat Yourself) enforcement tool.

Detects code duplication in Python files by comparing function bodies
and sliding-window code blocks using MD5 hashing for exact matches
and SequenceMatcher for fuzzy similarity.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

# Defaults
DEFAULT_MIN_LINES = 5
DEFAULT_SIMILARITY = 0.8
DEFAULT_MAX_WINDOW = 50
DEFAULT_MIN_CONTENT_LEN = 20
COMMENT_RATIO_THRESHOLD = 0.5

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


def _hash_content(content: str) -> str:
    """Return MD5 hex digest of *content* (non-security use)."""
    return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()  # nosec B324


class CodeBlock:
    """A contiguous region of source code with location metadata."""

    __slots__ = ("file_path", "start_line", "end_line", "content", "hash")

    def __init__(self, file_path: Path, start_line: int, end_line: int, content: str):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.hash = _hash_content(content)

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

    def __repr__(self) -> str:
        return f"{self.file_path}:{self.start_line}-{self.end_line} ({self.line_count} lines)"


class DuplicationDetector:
    """Find exact and near-duplicate code blocks across Python files."""

    def __init__(
        self,
        min_lines: int = DEFAULT_MIN_LINES,
        similarity_threshold: float = DEFAULT_SIMILARITY,
    ):
        self.min_lines = min_lines
        self.similarity_threshold = similarity_threshold
        self.blocks: list[CodeBlock] = []
        self.duplicates: list[tuple[CodeBlock, CodeBlock, float]] = []

    # -- extraction --------------------------------------------------------

    def extract_functions(self, file_path: Path) -> list[CodeBlock]:
        """Extract function/method bodies that meet the minimum-lines bar."""
        blocks: list[CodeBlock] = []
        try:
            content = file_path.read_text()
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return blocks
        except OSError:
            return blocks

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = node.end_lineno or start
                if end - start + 1 >= self.min_lines:
                    func_content = "\n".join(content.splitlines()[start - 1 : end])
                    blocks.append(CodeBlock(file_path, start, end, func_content))
        return blocks

    def extract_code_blocks(self, file_path: Path) -> list[CodeBlock]:
        """Extract sliding-window code blocks from *file_path*."""
        blocks: list[CodeBlock] = []
        try:
            lines = file_path.read_text().splitlines(keepends=True)
        except OSError:
            return blocks

        if len(lines) < self.min_lines:
            return blocks

        for i in range(len(lines) - self.min_lines + 1):
            max_window = min(DEFAULT_MAX_WINDOW, len(lines) - i + 1)
            for window_size in range(self.min_lines, max_window):
                content = "".join(lines[i : i + window_size]).strip()
                if len(content) < DEFAULT_MIN_CONTENT_LEN:
                    continue
                line_count = len(content.splitlines())
                if line_count == 0:
                    continue
                comment_lines = sum(1 for ln in content.splitlines() if ln.strip().startswith("#"))
                if comment_lines / line_count > COMMENT_RATIO_THRESHOLD:
                    continue
                blocks.append(CodeBlock(file_path, i + 1, i + window_size, content))
        return blocks

    # -- analysis ----------------------------------------------------------

    @staticmethod
    def calculate_similarity(block1: CodeBlock, block2: CodeBlock) -> float:
        """Return 0-1 similarity ratio between two blocks (whitespace-normalized)."""
        a = " ".join(block1.content.split())
        b = " ".join(block2.content.split())
        return difflib.SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _blocks_overlap(a: CodeBlock, b: CodeBlock) -> bool:
        """Return True if *a* and *b* overlap within the same file."""
        if a.file_path != b.file_path:
            return False
        return not (a.end_line < b.start_line or b.end_line < a.start_line)

    def find_duplicates(self, files: list[Path], *, use_functions: bool = False) -> None:
        """Populate *self.duplicates* from the given *files*."""
        for file_path in files:
            if use_functions:
                self.blocks.extend(self.extract_functions(file_path))
            else:
                self.blocks.extend(self.extract_code_blocks(file_path))

        # Phase 1: exact duplicates via hash buckets
        hash_groups: dict[str, list[CodeBlock]] = defaultdict(list)
        for block in self.blocks:
            hash_groups[block.hash].append(block)

        for group in hash_groups.values():
            if len(group) > 1:
                for i in range(len(group)):
                    for j in range(i + 1, len(group)):
                        if not self._blocks_overlap(group[i], group[j]):
                            self.duplicates.append((group[i], group[j], 1.0))

        # Phase 2: fuzzy similarity for non-exact matches
        seen: set[tuple[str, str]] = set()
        for i, b1 in enumerate(self.blocks):
            for b2 in self.blocks[i + 1 :]:
                if self._blocks_overlap(b1, b2):
                    continue
                key = (
                    f"{b1.file_path}:{b1.start_line}",
                    f"{b2.file_path}:{b2.start_line}",
                )
                if key in seen:
                    continue
                sim = self.calculate_similarity(b1, b2)
                if self.similarity_threshold <= sim < 1.0:
                    self.duplicates.append((b1, b2, sim))
                    seen.add(key)

    # -- reporting ---------------------------------------------------------

    def report_lines(self) -> list[str]:
        """Return the duplication report as a list of plain-text lines."""
        if not self.duplicates:
            return ["No significant code duplication found."]

        lines: list[str] = []
        lines.append(f"Found {len(self.duplicates)} duplicate code blocks")
        lines.append("")
        lines.append("=" * 80)
        lines.append("DUPLICATION REPORT")
        lines.append("=" * 80)

        sorted_dupes = sorted(self.duplicates, key=lambda x: x[2], reverse=True)
        for idx, (b1, b2, sim) in enumerate(sorted_dupes, 1):
            lines.append(f"\n{idx}. Similarity: {sim:.1%}")
            lines.append(f"   Location 1: {b1}")
            lines.append(f"   Location 2: {b2}")
            if sim == 1.0:
                lines.append("   EXACT DUPLICATE")
            else:
                lines.append(f"   SIMILAR CODE ({sim:.1%})")

        lines.append("")
        lines.append("=" * 80)
        lines.append("REMEDIATION TASKS")
        lines.append("=" * 80)

        file_groups: dict[Path, list[tuple]] = defaultdict(list)
        for b1, b2, sim in sorted_dupes:
            file_groups[b1.file_path].append((b1, b2, sim))

        for file_path, dupes in file_groups.items():
            lines.append(f"\n{file_path}")
            for b1, b2, sim in dupes:
                if sim == 1.0:
                    lines.append(
                        f"  [ ] Extract duplicate at lines "
                        f"{b1.start_line}-{b1.end_line} to shared function"
                    )
                    lines.append(f"      Also found in: {b2.file_path}")
                else:
                    lines.append(
                        f"  [ ] Review similar code at lines " f"{b1.start_line}-{b1.end_line}"
                    )
                    lines.append(
                        f"      Similar to: {b2.file_path}:" f"{b2.start_line}-{b2.end_line}"
                    )
        return lines


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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.  Returns 0 on success, 1 if duplicates found."""
    parser = argparse.ArgumentParser(description="Detect code duplication in Python files")
    parser.add_argument("--min-lines", type=int, default=DEFAULT_MIN_LINES)
    parser.add_argument("--similarity", type=float, default=DEFAULT_SIMILARITY)
    parser.add_argument("--functions-only", action="store_true")
    parser.add_argument("--path", type=str)

    args = parser.parse_args(argv)

    root = Path(args.path).resolve() if args.path else Path(__file__).resolve().parent.parent

    files = find_python_files(root)
    if not files:
        return 1

    detector = DuplicationDetector(
        min_lines=args.min_lines,
        similarity_threshold=args.similarity,
    )
    detector.find_duplicates(files, use_functions=args.functions_only)

    for line in detector.report_lines():
        print(line)

    return 1 if detector.duplicates else 0


if __name__ == "__main__":
    sys.exit(main())
