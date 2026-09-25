from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class TaskMemory:
    task_id: str
    goal: str
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def record_action(self, tool_name: str, arguments: Dict[str, Any], result: str):
        self.actions_taken.append({
            "tool": tool_name,
            "args": arguments,
            "result": result[:500],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def record_failure(self, error: str, traceback: str):
        self.failure_history.append({
            "error": error,
            "traceback": traceback[:600],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
