from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from app.runtime.workspace import IsolatedWorkspace, WorkspaceSecurityError
from app.safety.permissions import RiskLevel
from app.tools.registry import AstraTool, ToolExecutionResult, tool_registry


class ReadFileTool(AstraTool):
    name = "read_file"
    description = "Reads content from a file inside the isolated workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path inside workspace"}
        },
        "required": ["path"]
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        rel_path = kwargs.get("path", "")
        ws = IsolatedWorkspace("temp", workspace_path)
        try:
            target = ws.validate_path(rel_path)
            if not target.exists():
                return ToolExecutionResult(success=False, output="", error=f"File not found: {rel_path}")
            content = target.read_text(encoding="utf-8", errors="replace")
            return ToolExecutionResult(success=True, output=content)
        except WorkspaceSecurityError as sec_err:
            return ToolExecutionResult(success=False, output="", error=str(sec_err))
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


class SearchFilesTool(AstraTool):
    name = "search_files"
    description = "Searches for files matching a glob pattern or string query."
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"}
        },
        "required": ["pattern"]
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        pattern = kwargs.get("pattern", "*")
        matched = []
        try:
            for p in workspace_path.glob(pattern):
                if p.is_file() and not any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                    rel = p.relative_to(workspace_path).as_posix()
                    matched.append(rel)
            return ToolExecutionResult(success=True, output="\n".join(sorted(matched)))
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


class CreateFileTool(AstraTool):
    name = "create_file"
    description = "Creates a new file with specified content inside the isolated workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "content": {"type": "string", "description": "File text content"}
        },
        "required": ["path", "content"]
    }
    permission_level = RiskLevel.LOW

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        rel_path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        ws = IsolatedWorkspace("temp", workspace_path)
        try:
            target = ws.validate_path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            return ToolExecutionResult(success=True, output=f"Successfully created file: {rel_path}")
        except WorkspaceSecurityError as sec_err:
            return ToolExecutionResult(success=False, output="", error=str(sec_err))
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


class EditFileTool(AstraTool):
    name = "edit_file"
    description = "Edits a file by replacing old_text with new_text."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"},
            "old_text": {"type": "string", "description": "Exact text chunk to replace"},
            "new_text": {"type": "string", "description": "Replacement text chunk"}
        },
        "required": ["path", "old_text", "new_text"]
    }
    permission_level = RiskLevel.LOW

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        rel_path = kwargs.get("path", "")
        old_text = kwargs.get("old_text", "")
        new_text = kwargs.get("new_text", "")
        ws = IsolatedWorkspace("temp", workspace_path)
        try:
            target = ws.validate_path(rel_path)
            if not target.exists():
                return ToolExecutionResult(success=False, output="", error=f"File not found: {rel_path}")
            current_content = target.read_text(encoding="utf-8")
            if old_text not in current_content:
                return ToolExecutionResult(success=False, output="", error=f"Target text snippet not found in {rel_path}")
            new_content = current_content.replace(old_text, new_text, 1)
            target.write_text(new_content, encoding="utf-8")
            return ToolExecutionResult(success=True, output=f"Successfully edited file: {rel_path}")
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


class DeleteFileTool(AstraTool):
    name = "delete_file"
    description = "Deletes a file inside the isolated workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative file path"}
        },
        "required": ["path"]
    }
    permission_level = RiskLevel.MEDIUM

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        rel_path = kwargs.get("path", "")
        ws = IsolatedWorkspace("temp", workspace_path)
        try:
            target = ws.validate_path(rel_path)
            if not target.exists():
                return ToolExecutionResult(success=False, output="", error=f"File not found: {rel_path}")
            target.unlink()
            return ToolExecutionResult(success=True, output=f"Successfully deleted file: {rel_path}")
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


# Register filesystem tools
tool_registry.register(ReadFileTool())
tool_registry.register(SearchFilesTool())
tool_registry.register(CreateFileTool())
tool_registry.register(EditFileTool())
tool_registry.register(DeleteFileTool())
