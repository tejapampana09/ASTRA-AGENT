from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.observability.logging import logger


def _safe_rmtree(path: Path) -> None:
    """Safely delete a directory tree, clearing read-only flags on Windows (e.g. .git objects)."""
    def _onerror(func, p, excinfo):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    if path.exists():
        try:
            shutil.rmtree(path, onerror=_onerror)
        except Exception:
            try:
                shutil.rmtree(path, ignore_errors=True)
            except Exception:
                pass


class WorkspaceSecurityError(Exception):
    """Raised when an operation attempts to escape the isolated workspace boundaries."""
    pass


@dataclass
class WorkspaceMetadata:
    task_id: str
    repo_name: str = "local_repo"
    repo_url: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_accessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_git_repo: bool = False
    initial_branch: str = "main"
    disk_usage_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WorkspaceMetadata:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class IsolatedWorkspace:
    task_id: str
    path: Path
    is_git_repo: bool = False
    metadata: Optional[WorkspaceMetadata] = None

    def __post_init__(self):
        if self.metadata is None:
            manifest_file = self.path / ".astra_workspace.json"
            if manifest_file.exists():
                try:
                    with open(manifest_file, "r", encoding="utf-8") as f:
                        self.metadata = WorkspaceMetadata.from_dict(json.load(f))
                except Exception:
                    self.metadata = WorkspaceMetadata(task_id=self.task_id, is_git_repo=self.is_git_repo)
            else:
                self.metadata = WorkspaceMetadata(task_id=self.task_id, is_git_repo=self.is_git_repo)

    def save_metadata(self) -> None:
        """Persist workspace state manifest."""
        if not self.path.exists():
            return
        manifest_file = self.path / ".astra_workspace.json"
        try:
            if self.metadata:
                self.metadata.disk_usage_bytes = self.get_disk_usage()
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(self.metadata.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist workspace metadata: {e}")

    def touch_accessed(self) -> None:
        """Update last accessed timestamp for LRU cache retention."""
        if self.metadata:
            self.metadata.last_accessed_at = datetime.now(timezone.utc).isoformat()
            self.save_metadata()

    def get_disk_usage(self) -> int:
        """Calculate total directory disk usage in bytes."""
        if not self.path.exists():
            return 0
        total = 0
        try:
            for root, _, files in os.walk(self.path):
                for f in files:
                    fp = os.path.join(root, f)
                    if not os.path.islink(fp):
                        total += os.path.getsize(fp)
        except Exception:
            pass
        return total

    def validate_path(self, relative_or_absolute_path: str | Path) -> Path:
        """
        Validate that a given path stays strictly inside the workspace boundary.
        Prevents directory traversal and symlink escape attacks.
        """
        self.touch_accessed()
        target = Path(relative_or_absolute_path)
        if not target.is_absolute():
            target = (self.path / target).resolve()
        else:
            target = target.resolve()

        resolved_root = self.path.resolve()
        try:
            target.relative_to(resolved_root)
        except ValueError:
            raise WorkspaceSecurityError(
                f"Security violation: path '{relative_or_absolute_path}' is outside isolated workspace '{self.path}'"
            )

        # Check for symlink escaping boundary
        if target.is_symlink():
            real_target = target.resolve()
            try:
                real_target.relative_to(resolved_root)
            except ValueError:
                raise WorkspaceSecurityError(
                    f"Security violation: symlink '{target}' points outside isolated workspace"
                )

        return target

    def is_dirty(self) -> bool:
        """Check if git working tree contains uncommitted changes."""
        if not self.is_git_repo:
            return False
        self.touch_accessed()
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
        self.touch_accessed()
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.path,
                capture_output=True,
                text=True,
                check=False
            )
            files = []
            for line in res.stdout.splitlines():
                if not line.strip():
                    continue
                file_part = line[2:].strip()
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
        self.touch_accessed()
        try:
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
                if fname == ".astra_workspace.json":
                    continue
                full_path = Path(root) / fname
                rel_path = full_path.relative_to(self.path)
                files.append(str(rel_path).replace("\\", "/"))
        return sorted(files)

    def cleanup(self) -> None:
        """Clean up the workspace directory."""
        if self.path.exists():
            try:
                _safe_rmtree(self.path)
                logger.info(f"Cleaned up workspace at {self.path}")
            except Exception as e:
                logger.error(f"Error during workspace cleanup: {e}")


