from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.observability.logging import logger


@dataclass
class LintVerificationReport:
    status: str  # "passed", "failed", "skipped"
    command: str = ""
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "status": self.status,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout[:1000],
            "stderr": self.stderr[:1000],
        }


class LintRunner:
    """Verifies linting and formatting compliance."""

    @classmethod
    def run_lint(cls, workspace_path: Path, timeout_seconds: int = 30) -> LintVerificationReport:
        # Check flake8 or ruff
        try:
            res = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "."],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            return LintVerificationReport(
                status="passed" if res.returncode == 0 else "failed",
                command="ruff check .",
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr
            )
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.debug(f"Ruff check not available or failed: {e}")

        # Check flake8
        try:
            res = subprocess.run(
                [sys.executable, "-m", "flake8", "."],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            return LintVerificationReport(
                status="passed" if res.returncode == 0 else "failed",
                command="flake8 .",
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr
            )
        except Exception:
            pass

        return LintVerificationReport(status="skipped", stdout="No linter configured or available.")
