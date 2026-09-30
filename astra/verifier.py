"""Independent Verifier for ASTRA Autonomous Agent.

Enforces mandatory independent verification (AST syntax check, byte-compilation,
and pytest test execution) to ensure no task is marked completed on mere hallucination.
"""
from __future__ import annotations

import ast
import os
import py_compile
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Tuple


class VerificationResult:
    """Outcome of an independent verification check."""

    def __init__(self, passed: bool, summary: str, details: str = "", phase: str = "complete"):
        self.passed = passed
        self.summary = summary
        self.details = details
        self.phase = phase

    def __repr__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return f"<VerificationResult [{status}] phase={self.phase}: {self.summary}>"


class IndependentVerifier:
    """Performs objective, external verification on modified code."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path.resolve()

    def verify(self, modified_files: Set[str] | List[str]) -> VerificationResult:
        """Run multi-stage verification on modified files and the test suite."""
        resolved_files: List[Path] = []
        for f in modified_files:
            p = Path(f)
            if not p.is_absolute():
                p = self.workspace_path / p
            if p.exists() and p.is_file():
                resolved_files.append(p)

        # 1. Stage 1: AST Syntax and Compilation Check
        py_files = [f for f in resolved_files if f.suffix == ".py"]
        syntax_err = self._check_syntax_and_compile(py_files)
        if syntax_err:
            return VerificationResult(
                passed=False,
                summary="AST Syntax or Compilation check failed.",
                details=syntax_err,
                phase="syntax_check",
            )

        # 2. Stage 2: Automated Test Execution (pytest)
        test_err, test_summary = self._run_test_suite()
        if test_err:
            return VerificationResult(
                passed=False,
                summary="Test suite execution failed.",
                details=test_err,
                phase="test_execution",
            )

        # 3. All checks passed
        details = test_summary or f"Verified {len(py_files)} modified Python file(s) with clean AST and compilation."
        return VerificationResult(
            passed=True,
            summary="All independent verification checks passed successfully.",
            details=details,
            phase="verified",
        )

    def _check_syntax_and_compile(self, py_files: List[Path]) -> Optional[str]:
        """Verify that every modified python file has valid syntax and compiles."""
        for pf in py_files:
            try:
                content = pf.read_text(encoding="utf-8", errors="replace")
                ast.parse(content, filename=str(pf))
            except SyntaxError as syn_err:
                rel = pf.relative_to(self.workspace_path) if pf.is_relative_to(self.workspace_path) else pf.name
                line_text = syn_err.text.strip() if syn_err.text else ""
                return (
                    f"SyntaxError in '{rel}' at line {syn_err.lineno}, col {syn_err.offset}:\n"
                    f"  {line_text}\n"
                    f"Error: {syn_err.msg}"
                )
            except Exception as e:
                return f"Error parsing '{pf.name}': {e}"

            # PyCompile check
            try:
                py_compile.compile(str(pf), doraise=True)
            except py_compile.PyCompileError as pyc_err:
                return f"Byte-compilation failed for '{pf.name}': {pyc_err}"
            except Exception:
                pass

        return None

    def _run_test_suite(self) -> Tuple[Optional[str], str]:
        """Locate test suite and execute pytest if tests exist."""
        has_tests = False
        tests_dir = self.workspace_path / "tests"
        if tests_dir.exists() and tests_dir.is_dir():
            has_tests = True
        else:
            # Check for any test_*.py or *_test.py files
            for p in self.workspace_path.glob("**/test_*.py"):
                if "node_modules" not in str(p) and ".pytest_cache" not in str(p):
                    has_tests = True
                    break

        if not has_tests:
            return None, "No automated test suite detected in workspace. Syntax verified."

        try:
            res = subprocess.run(
                ["python", "-m", "pytest", "-q", "--tb=short"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=45,
                check=False,
            )
            output = (res.stdout + "\n" + res.stderr).strip()
            if res.returncode != 0:
                # Truncate output to top 1500 chars to avoid giant tracebacks
                err_lines = output.splitlines()
                preview = "\n".join(err_lines[-35:]) if len(err_lines) > 35 else output
                return preview, ""
            
            # Extract test summary line
            summary_line = output.splitlines()[-1] if output else "Tests passed."
            return None, f"pytest passed: {summary_line}"
        except subprocess.TimeoutExpired:
            return "Test execution timed out after 45 seconds.", ""
        except Exception as exc:
            return f"Error executing pytest: {exc}", ""
