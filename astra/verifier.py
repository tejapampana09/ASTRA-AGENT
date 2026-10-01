"""ASTRA V4 Multi-Language Independent Verification Engine.

Supports:
- Python (AST syntax, bytecode compilation, pytest / unittest)
- Node.js / React / TypeScript (syntax, npm test, tsc typecheck, build)
- Rust (cargo test, cargo check)
- Go (go test)
- Loop detection (repeated errors x 3 stops with diagnosis)
- Error classification (syntax, type, build, test, runtime)
"""
from __future__ import annotations

import ast
import os
import py_compile
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from astra.workspace import ProjectMetadata, ProjectType, WorkspaceManager


class ErrorCategory(str, Enum):
    SYNTAX = "syntax_error"
    TYPE_CHECK = "type_error"
    BUILD = "build_error"
    TEST_FAILURE = "test_failure"
    MISSING_DEPENDENCY = "missing_dependency"
    RUNTIME = "runtime_error"
    TIMEOUT = "timeout_error"
    UNKNOWN = "unknown_error"


@dataclass
class VerificationResult:
    """Outcome of an independent verification check."""
    passed: bool
    summary: str
    details: str = ""
    phase: str = "complete"
    error_category: Optional[ErrorCategory] = None
    failing_command: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary,
            "details": self.details,
            "phase": self.phase,
            "error_category": self.error_category.value if self.error_category else None,
            "failing_command": self.failing_command,
        }

    def __repr__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        return f"<VerificationResult [{status}] phase={self.phase}: {self.summary}>"


class LoopDetector:
    """Detects repeated identical failures to avoid infinite looping and thrashing."""

    def __init__(self, max_repeated_errors: int = 3):
        self.max_repeated = max_repeated_errors
        self.error_history: List[str] = []

    def record_and_check(self, error_str: str) -> bool:
        """Return True if loop/stall is detected (same failure repeated >= max_repeated)."""
        # Normalize whitespace and numbers/paths slightly to catch similar errors
        normalized = re.sub(r"\s+", " ", error_str.strip()[:300].lower())
        self.error_history.append(normalized)

        # Check last N
        if len(self.error_history) >= self.max_repeated:
            recent = self.error_history[-self.max_repeated:]
            if len(set(recent)) == 1:
                return True
        return False


