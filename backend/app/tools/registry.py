from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from app.observability.logging import logger
from app.safety.permissions import RiskLevel


@dataclass
class ToolExecutionResult:
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AstraTool(ABC):
    """Base class for all tools registered in the ASTRA tool registry."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    permission_level: RiskLevel
    timeout_seconds: int = 60
    error_behavior: str = "return_error"  # "return_error", "raise", "retry"

    @abstractmethod
    def execute(self, workspace_path: Any, **kwargs: Any) -> ToolExecutionResult:
        pass


class ToolRegistry:
    """Central registry for discovering and safely executing ASTRA tools."""

    def __init__(self):
        self._tools: Dict[str, AstraTool] = {}

    def register(self, tool: AstraTool) -> None:
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool '{tool.name}' (risk: {tool.permission_level.value})")

    def get(self, name: str) -> Optional[AstraTool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "permission_level": t.permission_level.value,
                "timeout": t.timeout_seconds,
            }
            for t in self._tools.values()
        ]

    def execute_tool(self, name: str, workspace_path: Any, **kwargs: Any) -> ToolExecutionResult:
        tool = self.get(name)
        if not tool:
            return ToolExecutionResult(
                success=False,
                output="",
                error=f"Tool '{name}' not found in registry."
            )
        try:
            return tool.execute(workspace_path=workspace_path, **kwargs)
        except Exception as e:
            logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            return ToolExecutionResult(
                success=False,
                output="",
                error=str(e)
            )


# Global registry singleton
tool_registry = ToolRegistry()
