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
        # 1. Targeted check on modified files if specified
        if files_changed is not None:
            py_files = [
                f for f in files_changed
                if f.endswith(".py") and (workspace_path / f).exists()
            ]
            if not py_files:
                # If only non-Python files were changed and no Node build required
                if not ((workspace_path / "package.json").exists() and any(f.endswith((".js", ".ts", ".jsx", ".tsx")) for f in files_changed)):
                    return BuildVerificationReport(status="passed", stdout="No compiled language files modified.")
            else:
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
                    if res.returncode != 0:
                        return BuildVerificationReport(
                            status="failed",
                            command=" ".join(cmd),
                            exit_code=res.returncode,
                            stdout=res.stdout,
                            stderr=res.stderr
                        )
                except Exception as e:
                    logger.error(f"py_compile build verification failed: {e}")
                    return BuildVerificationReport(status="failed", stderr=str(e))

                # For simple single-file modifications with no project manifests, targeted check is sufficient
                is_simple_task = len(py_files) <= 1 and not any(
                    (workspace_path / marker).exists()
                    for marker in ["pyproject.toml", "setup.py", "requirements.txt"]
                )
                if is_simple_task:
                    return BuildVerificationReport(
                        status="passed",
                        command=" ".join(cmd),
                        exit_code=0,
                        stdout=f"Targeted build verification passed for {', '.join(py_files)}.",
                        stderr=""
                    )

        # 2. Broader project-level build verification (when files_changed is None or multiple files / project task)
        has_py = any(workspace_path.glob("*.py")) or (workspace_path / "src").is_dir() or (workspace_path / "app").is_dir()
        if has_py:
            cmd = [
                sys.executable,
                "-m",
                "compileall",
                "-q",
                "-x",
                r"(\.venv|venv|node_modules|\.git|\.tox|\.mypy_cache)",
                str(workspace_path.resolve())
            ]
            try:
                res = subprocess.run(
                    cmd,
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    check=False
                )
                if res.returncode != 0:
                    return BuildVerificationReport(
                        status="failed",
                        command=" ".join(cmd),
                        exit_code=res.returncode,
                        stdout=res.stdout,
                        stderr=res.stderr
                    )
                return BuildVerificationReport(
                    status="passed",
                    command=" ".join(cmd),
                    exit_code=0,
                    stdout="Project build and compilation passed.",
                    stderr=""
                )
            except Exception as e:
                logger.error(f"Project compileall verification failed: {e}")
                return BuildVerificationReport(status="failed", stderr=str(e))

        # Check Node.js package.json build script
        if (workspace_path / "package.json").exists() and (files_changed is None or any(f.endswith((".js", ".ts", ".jsx", ".tsx")) for f in files_changed)):
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

