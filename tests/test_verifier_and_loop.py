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


def test_independent_verifier_exceptions_never_report_success(temp_workspace):
    from unittest.mock import patch
    (temp_workspace / "valid.py").write_text("x = 1\n", encoding="utf-8")
    verifier = IndependentVerifier(temp_workspace)

    # Simulate an internal unexpected exception during syntax check
    with patch.object(verifier, "_check_python_syntax", side_effect=RuntimeError("Simulated internal parser crash")):
        res = verifier.verify(["valid.py"])
        assert res.passed is False
        assert res.status.value == "unavailable"
        assert "Simulated internal parser crash" in res.summary or "Simulated internal parser crash" in res.details


def test_independent_verifier_unavailable_tool_never_reports_success(temp_workspace):
    from unittest.mock import patch
    (temp_workspace / "code.py").write_text("def run(): pass\n", encoding="utf-8")
    tests_dir = temp_workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_code.py").write_text("def test_run(): pass\n", encoding="utf-8")

    verifier = IndependentVerifier(temp_workspace)
    # Simulate missing pytest executable
    with patch.object(verifier, "_run_project_tests", return_value=("pytest executable not found: [Errno 2]", "", "pytest")):
        res = verifier.verify(["code.py"], goal="run pytest")
        assert res.passed is False
        assert res.status.value == "unavailable"
        assert "unavailable" in res.summary.lower()


def test_independent_verifier_typescript_unavailable_fails_honestly(temp_workspace):
    from unittest.mock import patch
    from astra.workspace import ProjectMetadata, ProjectType
    (temp_workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
    (temp_workspace / "app.ts").write_text("const x: number = 42;", encoding="utf-8")

    verifier = IndependentVerifier(temp_workspace)
    mock_meta = ProjectMetadata(workspace_path=str(temp_workspace), project_type=ProjectType.TYPESCRIPT)
    with patch.object(verifier.workspace_manager, "scan", return_value=mock_meta), \
         patch.object(verifier, "_check_typescript", return_value=("npx: command not found", "unavailable")):
        res = verifier.verify(["app.ts"])
        assert res.passed is False
        assert res.status.value == "unavailable"
        assert "unavailable" in res.summary.lower()

