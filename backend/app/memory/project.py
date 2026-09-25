from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProjectMemory:
    repository_id: str
    framework: Optional[str] = None
    architecture: Optional[str] = None
    build_command: Optional[str] = None
    test_command: Optional[str] = None
    coding_conventions: List[str] = field(default_factory=list)
    important_files: List[str] = field(default_factory=list)
    known_issues: List[str] = field(default_factory=list)
    previous_task_results: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_id": self.repository_id,
            "framework": self.framework,
            "architecture": self.architecture,
            "build_command": self.build_command,
            "test_command": self.test_command,
            "coding_conventions": self.coding_conventions,
            "important_files": self.important_files,
            "known_issues": self.known_issues,
            "previous_task_results": self.previous_task_results[-10:],
        }
