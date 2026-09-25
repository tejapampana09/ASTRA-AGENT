from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.observability.logging import logger


def _run_git(workspace_path: Path, args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git"] + args,
        cwd=workspace_path,
        capture_output=True,
        text=True,
        check=False
    )


class CommitManager:
    """
    AUTONOMOUS COMMIT MANAGER (Phase 4.1):
    Constructs clean, Conventional Commits with verification metadata,
    structured change bullet points, and task traceability.
    """

    @classmethod
    def detect_commit_type(cls, goal: str, had_failures: bool = False) -> str:
        """Determines conventional commit prefix based on task goal and failure history."""
        goal_lower = goal.lower()
        if any(w in goal_lower for w in ["fix", "bug", "error", "patch", "issue", "resolve", "defect"]) or had_failures:
            return "fix"
        elif any(w in goal_lower for w in ["add", "implement", "create", "feature", "new"]):
            return "feat"
        elif any(w in goal_lower for w in ["refactor", "cleanup", "restructure", "organize"]):
            return "refactor"
        elif any(w in goal_lower for w in ["test", "tests", "coverage"]):
            return "test"
        elif any(w in goal_lower for w in ["doc", "docs", "readme"]):
            return "docs"
        return "feat"

    @classmethod
    def detect_scope(cls, files_changed: List[str]) -> str:
        """Extracts a semantic scope from the primary changed files."""
        if not files_changed:
            return "core"

        first_file = files_changed[0].replace("\\", "/")
        parts = first_file.split("/")
        if len(parts) > 1:
            scope = parts[0]
            if scope in ["services", "app", "src", "backend", "lib"]:
                scope = parts[1].replace(".py", "").replace(".ts", "").replace(".js", "")
            return scope
        return Path(first_file).stem

    @classmethod
    def format_commit_message(
        cls,
        task_id: str,
        goal: str,
        files_changed: List[str],
        verification_status: str = "verified",
        test_summary: Optional[str] = None
    ) -> str:
        """
        Builds a production-grade Conventional Commit message.
        """
        commit_type = cls.detect_commit_type(goal)
        scope = cls.detect_scope(files_changed)

        # Truncate goal for subject line
        clean_goal = goal.strip().rstrip(".")
        if len(clean_goal) > 65:
            clean_goal = clean_goal[:62] + "..."

        header = f"{commit_type}({scope}): {clean_goal}"

        body_lines = [
            f"Autonomous engineering task completed by ASTRA 2.0.",
            "",
            "Changes implemented:"
        ]
        for f in files_changed[:6]:
            body_lines.append(f"- Updated {f}")
        if len(files_changed) > 6:
            body_lines.append(f"- And {len(files_changed) - 6} additional files")

        if test_summary:
            body_lines.extend(["", f"Verification: {test_summary}"])
        else:
            body_lines.extend(["", f"Verification: {verification_status.upper()}"])

        footer = [
            "",
            f"Task-ID: {task_id}",
            "Signed-off-by: ASTRA Autonomous Agent <astra@agent.internal>"
        ]

        return f"{header}\n\n" + "\n".join(body_lines) + "\n" + "\n".join(footer)

    @classmethod
    def create_commit(
        cls,
        workspace_path: Path,
        task_id: str,
        goal: str,
        files_changed: List[str],
        verification_status: str = "verified",
        test_summary: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Stages specified modified files and creates a conventional git commit.
        """
        # Ensure user config
        _run_git(workspace_path, ["config", "user.name", "ASTRA Autonomous Agent"])
        _run_git(workspace_path, ["config", "user.email", "astra@agent.internal"])

        # 1. Stage files
        if files_changed:
            for f in files_changed:
                _run_git(workspace_path, ["add", f])
        else:
            _run_git(workspace_path, ["add", "-A"])

        # Check if anything is staged
        status_res = _run_git(workspace_path, ["diff", "--cached", "--name-only"])
        staged_files = [line.strip() for line in status_res.stdout.splitlines() if line.strip()]

        if not staged_files:
            logger.info(f"[{task_id}] No staged changes to commit.")
            return {
                "success": True,
                "committed": False,
                "commit_sha": None,
                "message": "Working tree clean; no changes to commit."
            }

        commit_msg = cls.format_commit_message(
            task_id=task_id,
            goal=goal,
            files_changed=staged_files,
            verification_status=verification_status,
            test_summary=test_summary
        )

        res = _run_git(workspace_path, ["commit", "-m", commit_msg])
        if res.returncode != 0:
            logger.error(f"[{task_id}] Git commit failed: {res.stderr}")
            return {
                "success": False,
                "committed": False,
                "commit_sha": None,
                "error": res.stderr
            }

        # Retrieve commit SHA
        sha_res = _run_git(workspace_path, ["rev-parse", "HEAD"])
        commit_sha = sha_res.stdout.strip() if sha_res.returncode == 0 else "unknown"

        logger.info(f"[{task_id}] Successfully created commit {commit_sha[:8]}: {commit_msg.splitlines()[0]}")

        return {
            "success": True,
            "committed": True,
            "commit_sha": commit_sha,
            "message": commit_msg,
            "staged_files": staged_files,
        }

    @classmethod
    def get_latest_commit(cls, workspace_path: Path) -> Dict[str, Any]:
        """Returns details of the most recent commit in the workspace."""
        res = _run_git(workspace_path, ["log", "-1", "--format=%H|%s|%an|%cI"])
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split("|")
            if len(parts) >= 4:
                return {
                    "sha": parts[0],
                    "subject": parts[1],
                    "author": parts[2],
                    "date": parts[3]
                }
        return {}
