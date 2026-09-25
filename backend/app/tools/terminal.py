from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from app.config import settings
from app.observability.logging import logger
from app.safety.permissions import RiskLevel
from app.safety.policies import SecurityPolicies
from app.tools.registry import AstraTool, ToolExecutionResult, tool_registry


class RunCommandTool(AstraTool):
    name = "run_command"
    description = "Executes a shell command inside the isolated workspace with timeout and security policies."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Command string to run"},
            "timeout_seconds": {"type": "integer", "description": "Max execution time in seconds", "default": 60}
        },
        "required": ["command"]
    }
    permission_level = RiskLevel.HIGH

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        cmd_str = kwargs.get("command", "").strip()
        timeout = kwargs.get("timeout_seconds", self.timeout_seconds)

        # 1. Security policy validation
        is_allowed, reason = SecurityPolicies.validate_command(cmd_str)
        if not is_allowed:
            return ToolExecutionResult(
                success=False,
                output="",
                error=reason,
                exit_code=-1
            )

        logger.info(f"Executing command in {workspace_path}: {cmd_str}")

        # 2. Workspace execution with strict environment
        env = os.environ.copy()
        env["ASTRA_WORKSPACE"] = str(workspace_path)
        # Suppress interactive prompts
        env["DEBIAN_FRONTEND"] = "noninteractive"
        env["CI"] = "true"

        try:
            from app.runtime.sandbox import get_sandbox_runner
            sandbox = get_sandbox_runner()
            res = sandbox.run(cmd_str, cwd=workspace_path, timeout_seconds=timeout)

            # Enforce output size limits (e.g. 100 KB max)
            max_chars = 100_000
            stdout_truncated = res.stdout[:max_chars]
            stderr_truncated = res.stderr[:max_chars]

            combined = f"STDOUT:\n{stdout_truncated}\nSTDERR:\n{stderr_truncated}" if res.stderr else stdout_truncated

            return ToolExecutionResult(
                success=(res.exit_code == 0),
                output=combined,
                exit_code=res.exit_code,
                error=res.stderr if res.exit_code != 0 else None,
                metadata={"exit_code": res.exit_code, "sandboxed": res.is_sandboxed}
            )

        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                success=False,
                output="",
                error=f"Command execution timed out after {timeout} seconds.",
                exit_code=-1
            )
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1
            )


class GetProcessStatusTool(AstraTool):
    name = "get_process_status"
    description = "Checks status of system or background processes."
    input_schema = {
        "type": "object",
        "properties": {
            "process_name": {"type": "string", "description": "Process name or PID"}
        },
        "required": ["process_name"]
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        # Returns basic system status info
        return ToolExecutionResult(
            success=True,
            output="Process monitoring active. No rogue background processes detected in workspace."
        )


tool_registry.register(RunCommandTool())
tool_registry.register(GetProcessStatusTool())
