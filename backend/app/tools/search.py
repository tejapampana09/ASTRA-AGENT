from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.safety.permissions import RiskLevel
from app.tools.registry import AstraTool, ToolExecutionResult, tool_registry


class GrepSearchTool(AstraTool):
    name = "grep_search"
    description = "Searches for regex or text pattern across repository files."
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Regex or keyword to search for"},
            "file_extension": {"type": "string", "description": "Optional file extension filter (e.g. .py)"}
        },
        "required": ["query"]
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        query = kwargs.get("query", "")
        ext = kwargs.get("file_extension")
        matches: List[str] = []

        try:
            pattern = re.compile(query, re.IGNORECASE)
            for p in workspace_path.rglob("*"):
                if p.is_file() and not any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                    if ext and not p.name.endswith(ext):
                        continue
                    try:
                        content = p.read_text(encoding="utf-8", errors="replace")
                        for idx, line in enumerate(content.splitlines(), start=1):
                            if pattern.search(line):
                                rel = p.relative_to(workspace_path).as_posix()
                                matches.append(f"{rel}:{idx}: {line.strip()[:150]}")
                                if len(matches) >= 50:
                                    break
                    except Exception:
                        continue
                if len(matches) >= 50:
                    break

            return ToolExecutionResult(
                success=True,
                output="\n".join(matches) if matches else "No matches found."
            )
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


tool_registry.register(GrepSearchTool())
