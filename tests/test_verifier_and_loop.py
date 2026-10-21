"""Unit tests for IndependentVerifier and LoopDetector."""
import shutil
import tempfile
from pathlib import Path
import pytest

from astra.verifier import ErrorCategory, IndependentVerifier, LoopDetector


@pytest.fixture
def temp_workspace():
    td = tempfile.mkdtemp()
    ws = Path(td).resolve()
    yield ws
    shutil.rmtree(td, ignore_errors=True)


def test_loop_detector_triggers_after_repeated_errors():
    detector = LoopDetector(max_repeated_errors=3)
    err = "AssertionError: assert 2 == 3"
    
    # 1st time
    assert detector.record_and_check(err) is False
    # 2nd time
    assert detector.record_and_check(err) is False
    # 3rd time -> Repeated error loop detected!
    assert detector.record_and_check(err) is True


def test_error_classification():
    verifier = IndependentVerifier(Path.cwd())
    
    assert verifier.classify_error("SyntaxError: invalid syntax (<string>, line 1)") == ErrorCategory.SYNTAX
    assert verifier.classify_error("TypeError: 'int' object is not callable") == ErrorCategory.TYPE_CHECK
    assert verifier.classify_error("ModuleNotFoundError: No module named 'foobar'") == ErrorCategory.MISSING_DEPENDENCY
    assert verifier.classify_error("AssertionError: assert add(1, 2) == 4") == ErrorCategory.TEST_FAILURE
    assert verifier.classify_error("pytest timed out after 60 seconds") == ErrorCategory.TIMEOUT


def test_independent_verifier_with_passing_pytest(temp_workspace):
    # Create code
    (temp_workspace / "math_mod.py").write_text("def mul(a, b):\n    return a * b\n")
    # Create test
    tests_dir = temp_workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_math.py").write_text("from math_mod import mul\ndef test_mul():\n    assert mul(3, 4) == 12\n")

    verifier = IndependentVerifier(temp_workspace)
    res = verifier.verify(["math_mod.py"])
    assert res.passed is True
    assert res.phase == "verified"
    assert "pytest passed" in res.details
    assert len(res.checks_run) >= 1


def test_independent_verifier_syntax_error_failure(temp_workspace):
    # Broken syntax in python file
    (temp_workspace / "bad.py").write_text("def broken(\n", encoding="utf-8")
    verifier = IndependentVerifier(temp_workspace)
    res = verifier.verify(["bad.py"])
    assert res.passed is False
    assert res.status.value == "failed"
    assert res.phase == "syntax_check"
    assert res.error_category == ErrorCategory.SYNTAX
    assert len(res.checks_run) == 1
    assert res.checks_run[0]["status"] == "failed"


def test_independent_verifier_failing_test(temp_workspace):
    (temp_workspace / "calc.py").write_text("def sub(a, b): return a + b\n", encoding="utf-8")
    tests_dir = temp_workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text("from calc import sub\ndef test_sub(): assert sub(5, 2) == 3\n", encoding="utf-8")
    verifier = IndependentVerifier(temp_workspace)
    res = verifier.verify(["calc.py"])
    assert res.passed is False
    assert res.status.value == "failed"
    assert res.phase == "test_execution"
    assert res.error_category == ErrorCategory.TEST_FAILURE
