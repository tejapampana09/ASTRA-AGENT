from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict

from app.observability.logging import logger
from app.safety.permissions import RiskLevel
from app.tools.registry import AstraTool, ToolExecutionResult, tool_registry


def _run_git(workspace_path: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=workspace_path,
        capture_output=True,
        text=True,
        check=False
    )


class GitStatusTool(AstraTool):
    name = "git_status"
    description = "Checks status of git working tree."
    input_schema = {"type": "object", "properties": {}}
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        res = _run_git(workspace_path, ["status", "--porcelain"])
        return ToolExecutionResult(success=True, output=res.stdout or "Working tree clean.")


class GitDiffTool(AstraTool):
    name = "git_diff"
    description = "Inspects git diff of current modifications."
    input_schema = {
        "type": "object",
        "properties": {
            "target": {"type": "string", "description": "Target ref (default HEAD)", "default": "HEAD"}
        }
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        target = kwargs.get("target", "HEAD")
        res = _run_git(workspace_path, ["diff", target])
        diff = res.stdout
        if not diff.strip():
            # Check untracked / uncommitted
            res_unstaged = _run_git(workspace_path, ["diff"])
            diff = res_unstaged.stdout
        return ToolExecutionResult(success=True, output=diff or "No changes detected.")


class GitLogTool(AstraTool):
    name = "git_log"
    description = "Retrieves commit log history."
    input_schema = {
        "type": "object",
        "properties": {
            "max_count": {"type": "integer", "description": "Number of commits to return", "default": 10}
        }
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        n = str(kwargs.get("max_count", 10))
        res = _run_git(workspace_path, ["log", f"-n{n}", "--oneline"])
        return ToolExecutionResult(success=True, output=res.stdout)


class GitBranchTool(AstraTool):
    name = "git_branch"
    description = "Lists or creates git branches."
    input_schema = {
        "type": "object",
        "properties": {
            "branch_name": {"type": "string", "description": "New branch name (optional)"}
        }
    }
    permission_level = RiskLevel.MEDIUM

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        branch = kwargs.get("branch_name")
        if branch:
            res = _run_git(workspace_path, ["checkout", "-b", branch])
            return ToolExecutionResult(success=(res.returncode == 0), output=res.stdout or f"Created branch {branch}", error=res.stderr if res.returncode != 0 else None)
        res = _run_git(workspace_path, ["branch", "-a"])
        return ToolExecutionResult(success=True, output=res.stdout)


class GitCheckoutTool(AstraTool):
    name = "git_checkout"
    description = "Checks out an existing git branch."
    input_schema = {
        "type": "object",
        "properties": {
            "branch": {"type": "string", "description": "Branch name"}
        },
        "required": ["branch"]
    }
    permission_level = RiskLevel.MEDIUM

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        branch = kwargs.get("branch", "")
        res = _run_git(workspace_path, ["checkout", branch])
        return ToolExecutionResult(success=(res.returncode == 0), output=res.stdout, error=res.stderr if res.returncode != 0 else None)


class GitCommitTool(AstraTool):
    name = "git_commit"
    description = "Stages files and creates a git commit."
    input_schema = {
        "type": "object",
        "properties": {
            "message": {"type": "string", "description": "Commit message"}
        },
        "required": ["message"]
    }
    permission_level = RiskLevel.MEDIUM

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        msg = kwargs.get("message", "ASTRA automated commit")
        # Add all
        _run_git(workspace_path, ["add", "-A"])
        res = _run_git(workspace_path, ["commit", "-m", msg])
        return ToolExecutionResult(
            success=(res.returncode == 0),
            output=res.stdout,
            error=res.stderr if res.returncode != 0 else None
        )


tool_registry.register(GitStatusTool())
tool_registry.register(GitDiffTool())
tool_registry.register(GitLogTool())
tool_registry.register(GitBranchTool())
tool_registry.register(GitCheckoutTool())
tool_registry.register(GitCommitTool())
