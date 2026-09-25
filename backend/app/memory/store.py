from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.observability.logging import logger


@dataclass
class TaskEpisodicMemory:
    """Detailed memory of a completed or attempted engineering task in a repository."""
    task_id: str
    repo_id: str
    goal: str
    files_modified: List[str] = field(default_factory=list)
    test_status: str = "verified"
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    discoveries: List[str] = field(default_factory=list)
    solution_summary: str = ""
    conventions_learned: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "repo_id": self.repo_id,
            "goal": self.goal,
            "files_modified": self.files_modified,
            "test_status": self.test_status,
            "failure_history": self.failure_history,
            "discoveries": self.discoveries,
            "solution_summary": self.solution_summary,
            "conventions_learned": self.conventions_learned,
            "timestamp": self.timestamp,
        }


class TaskMemoryStore:
    """
    Durable episodic memory store for ASTRA 2.0.
    Persists cross-task learnings, past failure discoveries, and solution strategies
    to PostgreSQL / database models so memory survives agent restarts and process restarts.
    """

    def __init__(self, db_session_factory=None):
        if db_session_factory is None:
            try:
                from app.database.session import get_sync_session_factory
                self._session_factory = get_sync_session_factory()
            except Exception:
                self._session_factory = None
        else:
            self._session_factory = db_session_factory

        # In-memory working cache: repo_id -> List[TaskEpisodicMemory]
        self._memories: Dict[str, List[TaskEpisodicMemory]] = {}

    def record_task_experience(
        self,
        task_id: str,
        repo_id: str,
        goal: str,
        files_modified: List[str],
        test_status: str,
        failure_history: Optional[List[Dict[str, Any]]] = None,
        discoveries: Optional[List[str]] = None,
        solution_summary: str = "",
        conventions_learned: Optional[List[str]] = None,
    ) -> TaskEpisodicMemory:
        """Stores a task's full episodic memory to the database and working memory."""
        mem = TaskEpisodicMemory(
            task_id=task_id,
            repo_id=repo_id,
            goal=goal,
            files_modified=files_modified,
            test_status=test_status,
            failure_history=failure_history or [],
            discoveries=discoveries or [],
            solution_summary=solution_summary,
            conventions_learned=conventions_learned or [],
        )

        if repo_id not in self._memories:
            self._memories[repo_id] = []
        self._memories[repo_id].append(mem)

        # Durable database persistence across restarts
        if self._session_factory:
            try:
                from app.database.models import TaskEpisodicMemoryRecord
                with self._session_factory() as session:
                    rec = TaskEpisodicMemoryRecord(
                        id=f"mem-{task_id}",
                        repo_id=repo_id,
                        task_id=task_id,
                        goal=goal,
                        modified_files=files_modified,
                        test_status=test_status,
                        discoveries=discoveries or [],
                        solution_summary=solution_summary,
                        conventions_learned=conventions_learned or [],
                    )
                    session.merge(rec)
                    session.commit()
            except Exception as e:
                logger.warning(f"Could not persist episodic memory to database: {e}")

        logger.info(f"Recorded durable task memory for task {task_id} in repo {repo_id}: {len(discoveries or [])} discoveries, {len(files_modified)} files.")
        return mem

    def retrieve_relevant_task_memories(
        self,
        repo_id: str,
        current_goal: str,
        candidate_files: Optional[List[str]] = None,
        top_k: int = 3
    ) -> List[TaskEpisodicMemory]:
        """
        Retrieves prior task memories relevant to the current task.
        Queries the persistent database first, ensuring cross-process restart safety.
        Scores relevance based on file overlap, goal keyword overlap, and failure discoveries.
        """
        repo_memories = list(self._memories.get(repo_id, []))

        # Query database to restore memories across restarts
        if self._session_factory:
            try:
                from app.database.models import TaskEpisodicMemoryRecord
                from sqlalchemy import select
                with self._session_factory() as session:
                    db_records = session.execute(
                        select(TaskEpisodicMemoryRecord).filter_by(repo_id=repo_id)
                    ).scalars().all()

                    existing_ids = {m.task_id for m in repo_memories}
                    for rec in db_records:
                        if rec.task_id not in existing_ids:
                            mem_obj = self._record_to_memory(rec)
                            repo_memories.append(mem_obj)
                            existing_ids.add(rec.task_id)
            except Exception as e:
                logger.debug(f"Episodic memory DB query fallback: {e}")

        if not repo_memories:
            return []

        goal_terms = set(re.findall(r"\w+", current_goal.lower()))
        target_files = set(candidate_files or [])

        scored_memories = []
        for mem in repo_memories:
            score = 0.0

            # 1. File overlap score (+5 per overlapping file)
            mem_files = set(mem.files_modified)
            shared_files = target_files.intersection(mem_files)
            score += len(shared_files) * 5.0

            # 2. Directory overlap score (+2 per matching folder)
            target_dirs = {f.split("/")[0] for f in target_files if "/" in f}
            mem_dirs = {f.split("/")[0] for f in mem.files_modified if "/" in f}
            score += len(target_dirs.intersection(mem_dirs)) * 2.0

            # 3. Goal keyword overlap (+1 per shared technical term)
            mem_goal_terms = set(re.findall(r"\w+", mem.goal.lower()))
            shared_terms = goal_terms.intersection(mem_goal_terms)
            score += len([t for t in shared_terms if len(t) > 3]) * 1.5

            # 4. Discovery keyword match (+3 if discoveries relate to current goal)
            for disc in mem.discoveries:
                disc_terms = set(re.findall(r"\w+", disc.lower()))
                if goal_terms.intersection(disc_terms):
                    score += 3.0

            if score > 0:
                scored_memories.append((mem, score))

        scored_memories.sort(key=lambda x: x[1], reverse=True)
        return [m for m, _ in scored_memories[:top_k]]

    @staticmethod
    def _record_to_memory(rec) -> TaskEpisodicMemory:
        return TaskEpisodicMemory(
            task_id=rec.task_id,
            repo_id=rec.repo_id,
            goal=rec.goal,
            files_modified=rec.modified_files or [],
            test_status=rec.test_status or "verified",
            failure_history=[],
            discoveries=rec.discoveries or [],
            solution_summary=rec.solution_summary or "",
            conventions_learned=rec.conventions_learned or [],
            timestamp=rec.created_at.isoformat() if rec.created_at else ""
        )

    def format_memory_for_agent_prompt(self, memories: List[TaskEpisodicMemory]) -> str:
        """Formats retrieved memories into an actionable prompt section for the planner and agent."""
        if not memories:
            return "No previous task history found for this repository."

        lines = ["### Prior Task Learnings & Repository Experience"]
        for idx, mem in enumerate(memories, 1):
            lines.append(f"\n#### Experience {idx}: Task {mem.task_id} (Status: {mem.test_status.upper()})")
            lines.append(f"- **Goal**: {mem.goal}")
            if mem.files_modified:
                lines.append(f"- **Files Modified**: {', '.join(mem.files_modified)}")
            if mem.discoveries:
                lines.append("- **Bugs Discovered / Root Causes**:")
                for d in mem.discoveries:
                    lines.append(f"  * {d}")
            if mem.solution_summary:
                lines.append(f"- **Solution Applied**: {mem.solution_summary}")
            if mem.conventions_learned:
                lines.append(f"- **Conventions Noted**: {', '.join(mem.conventions_learned)}")

        return "\n".join(lines)


# Global singleton task memory store with database session factory auto-wired
_task_memory_store: Optional[TaskMemoryStore] = None


def get_task_memory_store() -> TaskMemoryStore:
    global _task_memory_store
    if _task_memory_store is None:
        _task_memory_store = TaskMemoryStore()
    return _task_memory_store


def set_task_memory_store(store: TaskMemoryStore) -> None:
    global _task_memory_store
    _task_memory_store = store


# Backward compatibility instance
task_memory_store = get_task_memory_store()
