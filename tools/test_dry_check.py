"""Tests for dry_check.py -- DRY enforcement tool."""

from __future__ import annotations

import pytest
from dry_check import CodeBlock, DuplicationDetector, _hash_content, find_python_files, main

# ---------------------------------------------------------------------------
# _hash_content
# ---------------------------------------------------------------------------


class TestHashContent:
    def test_deterministic(self):
        assert _hash_content("hello") == _hash_content("hello")

    def test_different_inputs(self):
        assert _hash_content("a") != _hash_content("b")

    def test_empty_string(self):
        result = _hash_content("")
        assert isinstance(result, str) and len(result) == 32


# ---------------------------------------------------------------------------
# CodeBlock
# ---------------------------------------------------------------------------


class TestCodeBlock:
    def test_basic_attrs(self, tmp_path):
        cb = CodeBlock(tmp_path / "f.py", 1, 10, "x = 1")
        assert cb.start_line == 1
        assert cb.end_line == 10
        assert cb.line_count == 10
        assert cb.content == "x = 1"
        assert isinstance(cb.hash, str)

    def test_repr(self, tmp_path):
        cb = CodeBlock(tmp_path / "f.py", 5, 9, "pass")
        r = repr(cb)
        assert "5-9" in r
        assert "5 lines" in r

    def test_hash_matches_content(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 1, "same")
        b = CodeBlock(tmp_path / "b.py", 1, 1, "same")
        assert a.hash == b.hash

    def test_hash_differs(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 1, "aaa")
        b = CodeBlock(tmp_path / "b.py", 1, 1, "bbb")
        assert a.hash != b.hash


# ---------------------------------------------------------------------------
# DuplicationDetector -- extraction
# ---------------------------------------------------------------------------


class TestExtractFunctions:
    def test_extracts_function(self, tmp_path):
        src = tmp_path / "mod.py"
        src.write_text(
            "def foo():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = 3\n"
            "    d = 4\n"
            "    return a + b + c + d\n"
        )
        dd = DuplicationDetector(min_lines=3)
        blocks = dd.extract_functions(src)
        assert len(blocks) == 1
        assert blocks[0].start_line == 1
        assert blocks[0].end_line == 6

    def test_skips_short_functions(self, tmp_path):
        src = tmp_path / "short.py"
        src.write_text("def tiny():\n    pass\n")
        dd = DuplicationDetector(min_lines=5)
        assert dd.extract_functions(src) == []

    def test_syntax_error_returns_empty(self, tmp_path):
        src = tmp_path / "bad.py"
        src.write_text("def broken(\n")
        dd = DuplicationDetector()
        assert dd.extract_functions(src) == []

    def test_missing_file_returns_empty(self, tmp_path):
        dd = DuplicationDetector()
        assert dd.extract_functions(tmp_path / "nonexistent.py") == []

    def test_async_function(self, tmp_path):
        src = tmp_path / "async_mod.py"
        src.write_text(
            "async def handler():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = 3\n"
            "    d = 4\n"
            "    return a + b + c + d\n"
        )
        dd = DuplicationDetector(min_lines=3)
        blocks = dd.extract_functions(src)
        assert len(blocks) == 1


class TestExtractCodeBlocks:
    def test_extracts_blocks(self, tmp_path):
        src = tmp_path / "blocks.py"
        src.write_text("\n".join(f"line_{i} = {i}" for i in range(20)) + "\n")
        dd = DuplicationDetector(min_lines=5)
        blocks = dd.extract_code_blocks(src)
        assert len(blocks) > 0

    def test_skips_short_files(self, tmp_path):
        src = tmp_path / "tiny.py"
        src.write_text("x = 1\n")
        dd = DuplicationDetector(min_lines=5)
        assert dd.extract_code_blocks(src) == []

    def test_skips_comment_heavy_blocks(self, tmp_path):
        src = tmp_path / "comments.py"
        src.write_text("\n".join(f"# comment {i}" for i in range(20)) + "\n")
        dd = DuplicationDetector(min_lines=5)
        blocks = dd.extract_code_blocks(src)
        assert len(blocks) == 0

    def test_missing_file_returns_empty(self, tmp_path):
        dd = DuplicationDetector()
        assert dd.extract_code_blocks(tmp_path / "gone.py") == []


# ---------------------------------------------------------------------------
# DuplicationDetector -- similarity and overlap
# ---------------------------------------------------------------------------


class TestSimilarity:
    def test_identical(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 1, "x = 1")
        assert DuplicationDetector.calculate_similarity(a, a) == 1.0

    def test_different(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 1, "aaaaaa")
        b = CodeBlock(tmp_path / "b.py", 1, 1, "zzzzzz")
        assert DuplicationDetector.calculate_similarity(a, b) < 0.5

    def test_whitespace_normalized(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 1, "x   =   1")
        b = CodeBlock(tmp_path / "b.py", 1, 1, "x = 1")
        assert DuplicationDetector.calculate_similarity(a, b) == 1.0


class TestBlocksOverlap:
    @pytest.mark.parametrize(
        ("start_a", "end_a", "start_b", "end_b", "expected"),
        [(1, 10, 5, 15, True), (1, 5, 6, 10, False)],
        ids=["overlapping", "disjoint"],
    )
    def test_same_file(self, tmp_path, start_a, end_a, start_b, end_b, expected):
        f = tmp_path / "f.py"
        a = CodeBlock(f, start_a, end_a, "x")
        b = CodeBlock(f, start_b, end_b, "y")
        assert DuplicationDetector._blocks_overlap(a, b) is expected

    def test_different_files_never_overlap(self, tmp_path):
        a = CodeBlock(tmp_path / "a.py", 1, 10, "x")
        b = CodeBlock(tmp_path / "b.py", 1, 10, "x")
        assert DuplicationDetector._blocks_overlap(a, b) is False