class WorkspaceManager:
    """
    ENTERPRISE WORKSPACE & MULTI-REPO MANAGER (P4.9):
    - Concurrent task workspace isolation: every task receives a completely isolated directory
    - Multi-repository sandboxing & cloning/checkout
    - Automated garbage collection based on age (TTL), LRU, and disk quotas
    - State & metadata introspection
    """

    def __init__(self, base_dir: Optional[str | Path] = None):
        self.base_dir = Path(base_dir or settings.WORKSPACE_BASE_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(
        self,
        task_id: str,
        source_repo_path: Optional[str | Path] = None,
        repo_url: Optional[str] = None,
        branch: Optional[str] = None,
        init_git: bool = True
    ) -> IsolatedWorkspace:
        """
        Creates an isolated workspace for a given task.
        Guarantees concurrency isolation even when multiple tasks target the same repository.
        """
        workspace_dir = (self.base_dir / task_id).resolve()
        if workspace_dir.exists():
            logger.info(f"Workspace already exists for task {task_id}, cleaning up first.")
            _safe_rmtree(workspace_dir)

        workspace_dir.mkdir(parents=True, exist_ok=True)

        is_git = False
        repo_name = "default_repo"

        # Auto-detect if source_repo_path is a remote git URL
        if not repo_url and source_repo_path and (
            str(source_repo_path).strip().startswith("http://")
            or str(source_repo_path).strip().startswith("https://")
            or str(source_repo_path).strip().startswith("git@")
        ):
            repo_url = str(source_repo_path).strip()
            source_repo_path = None

        # 1. Clone remote repo if requested
        if repo_url:
            repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            clone_cmd = ["git", "clone", "--depth", "1"]
            if branch:
                clone_cmd.extend(["--branch", branch])
            clone_cmd.extend([repo_url, str(workspace_dir)])
            try:
                res = subprocess.run(clone_cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    is_git = True
                    logger.info(f"Cloned repository {repo_url} into {workspace_dir}")
                else:
                    logger.warning(f"Git clone failed (mock/offline environment fallback): {res.stderr}")
            except Exception as e:
                logger.warning(f"Error running git clone: {e}")

        # 2. Or copy local source repo if provided
        elif source_repo_path:
            src = Path(source_repo_path).resolve()
            if src.exists() and src.is_dir():
                repo_name = src.name
                logger.info(f"Copying source repo {src} into workspace {workspace_dir}")
                for item in src.iterdir():
                    if item.name in {".venv", "__pycache__", ".git"}:
                        continue
                    dest = workspace_dir / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

        # 3. Initialize Git if not already cloned
        if init_git and not is_git:
            try:
                subprocess.run(["git", "init"], cwd=workspace_dir, capture_output=True, check=False)
                subprocess.run(["git", "config", "user.name", "ASTRA Agent"], cwd=workspace_dir, capture_output=True, check=False)
                subprocess.run(["git", "config", "user.email", "astra-agent@astra2.local"], cwd=workspace_dir, capture_output=True, check=False)
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

        # 4. Save metadata manifest
        meta = WorkspaceMetadata(
            task_id=task_id,
            repo_name=repo_name,
            repo_url=repo_url,
            is_git_repo=is_git,
            initial_branch=branch or "main",
        )

        ws = IsolatedWorkspace(task_id=task_id, path=workspace_dir, is_git_repo=is_git, metadata=meta)
        ws.save_metadata()

        # Ensure internal metadata manifest is excluded from git tracking
        if is_git:
            try:
                git_exclude = workspace_dir / ".git" / "info" / "exclude"
                if git_exclude.parent.exists():
                    existing = git_exclude.read_text(encoding="utf-8") if git_exclude.exists() else ""
                    if ".astra_workspace.json" not in existing:
                        git_exclude.write_text(existing + "\n.astra_workspace.json\n", encoding="utf-8")
            except Exception:
                pass

        logger.info(f"Created isolated workspace for task {task_id} at {workspace_dir}")
        return ws

    def get_workspace(self, task_id: str) -> Optional[IsolatedWorkspace]:
        """Retrieve existing workspace if it exists on disk."""
        target_dir = (self.base_dir / task_id).resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            return None
        is_git = (target_dir / ".git").is_dir()
        return IsolatedWorkspace(task_id=task_id, path=target_dir, is_git_repo=is_git)

    def list_workspaces(self) -> List[WorkspaceMetadata]:
        """List all active workspaces and their metadata."""
        results: List[WorkspaceMetadata] = []
        if not self.base_dir.exists():
            return results

        for child in self.base_dir.iterdir():
            if child.is_dir():
                manifest = child / ".astra_workspace.json"
                if manifest.exists():
                    try:
                        with open(manifest, "r", encoding="utf-8") as f:
                            results.append(WorkspaceMetadata.from_dict(json.load(f)))
                        continue
                    except Exception:
                        pass
                # Fallback manifest for unindexed directories
                meta = WorkspaceMetadata(
                    task_id=child.name,
                    repo_name=child.name,
                    is_git_repo=(child / ".git").is_dir(),
                )
                results.append(meta)
        return results

    def cleanup_workspace(self, task_id: str) -> bool:
        """Removes an individual task workspace."""
        ws_dir = (self.base_dir / task_id).resolve()
        if ws_dir.exists():
            try:
                _safe_rmtree(ws_dir)
                if not ws_dir.exists():
                    logger.info(f"Successfully deleted workspace for task {task_id}")
                    return True
                else:
                    logger.warning(f"Workspace directory {ws_dir} still exists after deletion attempt")
                    return False
            except Exception as e:
                logger.error(f"Failed to delete workspace {ws_dir}: {e}")
                return False
        return False

    def cleanup_stale_workspaces(
        self,
        max_age_seconds: int = 86400,
        max_workspaces: Optional[int] = None,
        max_disk_bytes: Optional[int] = None,
    ) -> List[str]:
        """
        Automated garbage collection:
        1. Deletes workspaces older than max_age_seconds.
        2. If active workspaces > max_workspaces, deletes LRU workspaces.
        3. If total disk usage > max_disk_bytes, deletes LRU workspaces until under limit.
        Returns list of purged task_ids.
        """
        purged: List[str] = []
        workspaces = self.list_workspaces()
        now = datetime.now(timezone.utc)

        # 1. TTL / Max-Age Eviction
        active_remaining: List[WorkspaceMetadata] = []
        for ws_meta in workspaces:
            try:
                created_dt = datetime.fromisoformat(ws_meta.created_at)
                age = (now - created_dt).total_seconds()
            except Exception:
                age = 0

            if age > max_age_seconds:
                logger.info(f"Purging stale workspace {ws_meta.task_id} (age: {int(age)}s > {max_age_seconds}s)")
                if self.cleanup_workspace(ws_meta.task_id):
                    purged.append(ws_meta.task_id)
            else:
                active_remaining.append(ws_meta)

        # Sort remaining by last_accessed_at ascending (oldest accessed first)
        def _get_accessed(m: WorkspaceMetadata) -> float:
            try:
                return datetime.fromisoformat(m.last_accessed_at).timestamp()
            except Exception:
                return 0.0

        active_remaining.sort(key=_get_accessed)

        # 2. Max Workspaces Count Limit Eviction (LRU)
        if max_workspaces is not None and len(active_remaining) > max_workspaces:
            excess = len(active_remaining) - max_workspaces
            for _ in range(excess):
                oldest = active_remaining.pop(0)
                logger.info(f"Purging workspace {oldest.task_id} to satisfy max_workspaces limit ({max_workspaces})")
                if self.cleanup_workspace(oldest.task_id):
                    purged.append(oldest.task_id)

        # 3. Disk Quota Eviction (LRU)
        if max_disk_bytes is not None:
            current_total = sum(self.get_workspace(m.task_id).get_disk_usage() for m in active_remaining if self.get_workspace(m.task_id))
            while current_total > max_disk_bytes and active_remaining:
                oldest = active_remaining.pop(0)
                ws_inst = self.get_workspace(oldest.task_id)
                size = ws_inst.get_disk_usage() if ws_inst else 0
                logger.info(f"Purging workspace {oldest.task_id} ({size} bytes) to satisfy disk limit ({max_disk_bytes})")
                if self.cleanup_workspace(oldest.task_id):
                    purged.append(oldest.task_id)
                    current_total -= size

        return purged

    def get_storage_summary(self) -> Dict[str, Any]:
        """Returns total workspaces, total disk usage, and breakdown."""
        workspaces = self.list_workspaces()
        total_bytes = 0
        details = []

        for m in workspaces:
            ws = self.get_workspace(m.task_id)
            usage = ws.get_disk_usage() if ws else 0
            total_bytes += usage
            details.append({
                "task_id": m.task_id,
                "repo_name": m.repo_name,
                "repo_url": m.repo_url,
                "created_at": m.created_at,
                "last_accessed_at": m.last_accessed_at,
                "disk_usage_bytes": usage,
                "disk_usage_mb": round(usage / (1024 * 1024), 2),
            })

        return {
            "total_workspaces": len(workspaces),
            "total_disk_bytes": total_bytes,
            "total_disk_mb": round(total_bytes / (1024 * 1024), 2),
            "workspaces": details,
        }
