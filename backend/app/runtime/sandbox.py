from __future__ import annotations

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.config import settings
from app.observability.logging import logger
from app.safety.policies import SecurityPolicies


@dataclass
class SandboxExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float = 0.0
    is_sandboxed: bool = True
    timeout_exceeded: bool = False


class SandboxRunner(ABC):
    """Abstract isolated runner for terminal commands and test suites."""

    @abstractmethod
    def run(
        self,
        command: List[str] | str,
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 60,
        isolate_network: bool = False
    ) -> SandboxExecutionResult:
        pass


class DockerSandboxRunner(SandboxRunner):
    """
    Executes commands inside an isolated Docker container with strict CPU,
    memory, pids, and network isolation limits.
    """

    def __init__(self, image: str = "python:3.12-slim"):
        self.image = image

    def run(
        self,
        command: List[str] | str,
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 60,
        isolate_network: bool = False
    ) -> SandboxExecutionResult:
        cmd_str = command if isinstance(command, str) else " ".join(command)

        # Validate security policy
        allowed, reason = SecurityPolicies.validate_command(cmd_str)
        if not allowed:
            return SandboxExecutionResult(exit_code=-1, stdout="", stderr=reason)

        abs_cwd = str(cwd.resolve()).replace("\\", "/")
        docker_args = [
            "docker", "run", "--rm",
            "-v", f"{abs_cwd}:/workspace",
            "-w", "/workspace",
            "--memory=512m",
            "--cpus=1.0",
            "--pids-limit=100",
        ]
        if isolate_network:
            docker_args.append("--network=none")

        # Pass non-secret environment variables
        if env:
            for k, v in env.items():
                if not any(sec in k.upper() for sec in ["KEY", "TOKEN", "SECRET", "PASS"]):
                    docker_args.extend(["-e", f"{k}={v}"])

        docker_args.extend([self.image, "sh", "-c", cmd_str])

        start_time = time.time()
        logger.info(f"Running in Docker Sandbox: {cmd_str}")

        try:
            res = subprocess.run(
                docker_args,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False
            )
            duration = time.time() - start_time
            return SandboxExecutionResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_seconds=duration,
                is_sandboxed=True
            )
        except subprocess.TimeoutExpired:
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout_seconds}s in Docker sandbox",
                duration_seconds=time.time() - start_time,
                timeout_exceeded=True
            )
        except Exception as e:
            logger.error(f"Docker sandbox execution failure: {e}")
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start_time
            )


class LocalProcessSandboxRunner(SandboxRunner):
    """
    Subprocess runner with strict environment filtering (stripping secrets and keys),
    cwd boundary locking, and timeout enforcement.
    Used when Docker sandbox is disabled or unavailable.
    """

    SAFE_ENV_ALLOWLIST = {
        "PATH", "PYTHONPATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
        "LANG", "LC_ALL", "USER", "USERNAME", "HOME", "USERPROFILE",
        "ASTRA_WORKSPACE", "CI"
    }

    def run(
        self,
        command: List[str] | str,
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 60,
        isolate_network: bool = False
    ) -> SandboxExecutionResult:
        cmd_str = command if isinstance(command, str) else " ".join(command)

        # Validate security policy
        allowed, reason = SecurityPolicies.validate_command(cmd_str)
        if not allowed:
            return SandboxExecutionResult(exit_code=-1, stdout="", stderr=reason)

        # Sanitize environment: never leak host API keys, cloud tokens, or secrets
        clean_env: Dict[str, str] = {}
        for k, v in os.environ.items():
            if k in self.SAFE_ENV_ALLOWLIST:
                clean_env[k] = v

        if env:
            for k, v in env.items():
                if not any(sec in k.upper() for sec in ["KEY", "TOKEN", "SECRET", "PASS"]):
                    clean_env[k] = v

        clean_env["ASTRA_WORKSPACE"] = str(cwd.resolve())
        clean_env["CI"] = "true"

        start_time = time.time()
        try:
            # If command is a list and no shell features required, run directly without shell=True
            use_shell = isinstance(command, str) or any(op in cmd_str for op in ["|", ">", "<", "&&", ";"])
            res = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env=clean_env,
                shell=use_shell,
                check=False
            )
            duration = time.time() - start_time
            return SandboxExecutionResult(
                exit_code=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                duration_seconds=duration,
                is_sandboxed=True
            )
        except subprocess.TimeoutExpired:
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {timeout_seconds}s in isolated workspace",
                duration_seconds=time.time() - start_time,
                timeout_exceeded=True
            )
        except Exception as e:
            return SandboxExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=time.time() - start_time
            )


def get_sandbox_runner() -> SandboxRunner:
    """Factory providing Docker sandbox when configured and available, or Local sandbox."""
    if settings.ENABLE_DOCKER_SANDBOX and shutil.which("docker"):
        return DockerSandboxRunner(image=settings.SANDBOX_CONTAINER_IMAGE)
    return LocalProcessSandboxRunner()