# ---------------------------------------------------------------------------
# DuplicationDetector -- find_duplicates
# ---------------------------------------------------------------------------


class TestFindDuplicates:
    def _write_duplicate_files(self, tmp_path):
        """Create two files with identical 6-line functions."""
        body = (
            "def compute():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = a + b\n"
            "    d = c * 2\n"
            "    return d\n"
        )
        (tmp_path / "one.py").write_text(body)
        (tmp_path / "two.py").write_text(body)
        return [tmp_path / "one.py", tmp_path / "two.py"]

    def test_finds_exact_function_duplicates(self, tmp_path):
        files = self._write_duplicate_files(tmp_path)
        dd = DuplicationDetector(min_lines=3)
        dd.find_duplicates(files, use_functions=True)
        assert len(dd.duplicates) > 0
        assert dd.duplicates[0][2] == 1.0

    def test_finds_exact_block_duplicates(self, tmp_path):
        files = self._write_duplicate_files(tmp_path)
        dd = DuplicationDetector(min_lines=3)
        dd.find_duplicates(files, use_functions=False)
        exact = [d for d in dd.duplicates if d[2] == 1.0]
        assert len(exact) > 0

    def test_no_duplicates_in_unique_files(self, tmp_path):
        (tmp_path / "a.py").write_text(
            "def alpha():\n" + "\n".join(f"    v{i} = {i}" for i in range(10)) + "\n"
        )
        (tmp_path / "b.py").write_text(
            "def beta():\n" + "\n".join(f"    w{i} = '{chr(65+i)}'" for i in range(10)) + "\n"
        )
        dd = DuplicationDetector(min_lines=5, similarity_threshold=0.95)
        dd.find_duplicates([tmp_path / "a.py", tmp_path / "b.py"], use_functions=True)
        exact = [d for d in dd.duplicates if d[2] == 1.0]
        assert len(exact) == 0


# ---------------------------------------------------------------------------
# DuplicationDetector -- report
# ---------------------------------------------------------------------------


class TestReport:
    def test_no_duplicates_message(self):
        dd = DuplicationDetector()
        lines = dd.report_lines()
        assert any("No significant" in ln for ln in lines)

    def test_report_with_duplicates(self, tmp_path):
        body = (
            "def compute():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = a + b\n"
            "    d = c * 2\n"
            "    return d\n"
        )
        (tmp_path / "one.py").write_text(body)
        (tmp_path / "two.py").write_text(body)
        dd = DuplicationDetector(min_lines=3)
        dd.find_duplicates([tmp_path / "one.py", tmp_path / "two.py"], use_functions=True)
        lines = dd.report_lines()
        report_text = "\n".join(lines)
        assert "DUPLICATION REPORT" in report_text
        assert "REMEDIATION TASKS" in report_text
        assert "EXACT DUPLICATE" in report_text

    def test_report_similar_code(self, tmp_path):
        b1 = CodeBlock(tmp_path / "a.py", 1, 5, "content_a")
        b2 = CodeBlock(tmp_path / "b.py", 1, 5, "content_b")
        dd = DuplicationDetector()
        dd.duplicates = [(b1, b2, 0.85)]
        lines = dd.report_lines()
        report_text = "\n".join(lines)
        assert "SIMILAR CODE" in report_text
        assert "Review similar code" in report_text


# ---------------------------------------------------------------------------
# find_python_files
# ---------------------------------------------------------------------------


class TestFindPythonFiles:
    def test_finds_py_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        (tmp_path / "b.py").write_text("y = 2\n")
        (tmp_path / "c.txt").write_text("not python\n")
        result = find_python_files(tmp_path)
        assert len(result) == 2

    def test_excludes_dirs(self, tmp_path):
        (tmp_path / "good.py").write_text("x = 1\n")
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "bad.py").write_text("x = 1\n")
        result = find_python_files(tmp_path)
        assert len(result) == 1

    def test_custom_excludes(self, tmp_path):
        mydir = tmp_path / "skip_me"
        mydir.mkdir()
        (mydir / "f.py").write_text("x = 1\n")
        (tmp_path / "keep.py").write_text("x = 1\n")
        result = find_python_files(tmp_path, exclude_dirs=frozenset({"skip_me"}))
        assert len(result) == 1

    def test_sorted_output(self, tmp_path):
        (tmp_path / "z.py").write_text("x = 1\n")
        (tmp_path / "a.py").write_text("y = 2\n")
        result = find_python_files(tmp_path)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# main() CLI entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_returns_zero_no_duplicates(self, tmp_path):
        (tmp_path / "unique.py").write_text(
            "def unique_func():\n" + "\n".join(f"    v{i} = {i}" for i in range(10)) + "\n"
        )
        rc = main(["--path", str(tmp_path), "--functions-only"])
        assert rc == 0

    def test_returns_one_with_duplicates(self, tmp_path):
        body = (
            "def compute():\n"
            "    a = 1\n"
            "    b = 2\n"
            "    c = a + b\n"
            "    d = c * 2\n"
            "    return d\n"
        )
        (tmp_path / "one.py").write_text(body)
        (tmp_path / "two.py").write_text(body)
        rc = main(["--path", str(tmp_path), "--functions-only", "--min-lines", "3"])
        assert rc == 1

    def test_returns_one_no_files(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        rc = main(["--path", str(empty)])
        assert rc == 1

    def test_custom_similarity(self, tmp_path):
        (tmp_path / "f.py").write_text(
            "def func():\n" + "\n".join(f"    x{i} = {i}" for i in range(10)) + "\n"
        )
        rc = main(["--path", str(tmp_path), "--similarity", "0.99", "--functions-only"])
        assert rc == 0
