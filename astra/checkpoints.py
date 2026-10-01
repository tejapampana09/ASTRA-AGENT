"""ASTRA V4 Checkpoint and Safe Rollback System.

Captures file states and git commits before mutating actions, enabling reliable
rollbacks without destroying pre-existing user code or untracked changes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Checkpoint:
    checkpoint_id: str
    session_id: str
    description: str
    timestamp: float = field(default_factory=time.time)
    git_head: Optional[str] = None
    # Map of relative file path -> previous content (or None if file didn't exist)
    file_snapshots: Dict[str, Optional[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "description": self.description,
            "timestamp": self.timestamp,
            "git_head": self.git_head,
            "files_tracked": list(self.file_snapshots.keys()),
        }


class CheckpointManager:
    """Manages workspace snapshots and non-destructive rollbacks."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path.resolve()
        self.checkpoints: List[Checkpoint] = []
        self._initial_files: set[str] = self._scan_initial_files()

    def _scan_initial_files(self) -> set[str]:
        """Record all files that existed before the agent performed any mutations."""
        existing = set()
        for root, dirs, files in os.walk(self.workspace_path):
            # Ignore hidden and build directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "dist", "build", "__pycache__", "venv")]
            for f in files:
                p = Path(root) / f
                try:
                    rel = p.relative_to(self.workspace_path).as_posix()
                    existing.add(rel)
                except Exception:
                    pass
        return existing

    def _get_git_head(self) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def create_checkpoint(
        self,
        session_id: str,
        description: str,
        files: Optional[List[str]] = None,
    ) -> Checkpoint:
        """Create a snapshot of specified files (or touched files) before modification."""
        chk_id = f"chk_{uuid.uuid4().hex[:10]}"
        git_head = self._get_git_head()
        snapshots: Dict[str, Optional[str]] = {}

        if files:
            for file_path in files:
                clean_path = Path(file_path)
                if not clean_path.is_absolute():
                    full_path = (self.workspace_path / clean_path).resolve()
                else:
                    full_path = clean_path.resolve()

                try:
                    rel = full_path.relative_to(self.workspace_path).as_posix()
                except ValueError:
                    continue

                if full_path.exists() and full_path.is_file():
                    try:
                        snapshots[rel] = full_path.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        snapshots[rel] = None
                else:
                    # File did not exist at this checkpoint
                    snapshots[rel] = None

        cp = Checkpoint(
            checkpoint_id=chk_id,
            session_id=session_id,
            description=description,
            git_head=git_head,
            file_snapshots=snapshots,
        )
        self.checkpoints.append(cp)
        return cp

    def rollback(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Revert changes back to a specific checkpoint or the most recent one.
        
        CRITICAL SAFETY RULE: Never delete or overwrite files that were present
        before the session started, unless restoring their snapshotted contents.
        """
        if not self.checkpoints:
            return {"success": False, "error": "No checkpoints available to rollback."}

        target_cp: Optional[Checkpoint] = None
        if checkpoint_id:
            for cp in reversed(self.checkpoints):
                if cp.checkpoint_id == checkpoint_id:
                    target_cp = cp
                    break
        else:
            target_cp = self.checkpoints[-1]

        if not target_cp:
            return {"success": False, "error": f"Checkpoint '{checkpoint_id}' not found."}

        restored_files: List[str] = []
        deleted_files: List[str] = []

        for rel_path, content in target_cp.file_snapshots.items():
            full_path = (self.workspace_path / rel_path).resolve()

            if content is None:
                # File did not exist at the checkpoint
                # Only delete if it was created during this session (not an initial file)
                if full_path.exists() and rel_path not in self._initial_files:
                    try:
                        full_path.unlink()
                        deleted_files.append(rel_path)
                    except Exception:
                        pass
            else:
                # Restore previous content
                try:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding="utf-8")
                    restored_files.append(rel_path)
                except Exception:
                    pass

        return {
            "success": True,
            "checkpoint_id": target_cp.checkpoint_id,
            "restored_files": restored_files,
            "deleted_files": deleted_files,
        }

    def list_checkpoints(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if session_id:
            return [c.to_dict() for c in self.checkpoints if c.session_id == session_id]
        return [c.to_dict() for c in self.checkpoints]
