from __future__ import annotations

import tempfile
from pathlib import Path

from app.verification.tests import TestRunner
from app.verification.build import BuildRunner
from app.verification.diff import DiffEngine


def test_test_runner_detects_and_runs_passing_tests():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir)

        # Create a passing test
        test_file = ws_path / "test_sample.py"
        test_file.write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")

        report = TestRunner.run_tests(ws_path)
        assert report.status == "passed"
        assert report.passed == 1
        assert report.failed == 0
        assert report.is_successful is True


def test_test_runner_detects_and_parses_failing_tests():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir)

        # Create a failing test
        test_file = ws_path / "test_fail.py"
        test_file.write_text("def test_broken():\n    assert 1 == 2, 'Value mismatch'\n", encoding="utf-8")

        report = TestRunner.run_tests(ws_path)
        assert report.status == "failed"
        assert report.failed == 1
        assert report.passed == 0
        assert report.is_successful is False
        assert len(report.failures) > 0
        assert "test_broken" in report.failures[0].test_name


def test_build_runner_compilation():
    with tempfile.TemporaryDirectory() as tmpdir:
        ws_path = Path(tmpdir)

        # Valid python code
        (ws_path / "valid.py").write_text("def foo():\n    return 42\n", encoding="utf-8")
        report = BuildRunner.run_build(ws_path)
        assert report.status == "passed"

        # Invalid syntax
        (ws_path / "invalid.py").write_text("def foo(:\n", encoding="utf-8")
        report_bad = BuildRunner.run_build(ws_path)
        assert report_bad.status == "failed"
