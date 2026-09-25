from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.observability.logging import logger


@dataclass
class FileDiffSummary:
    file_path: str
    lines_added: int = 0
    lines_deleted: int = 0
    is_new: bool = False
    is_deleted: bool = False


@dataclass
class GitDiffReport:
    raw_diff: str
    files_changed_count: int = 0
    total_added: int = 0
    total_deleted: int = 0
    files: List[FileDiffSummary] = field(default_factory=list)


class DiffEngine:
    """Calculates and parses git diffs and file modifications."""

    @staticmethod
    def inspect_diff(workspace_path: Path) -> GitDiffReport:
        try:
            # First check if git is initialized
            if not (workspace_path / ".git").exists():
                return GitDiffReport(raw_diff="")

            # Mark untracked files with intent-to-add so git diff includes them
            subprocess.run(["git", "add", "-N", "."], cwd=workspace_path, capture_output=True, check=False)

            # Get full diff against HEAD
            res = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=False
            )
            raw_diff = res.stdout
            if not raw_diff.strip():
                # Check untracked files
                untracked = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=workspace_path,
                    capture_output=True,
                    text=True,
                    check=False
                )
                if untracked.stdout.strip():
                    raw_diff = f"# Untracked / Staged status:\n{untracked.stdout}"

            # Parse diff stats
            stats_res = subprocess.run(
                ["git", "diff", "--numstat", "HEAD"],
                cwd=workspace_path,
                capture_output=True,
                text=True,
                check=False
            )

            file_summaries: List[FileDiffSummary] = []
            total_added = 0
            total_deleted = 0

            for line in stats_res.stdout.strip().splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    added_str, deleted_str, fname = parts[0], parts[1], parts[2]
                    added = int(added_str) if added_str.isdigit() else 0
                    deleted = int(deleted_str) if deleted_str.isdigit() else 0
                    total_added += added
                    total_deleted += deleted
                    file_summaries.append(
                        FileDiffSummary(
                            file_path=fname,
                            lines_added=added,
                            lines_deleted=deleted,
                        )
                    )

            return GitDiffReport(
                raw_diff=raw_diff,
                files_changed_count=len(file_summaries),
                total_added=total_added,
                total_deleted=total_deleted,
                files=file_summaries,
            )

        except Exception as e:
            logger.warning(f"Error inspecting diff: {e}")
            return GitDiffReport(raw_diff="", files_changed_count=0)
