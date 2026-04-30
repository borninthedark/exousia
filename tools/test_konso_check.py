#!/usr/bin/env python3
"""Tests for konso_check.py — dead code detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from check_utils import find_python_files
from konso_check import DeadCodeIssue, KonsoDetector, main


class TestDeadCodeIssue:
    def test_str_format(self):
        issue = DeadCodeIssue(
            file_path=Path("test.py"), line=10, kind="unreachable", description="dead after return"
        )
        assert "test.py:10" in str(issue)
        assert "[unreachable]" in str(issue)
        assert "dead after return" in str(issue)


class TestKonsoDetector:
    def test_unreachable_after_return(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("def foo():\n    return 1\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "unreachable"
        assert issues[0].line == 3

    def test_unreachable_after_raise(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("def foo():\n    raise ValueError\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "unreachable"

    def test_unreachable_after_break(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("for i in range(10):\n    break\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "unreachable"

    def test_unreachable_after_continue(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("for i in range(10):\n    continue\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "unreachable"

    def test_no_false_positive_conditional_return(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("def foo(x):\n    if x:\n        return 1\n    return 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 0

    def test_dead_branch_always_true(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("if True:\n    x = 1\nelse:\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "dead-branch"
        assert "always True" in issues[0].description

    def test_dead_branch_always_false(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("if False:\n    x = 1\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "dead-branch"
        assert "always False" in issues[0].description

    def test_dead_branch_not_true(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("if not True:\n    x = 1\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert issues[0].kind == "dead-branch"

    def test_no_issue_dynamic_condition(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("x = 1\nif x > 0:\n    pass\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 0

    def test_syntax_error_skipped(self, tmp_path):
        src = tmp_path / "bad.py"
        src.write_text("def foo(:\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 0
        assert detector.files_scanned == 0

    def test_missing_file_skipped(self, tmp_path):
        detector = KonsoDetector()
        issues = detector.scan_file(tmp_path / "missing.py")
        assert len(issues) == 0

    def test_scan_counts(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("def foo():\n    if True:\n        return 1\n    return 2\n")
        detector = KonsoDetector()
        detector.scan_file(src)
        assert detector.files_scanned == 1
        assert detector.functions_scanned == 1
        assert detector.branches_scanned == 1

    def test_multiple_unreachable_after_return(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("def foo():\n    return 1\n    x = 2\n    y = 3\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 2

    def test_unreachable_in_else_block(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("if x:\n    pass\nelse:\n    return 1\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1

    def test_unreachable_in_try_except(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("try:\n    pass\nexcept Exception:\n    raise\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1

    def test_async_function_scanned(self, tmp_path):
        src = tmp_path / "test.py"
        src.write_text("async def foo():\n    return 1\n    x = 2\n")
        detector = KonsoDetector()
        issues = detector.scan_file(src)
        assert len(issues) == 1
        assert detector.functions_scanned == 1


class TestReportLines:
    def test_clean_report(self):
        detector = KonsoDetector()
        detector.files_scanned = 5
        detector.functions_scanned = 20
        detector.branches_scanned = 10
        lines = detector.report_lines()
        assert any("scanned 5 files" in line for line in lines)
        assert any("no dead code found" in line for line in lines)

    def test_issues_report(self):
        detector = KonsoDetector()
        detector.files_scanned = 1
        detector.functions_scanned = 1
        detector.branches_scanned = 0
        detector.issues = [
            DeadCodeIssue(Path("a.py"), 5, "unreachable", "dead after return on line 4")
        ]
        lines = detector.report_lines()
        output = "\n".join(lines)
        assert "DEAD CODE REPORT" in output
        assert "a.py:5" in output
        assert "1 souls awaiting burial" in output


class TestFindPythonFiles:
    def test_finds_py_files(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.txt").write_text("")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("")
        files = find_python_files(tmp_path)
        assert len(files) == 2
        assert all(f.suffix == ".py" for f in files)

    def test_excludes_dirs(self, tmp_path):
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "x.py").write_text("")
        (tmp_path / "a.py").write_text("")
        files = find_python_files(tmp_path)
        assert len(files) == 1


class TestMain:
    def test_clean_exit_zero(self, tmp_path):
        (tmp_path / "clean.py").write_text("def foo():\n    return 1\n")
        assert main(["--path", str(tmp_path)]) == 0

    def test_dead_code_exit_one(self, tmp_path):
        (tmp_path / "dead.py").write_text("def foo():\n    return 1\n    x = 2\n")
        assert main(["--path", str(tmp_path)]) == 1

    def test_no_files_exit_one(self, tmp_path):
        assert main(["--path", str(tmp_path)]) == 1
