from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


def _run_git_cmd(workspace_path: Path, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=workspace_path,
        capture_output=True,
        text=True,
        check=False
    )


class BranchManager:
    """
    AUTONOMOUS BRANCH MANAGER (Phase 4.1):
    Manages isolated Git feature branches for ASTRA tasks.
    Guarantees tasks run on dedicated branches, protecting the main/master branch.
    """

    @classmethod
    def slugify(cls, text: str, max_length: int = 30) -> str:
        """Converts goal into a safe, alphanumeric git branch slug."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return text[:max_length].rstrip("-") or "patch"

    @classmethod
    def generate_branch_name(cls, task_id: str, goal: str) -> str:
        """Constructs standardized branch name: astra/{task_id[:12]}-{slug}."""
        clean_id = task_id.replace("task-", "")[:8]
        slug = cls.slugify(goal)
        return f"astra/{clean_id}-{slug}"

    @classmethod
    def ensure_git_repo(cls, workspace_path: Path) -> bool:
        """Ensures workspace is a valid git repository, initializing one if needed."""
        git_dir = workspace_path / ".git"
        if not git_dir.exists():
            res = _run_git_cmd(workspace_path, ["init"])
            if res.returncode == 0:
                # Configure basic user identity for commit operations
                _run_git_cmd(workspace_path, ["config", "user.name", "ASTRA Autonomous Agent"])
                _run_git_cmd(workspace_path, ["config", "user.email", "astra@agent.internal"])
                return True
            return False
        return True

    @classmethod
    def get_current_branch(cls, workspace_path: Path) -> str:
        """Returns the current active branch name."""
        cls.ensure_git_repo(workspace_path)
        res = _run_git_cmd(workspace_path, ["rev-parse", "--abbrev-ref", "HEAD"])
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
        return "main"

    @classmethod
    def create_feature_branch(
        cls,
        workspace_path: Path,
        task_id: str,
        goal: str,
        base_branch: Optional[str] = None
    ) -> str:
        """
        Creates and checks out an isolated feature branch for the task.
        """
        cls.ensure_git_repo(workspace_path)
        branch_name = cls.generate_branch_name(task_id, goal)

        current = cls.get_current_branch(workspace_path)
        if current == branch_name:
            logger.info(f"Already on target branch: {branch_name}")
            return branch_name

        # If base branch requested, checkout base branch first
        if base_branch and base_branch != current:
            _run_git_cmd(workspace_path, ["checkout", base_branch])

        # Create and checkout new branch
        res = _run_git_cmd(workspace_path, ["checkout", "-b", branch_name])
        if res.returncode != 0:
            # Branch might already exist, switch to it
            res_switch = _run_git_cmd(workspace_path, ["checkout", branch_name])
            if res_switch.returncode != 0:
                logger.warning(f"Could not checkout branch {branch_name}: {res.stderr}")
                return current

        logger.info(f"[{task_id}] Created and switched to isolated feature branch: {branch_name}")
        return branch_name

    @classmethod
    def checkout_branch(cls, workspace_path: Path, branch_name: str) -> bool:
        """Checks out an existing branch."""
        cls.ensure_git_repo(workspace_path)
        res = _run_git_cmd(workspace_path, ["checkout", branch_name])
        return res.returncode == 0

    @classmethod
    def list_branches(cls, workspace_path: Path) -> List[str]:
        """Lists all local branches."""
        cls.ensure_git_repo(workspace_path)
        res = _run_git_cmd(workspace_path, ["branch", "--list"])
        if res.returncode == 0:
            branches = []
            for line in res.stdout.splitlines():
                b = line.replace("*", "").strip()
                if b:
                    branches.append(b)
            return branches
        return []

    @classmethod
    def delete_branch(cls, workspace_path: Path, branch_name: str, force: bool = False) -> bool:
        """Deletes a local branch (cannot be the current branch)."""
        cls.ensure_git_repo(workspace_path)
        flag = "-D" if force else "-d"
        res = _run_git_cmd(workspace_path, ["branch", flag, branch_name])
        return res.returncode == 0
