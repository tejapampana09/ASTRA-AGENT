from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.memory.project import ProjectMemory
from app.observability.logging import logger


class MemoryRetriever:
    """Retrieves relevant conventions and prior task learnings for an active task."""

    def __init__(self):
        self._project_memories: Dict[str, ProjectMemory] = {}

    def save_project_memory(self, memory: ProjectMemory):
        self._project_memories[memory.repository_id] = memory

    def get_project_memory(self, repo_id: str) -> Optional[ProjectMemory]:
        return self._project_memories.get(repo_id)

    def retrieve_relevant_context(self, repo_id: str, query: str) -> Dict[str, Any]:
        mem = self.get_project_memory(repo_id)
        if not mem:
            return {}
        return {
            "test_command": mem.test_command,
            "build_command": mem.build_command,
            "conventions": mem.coding_conventions,
            "important_files": mem.important_files,
        }


memory_retriever = MemoryRetriever()
