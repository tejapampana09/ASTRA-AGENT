"""Core autonomous software engineering agent loop (Think-Plan-Act-Observe-Verify)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from astra.llm import LLMClient
from astra.tools import TOOL_DEFINITIONS, ToolExecutor

SYSTEM_PROMPT = """You are ASTRA, an elite autonomous software engineering agent.
Your objective is to solve software engineering tasks, fix bugs, implement features, and verify code directly in the user's repository.

You have access to powerful tools to inspect and modify the workspace:
- read_file(file_path, start_line, end_line): Inspect file contents
- write_file(file_path, content): Create or overwrite files
- edit_file(file_path, target_snippet, replacement_snippet): Perform surgical edits
- list_dir(dir_path): Inspect directory structure
- search_code(query, search_dir): Search codebase symbols and text
- run_command(command, timeout): Run pytest, unittest, python scripts, linters, or git commands

GUIDELINES:
1. EXPLORE FIRST: Before editing, read existing code, understand architecture, and check test configurations.
2. SURGICAL EDITS: Prefer `edit_file` over rewriting entire files whenever possible.
3. VERIFY WITH EVIDENCE: After modifying code, run relevant tests (e.g., `run_command("pytest")` or targeted test) to prove your fix works.
4. DEBUG AUTONOMOUSLY: If tests fail, read the error traceback, inspect the failing lines, hypothesize the cause, and iterate until tests pass.
5. BE CONCISE: State your reasoning briefly before each action. When done, summarize what changes were made and how they were verified.
"""


class AgentCallback:
    """Hooks for streaming execution steps to the terminal or UI."""

    def on_thought(self, thought: str) -> None:
        pass

    def on_tool_call(self, name: str, args: Dict[str, Any]) -> None:
        pass

    def on_tool_result(self, name: str, result: str) -> None:
        pass

    def on_file_changed(self, file_path: str) -> None:
        pass

    def on_verification(self, status: str, details: str) -> None:
        pass


class AstraAgent:
    """Autonomous software engineering agent."""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        model_name: Optional[str] = None,
        max_iterations: int = 15,
        callback: Optional[AgentCallback] = None,
    ):
        self.workspace_path = (workspace_path or Path.cwd()).resolve()
        self.tools = ToolExecutor(self.workspace_path)
        self.llm = LLMClient(model_name=model_name)
        self.max_iterations = max_iterations
        self.callback = callback or AgentCallback()
        self.files_modified: Set[str] = set()

    def run(self, goal: str) -> Dict[str, Any]:
        """Execute the goal autonomously through iterative reasoning and tool execution."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Workspace directory: {self.workspace_path}\n\nTask Goal:\n{goal}"},
        ]

        iteration = 0
        final_summary = ""

        while iteration < self.max_iterations:
            iteration += 1

            # Call LLM
            try:
                response = self.llm.complete(messages, tools=TOOL_DEFINITIONS)
            except Exception as exc:
                return {
                    "status": "error",
                    "error": str(exc),
                    "iterations": iteration,
                    "files_modified": list(self.files_modified),
                }

            # If model returned text/thoughts
            if response.content:
                final_summary = response.content.strip()
                if response.has_tool_calls():
                    self.callback.on_thought(final_summary)

            # If no tool calls, the model considers the task finished
            if not response.has_tool_calls():
                break

            # Process tool calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
                "raw_content": response.raw_content,
            }
            messages.append(assistant_msg)

            for tc in response.tool_calls:
                fn = tc.get("function", {})
                fn_name = fn.get("name")
                fn_args = fn.get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                self.callback.on_tool_call(fn_name, fn_args)

                # Execute tool
                tool_out = self._execute_tool(fn_name, fn_args)

                # Track file changes
                if fn_name in ("write_file", "edit_file"):
                    fp = fn_args.get("file_path")
                    if fp:
                        self.files_modified.add(fp)
                        self.callback.on_file_changed(fp)

                self.callback.on_tool_result(fn_name, tool_out)

                messages.append(
                    {
                        "role": "tool",
                        "name": fn_name,
                        "tool_call_id": tc.get("id"),
                        "content": tool_out,
                    }
                )

        # Verification summary
        status = "completed" if iteration < self.max_iterations else "max_iterations_reached"
        return {
            "status": status,
            "summary": final_summary,
            "iterations": iteration,
            "files_modified": list(self.files_modified),
        }

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Map tool call to ToolExecutor methods."""
        try:
            if name == "read_file":
                return self.tools.read_file(
                    file_path=args.get("file_path", ""),
                    start_line=args.get("start_line"),
                    end_line=args.get("end_line"),
                )
            elif name == "write_file":
                return self.tools.write_file(
                    file_path=args.get("file_path", ""),
                    content=args.get("content", ""),
                )
            elif name == "edit_file":
                return self.tools.edit_file(
                    file_path=args.get("file_path", ""),
                    target_snippet=args.get("target_snippet", ""),
                    replacement_snippet=args.get("replacement_snippet", ""),
                )
            elif name == "list_dir":
                return self.tools.list_dir(dir_path=args.get("dir_path", "."))
            elif name == "search_code":
                return self.tools.search_code(
                    query=args.get("query", ""),
                    search_dir=args.get("search_dir", "."),
                )
            elif name == "run_command":
                return self.tools.run_command(
                    command=args.get("command", ""),
                    timeout=args.get("timeout", 30),
                )
            elif name == "web_search":
                return self.tools.web_search(
                    query=args.get("query", ""),
                )
            else:
                return f"Error: Unknown tool '{name}'."
        except Exception as exc:
            return f"Tool execution error ({name}): {exc}"
