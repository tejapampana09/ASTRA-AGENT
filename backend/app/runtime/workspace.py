from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.config import settings
from app.observability.logging import logger


class WorkspaceSecurityError(Exception):
    """Raised when an operation attempts to escape the isolated workspace boundaries."""
    pass


@dataclass
class IsolatedWorkspace:
    task_id: str
    path: Path
    is_git_repo: bool = False

    def validate_path(self, relative_or_absolute_path: str | Path) -> Path:
        """
        Validate that a given path stays strictly inside the workspace boundary.
        Prevents directory traversal attacks (e.g., ../../etc/passwd).
        """
        target = Path(relative_or_absolute_path)
        if not target.is_absolute():
            target = (self.path / target).resolve()
        else:
            target = target.resolve()

        try:
            target.relative_to(self.path.resolve())
        except ValueError:
            raise WorkspaceSecurityError(
                f"Security violation: path '{relative_or_absolute_path}' is outside isolated workspace '{self.path}'"
            )
        return target

    def is_dirty(self) -> bool:
        """Check if git working tree contains uncommitted changes."""
        if not self.is_git_repo:
            return False
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=False
            )
            return len(res.stdout.strip()) > 0
        except Exception:
            return False

    def get_modified_files(self) -> List[str]:
        """Return list of files that have actually been created, modified, or deleted."""
        if not self.is_git_repo:
            return []
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=False
            )
            files = []
            for line in res.stdout.strip().splitlines():
                if not line.strip():
                    continue
                file_part = line[3:].strip()
                if " -> " in file_part:
                    file_part = file_part.split(" -> ")[1].strip()
                file_part = file_part.strip('"\'')
                files.append(file_part.replace("\\", "/"))
            return sorted(files)
        except Exception as e:
            logger.warning(f"Failed to get modified files from git: {e}")
            return []

    def get_git_diff(self) -> str:
        """Return git diff of changes within the workspace."""
        if not self.is_git_repo:
            return ""
        try:
            # Mark untracked files with intent-to-add so git diff displays them
            subprocess.run(["git", "add", "-N", "."], cwd=self.path, capture_output=True, check=False)
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=False
            )
            if not res.stdout.strip():
                res_unstaged = subprocess.run(
                    ["git", "diff"],
                    cwd=self.path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                return res_unstaged.stdout
            return res.stdout
        except Exception as e:
            logger.warning(f"Failed to get git diff: {e}")
            return ""

    def list_files(self, relative_dir: str = ".") -> List[str]:
        """List files relative to workspace root, excluding git/cache metadata."""
        start_dir = self.validate_path(relative_dir)
        files = []
        for root, dirs, filenames in os.walk(start_dir):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".venv"}]
            for fname in filenames:
                full_path = Path(root) / fname
                rel_path = full_path.relative_to(self.path)
                files.append(str(rel_path).replace("\\", "/"))
        return sorted(files)

    def cleanup(self) -> None:
        """Clean up the workspace directory."""
        if self.path.exists():
            try:
                shutil.rmtree(self.path, ignore_errors=True)
                logger.info(f"Cleaned up workspace at {self.path}")
            except Exception as e:
                logger.error(f"Error during workspace cleanup: {e}")


class WorkspaceManager:
    """Manages creation, initialization, and lifecycle of isolated task workspaces."""

    def __init__(self, base_dir: Optional[str | Path] = None):
        self.base_dir = Path(base_dir or settings.WORKSPACE_BASE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(
        self,
        task_id: str,
        source_repo_path: Optional[str | Path] = None,
        init_git: bool = True
    ) -> IsolatedWorkspace:
        """
        Creates an isolated workspace for a given task.
        If source_repo_path is provided, copies its content into the workspace.
        """
        workspace_dir = (self.base_dir / task_id).resolve()
        if workspace_dir.exists():
            logger.info(f"Workspace already exists for task {task_id}, cleaning up first.")
            shutil.rmtree(workspace_dir, ignore_errors=True)

        workspace_dir.mkdir(parents=True, exist_ok=True)

        is_git = False
        if source_repo_path:
            src = Path(source_repo_path).resolve()
            if src.exists() and src.is_dir():
                logger.info(f"Copying source repo {src} into workspace {workspace_dir}")
                for item in src.iterdir():
                    if item.name in {".venv", "__pycache__", ".git"}:
                        continue
                    dest = workspace_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

        if init_git:
            try:
                subprocess.run(
                    ["git", "init"],
                    cwd=workspace_dir,
                    capture_output=True,
                    check=False
                )
                subprocess.run(
                    ["git", "config", "user.name", "ASTRA Agent"],
                    cwd=workspace_dir,
                    capture_output=True,
                    check=False
                )
                subprocess.run(
                    ["git", "config", "user.email", "astra-agent@astra2.local"],
                    cwd=workspace_dir,
                    capture_output=True,
                    check=False
                )
                # Initial commit so diffs against HEAD work
                subprocess.run(["git", "add", "-A"], cwd=workspace_dir, capture_output=True, check=False)
                subprocess.run(
                    ["git", "commit", "-m", "Initial commit from repository source", "--allow-empty"],
                    cwd=workspace_dir,
                    capture_output=True,
                    check=False
                )
                is_git = True
            except Exception as e:
                logger.warning(f"Could not initialize git repository in workspace: {e}")

        logger.info(f"Created isolated workspace for task {task_id} at {workspace_dir}")
        return IsolatedWorkspace(task_id=task_id, path=workspace_dir, is_git_repo=is_git)
