from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


@dataclass
class TestFailureDetail:
    test_name: str
    error_message: str
    traceback: str


@dataclass
class TestVerificationReport:
    status: str  # "passed", "failed", "no_tests_found", "error"
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    total: int = 0
    duration_seconds: float = 0.0
    command: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    failures: List[TestFailureDetail] = field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        return self.status == "passed" and self.failed == 0 and self.errors == 0 and self.passed > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "total": self.total,
            "duration_seconds": self.duration_seconds,
            "command": self.command,
            "exit_code": self.exit_code,
            "failures": [
                {"test_name": f.test_name, "error": f.error_message, "traceback": f.traceback[:500]}
                for f in self.failures
            ]
        }


class TestRunner:
    """Autonomous test runner capable of executing and parsing test outputs."""

    @staticmethod
    def detect_test_command(workspace_path: Path) -> Optional[List[str]]:
        """
        Detect the appropriate test runner for the workspace.
        Ensures test commands are only returned when real tests or explicit configurations exist.
        """
        # 1. Search for actual Python test files
        python_test_files = []
        for p in workspace_path.rglob("*"):
            if any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                continue
            if p.is_file() and (p.name.startswith("test_") or p.name.endswith("_test.py")):
                python_test_files.append(p)

        has_explicit_pytest_cfg = (workspace_path / "pytest.ini").exists() or (
            (workspace_path / "pyproject.toml").exists()
            and "[tool.pytest" in (workspace_path / "pyproject.toml").read_text(encoding="utf-8", errors="replace")
        )

        if python_test_files or has_explicit_pytest_cfg:
            return [sys.executable, "-m", "pytest", "-v"]

        # 2. Check Node.js package.json with a valid test script
        pkg_file = workspace_path / "package.json"
        if pkg_file.exists():
            try:
                import json
                pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
                test_script = pkg_data.get("scripts", {}).get("test", "")
                if test_script and "no test specified" not in test_script:
                    return ["npm", "test"]
            except Exception:
                pass

        if (workspace_path / "Cargo.toml").exists() and list(workspace_path.glob("tests/*.rs")):
            return ["cargo", "test"]

        if (workspace_path / "go.mod").exists() and list(workspace_path.glob("**/*_test.go")):
            return ["go", "test", "./..."]

        return None

    @classmethod
    def run_tests(
        cls,
        workspace_path: Path,
        custom_command: Optional[List[str]] = None,
        timeout_seconds: int = 60
    ) -> TestVerificationReport:
        cmd = custom_command or cls.detect_test_command(workspace_path)
        if not cmd:
            return TestVerificationReport(
                status="no_tests_found",
                stdout="No test framework or test files detected in repository."
            )

        cmd_str = " ".join(cmd)
        logger.info(f"Running verification tests in {workspace_path} via sandbox: {cmd_str}")

        try:
            from app.runtime.sandbox import get_sandbox_runner
            sandbox = get_sandbox_runner()
            res = sandbox.run(cmd, cwd=workspace_path, timeout_seconds=timeout_seconds)

            if res.timeout_exceeded:
                return TestVerificationReport(
                    status="error",
                    command=cmd_str,
                    exit_code=-1,
                    stderr=f"Test execution timed out after {timeout_seconds} seconds"
                )

            report = cls._parse_pytest_output(res.stdout, res.stderr, res.exit_code, cmd_str)
            return report

        except Exception as e:
            logger.error(f"Failed to execute tests: {e}")
            return TestVerificationReport(
                status="error",
                command=cmd_str,
                exit_code=-1,
                stderr=str(e)
            )

    @classmethod
    def _parse_pytest_output(
        cls,
        stdout: str,
        stderr: str,
        exit_code: int,
        cmd_str: str
    ) -> TestVerificationReport:
        passed = 0
        failed = 0
        errors = 0
        skipped = 0

        # Pytest summary line regex: e.g. "=== 5 passed, 1 failed in 0.23s ==="
        match_passed = re.search(r"(\d+)\s+passed", stdout)
        if match_passed:
            passed = int(match_passed.group(1))

        match_failed = re.search(r"(\d+)\s+failed", stdout)
        if match_failed:
            failed = int(match_failed.group(1))

        match_errors = re.search(r"(\d+)\s+error", stdout)
        if match_errors:
            errors = int(match_errors.group(1))

        match_skipped = re.search(r"(\d+)\s+skipped", stdout)
        if match_skipped:
            skipped = int(match_skipped.group(1))

        total = passed + failed + errors + skipped

        # Parse specific test failures if present
        failures: List[TestFailureDetail] = []
        if failed > 0 or errors > 0:
            failure_blocks = re.findall(r"_{3,}\s+([^\n]+)\s+_{3,}(.*?)(?=\n_{3,}|\n={3,}|$)", stdout, re.DOTALL)
            for test_name, block in failure_blocks:
                failures.append(
                    TestFailureDetail(
                        test_name=test_name.strip(),
                        error_message=block.strip().splitlines()[-1] if block.strip() else "Test failed",
                        traceback=block.strip()
                    )
                )

        status = "passed" if (exit_code == 0 and (passed > 0 or total == 0)) else "failed"
        if exit_code != 0 and total == 0:
            status = "error"

        return TestVerificationReport(
            status=status,
            passed=passed,
            failed=failed,
            errors=errors,
            skipped=skipped,
            total=total,
            command=cmd_str,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            failures=failures,
        )
