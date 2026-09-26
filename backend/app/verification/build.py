from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from app.observability.logging import logger


@dataclass
class BuildVerificationReport:
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


class BuildRunner:
    """Verifies that the repository code compiles/builds cleanly without syntax/type breakages."""

    @classmethod
    def run_build(
        cls,
        workspace_path: Path,
        timeout_seconds: int = 60,
        files_changed: Optional[List[str]] = None,
    ) -> BuildVerificationReport:
        # If files_changed is provided, verify only changed Python files
        if files_changed is not None:
            py_files = [
                f for f in files_changed
                if f.endswith(".py") and (workspace_path / f).exists()
            ]
            if not py_files:
                return BuildVerificationReport(status="passed", stdout="No compiled language files modified.")

            target_args = [str((workspace_path / f).resolve()) for f in py_files]
            cmd = [sys.executable, "-m", "py_compile"] + target_args
            try:
                res = subprocess.run(
                    cmd,
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False
                )
                status = "passed" if res.returncode == 0 else "failed"
                return BuildVerificationReport(
                    status=status,
                    command=" ".join(cmd),
                    exit_code=res.returncode,
                    stdout=res.stdout,
                    stderr=res.stderr
                )
            except Exception as e:
                logger.error(f"py_compile build verification failed: {e}")
                return BuildVerificationReport(status="failed", stderr=str(e))

        # Check Node.js package.json build script
        if (workspace_path / "package.json").exists() and files_changed and any(f.endswith((".js", ".ts", ".jsx", ".tsx")) for f in files_changed):
            cmd = ["npm", "run", "build"]
            try:
                res = subprocess.run(
                    cmd,
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False
                )
                status = "passed" if res.returncode == 0 else "failed"
                return BuildVerificationReport(
                    status=status,
                    command=" ".join(cmd),
                    exit_code=res.returncode,
                    stdout=res.stdout,
                    stderr=res.stderr
                )
            except Exception as e:
                return BuildVerificationReport(status="failed", stderr=str(e))

        return BuildVerificationReport(status="skipped", stdout="No build step required.")