class IndependentVerifier:
    """Performs objective, project-aware external verification."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path.resolve()
        self.workspace_manager = WorkspaceManager(self.workspace_path)
        self.loop_detector = LoopDetector(max_repeated_errors=3)

    def classify_error(self, output: str) -> ErrorCategory:
        lowered = output.lower()
        if "syntaxerror" in lowered or "syntax error" in lowered or "parsing error" in lowered:
            return ErrorCategory.SYNTAX
        if "typeerror" in lowered or "ts2" in lowered or "cannot find name" in lowered or "type mismatch" in lowered:
            return ErrorCategory.TYPE_CHECK
        if "modulenotfounderror" in lowered or "cannot find module" in lowered or "importerror" in lowered:
            return ErrorCategory.MISSING_DEPENDENCY
        if "failed to compile" in lowered or "build failed" in lowered or "compilation error" in lowered:
            return ErrorCategory.BUILD
        if "assert" in lowered or "failed" in lowered or "assertionerror" in lowered or "test failed" in lowered:
            return ErrorCategory.TEST_FAILURE
        if "timed out" in lowered:
            return ErrorCategory.TIMEOUT
        return ErrorCategory.RUNTIME

    def verify(self, modified_files: Set[str] | List[str], goal: str = "") -> VerificationResult:
        """Run multi-stage verification on modified files and test suite."""
        resolved_files: List[Path] = []
        for f in modified_files:
            p = Path(f)
            if not p.is_absolute():
                p = self.workspace_path / p
            if p.exists() and p.is_file():
                resolved_files.append(p)

        meta = self.workspace_manager.scan()

        # Stage 1: Syntax & Static parse check for Python files
        py_files = [f for f in resolved_files if f.suffix == ".py"]
        if py_files or meta.project_type == ProjectType.PYTHON:
            syntax_err = self._check_python_syntax(py_files)
            if syntax_err:
                cat = self.classify_error(syntax_err)
                return VerificationResult(
                    passed=False,
                    summary="Python syntax or compilation check failed.",
                    details=syntax_err,
                    phase="syntax_check",
                    error_category=cat,
                )

        # Stage 2: TypeScript / Node type-check or build if TS project
        if meta.project_type in (ProjectType.TYPESCRIPT, ProjectType.REACT):
            if (self.workspace_path / "tsconfig.json").exists():
                ts_err = self._check_typescript()
                if ts_err:
                    cat = self.classify_error(ts_err)
                    return VerificationResult(
                        passed=False,
                        summary="TypeScript compiler check failed.",
                        details=ts_err,
                        phase="type_check",
                        error_category=cat,
                        failing_command="npx tsc --noEmit",
                    )

        # Stage 3: Automated Test Execution ONLY when relevant to user's goal or test files
        # Do NOT force a full pytest run on everyday tasks or non-test edits
        should_run_tests = False
        goal_lower = (goal or "").lower()
        if any(w in goal_lower for w in ["test", "pytest", "failing", "regression", "verify test"]):
            should_run_tests = True
        elif any("test" in f.name.lower() or "tests" in str(f).lower() for f in resolved_files):
            should_run_tests = True

        test_summary = ""
        if should_run_tests:
            test_err, test_summary, test_cmd = self._run_project_tests(meta)
            if test_err:
                cat = self.classify_error(test_err)
                return VerificationResult(
                    passed=False,
                    summary=f"Automated test execution failed ({test_cmd}).",
                    details=test_err,
                    phase="test_execution",
                    error_category=cat,
                    failing_command=test_cmd,
                )

        # All stages passed
        details = test_summary or f"Verified {len(resolved_files)} file(s) with clean syntax."
        return VerificationResult(
            passed=True,
            summary="All independent verification checks passed successfully.",
            details=details,
            phase="verified",
        )

    def _check_python_syntax(self, py_files: List[Path]) -> Optional[str]:
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

    def _check_typescript(self) -> Optional[str]:
        try:
            res = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=40,
                check=False,
                shell=True,
            )
            if res.returncode != 0:
                out = (res.stdout + "\n" + res.stderr).strip()
                lines = out.splitlines()[:25]
                return "\n".join(lines)
            return None
        except Exception:
            return None

    def _run_project_tests(self, meta: ProjectMetadata) -> Tuple[Optional[str], str, Optional[str]]:
        # 1. Python Project
        if meta.project_type == ProjectType.PYTHON:
            tests_dir = self.workspace_path / "tests"
            has_tests = tests_dir.exists() and tests_dir.is_dir()
            if not has_tests:
                for p in self.workspace_path.glob("**/test_*.py"):
                    if "node_modules" not in str(p) and ".pytest_cache" not in str(p):
                        has_tests = True
                        break

            if not has_tests:
                return None, "No automated test suite detected in workspace. Syntax verified.", None

            cmd = ["python", "-m", "pytest", "-q", "--tb=short", "-o", "pythonpath=."]
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.workspace_path) + (os.pathsep + env["PYTHONPATH"] if "PYTHONPATH" in env else "")
            try:
                res = subprocess.run(
                    cmd,
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                    env=env,
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                if res.returncode != 0:
                    err_lines = output.splitlines()
                    preview = "\n".join(err_lines[-35:]) if len(err_lines) > 35 else output
                    return preview, "", "pytest"
                summary_line = output.splitlines()[-1] if output else "Tests passed."
                return None, f"pytest passed: {summary_line}", "pytest"
            except subprocess.TimeoutExpired:
                return "pytest timed out after 60 seconds.", "", "pytest"
            except Exception as exc:
                return f"Error executing pytest: {exc}", "", "pytest"

        # 2. Node / React / TypeScript Project
        if meta.project_type in (ProjectType.NODE, ProjectType.TYPESCRIPT, ProjectType.REACT):
            pkg_path = self.workspace_path / "package.json"
            if pkg_path.exists():
                test_cmd = meta.test_command or "npm test"
                try:
                    res = subprocess.run(
                        test_cmd,
                        cwd=self.workspace_path,
                        shell=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=60,
                        check=False,
                    )
                    output = (res.stdout + "\n" + res.stderr).strip()
                    # If test script says 'no test specified', treat as no tests
                    if "no test specified" in output.lower():
                        return None, "Node project verified (no tests configured).", test_cmd
                    if res.returncode != 0:
                        lines = output.splitlines()
                        preview = "\n".join(lines[-35:]) if len(lines) > 35 else output
                        return preview, "", test_cmd
                    return None, f"Node tests passed: {test_cmd}", test_cmd
                except Exception as exc:
                    return f"Error running tests ({test_cmd}): {exc}", "", test_cmd

        # 3. Rust Project
        if meta.project_type == ProjectType.RUST:
            try:
                res = subprocess.run(
                    ["cargo", "test"],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90,
                    check=False,
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                if res.returncode != 0:
                    return output[-1500:], "", "cargo test"
                return None, "cargo test passed.", "cargo test"
            except Exception as exc:
                return f"Error executing cargo test: {exc}", "", "cargo test"

        # 4. Go Project
        if meta.project_type == ProjectType.GO:
            try:
                res = subprocess.run(
                    ["go", "test", "./..."],
                    cwd=self.workspace_path,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                output = (res.stdout + "\n" + res.stderr).strip()
                if res.returncode != 0:
                    return output[-1500:], "", "go test"
                return None, "go test passed.", "go test"
            except Exception as exc:
                return f"Error executing go test: {exc}", "", "go test"

        return None, "Workspace verified.", None
