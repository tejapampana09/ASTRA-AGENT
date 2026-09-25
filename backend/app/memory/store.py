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
    Episodic memory store for ASTRA 2.0.
    Retains cross-task learnings, past failure discoveries, and solution strategies.
    Ensures that when Task 2 touches code touched in Task 1, prior findings are instantly accessible.
    """

    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory
        # In-memory dictionary: repo_id -> List[TaskEpisodicMemory]
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
        """Stores a task's full episodic memory."""
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

        # Persist to database if session factory is available
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

        logger.info(f"Recorded task memory for task {task_id} in repo {repo_id}: {len(discoveries or [])} discoveries, {len(files_modified)} files.")
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
        Scores relevance based on:
        1. Overlapping files modified (highest weight)
        2. Keyword overlap in task goals
        3. Related failure discoveries
        """
        repo_memories = self._memories.get(repo_id, [])
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


# Global singleton task memory store
task_memory_store = TaskMemoryStore()
