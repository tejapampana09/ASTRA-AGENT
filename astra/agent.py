"""Core autonomous software engineering agent loop (Think-Plan-Act-Observe-Verify).

Features:
- Mandatory Independent Verification (AST Syntax, Compilation, & pytest test execution)
- Auto-Healing Fix Loop: If verification fails, the agent autonomously diagnoses & fixes code
- Context Window Compression: Prunes older tool outputs to preserve token quota
- Full State Machine: PLAN -> EXPLORE -> ACT -> OBSERVE -> VERIFY -> FIX -> DONE
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from astra.llm import LLMClient
from astra.tools import TOOL_DEFINITIONS, ToolExecutor
from astra.verifier import IndependentVerifier, VerificationResult

SYSTEM_PROMPT = """You are ASTRA, an elite autonomous software engineering agent.
Your objective is to solve software engineering tasks, fix bugs, implement features, and independently verify code in the workspace.

You have access to powerful tools to inspect and modify the repository:
- read_file(file_path, start_line, end_line): Inspect file contents
- write_file(file_path, content): Create or overwrite files
- edit_file(file_path, target_snippet, replacement_snippet): Perform surgical edits
- list_dir(dir_path): Inspect directory structure
- search_code(query, search_dir): Search codebase symbols and text
- run_command(command, timeout): Run pytest, python scripts, linters, or git commands
- web_search(query): Search live web for docs or solutions

AGENT WORKFLOW (Mandatory):
1. EXPLORE: Read existing files, understand the architecture, and check test configurations.
2. SURGICAL EDITS: Modify only what is necessary. Preserve style and existing tests.
3. OBSERVE & FIX: If a command or edit errors, diagnose the cause and iterate.
4. VERIFY: Note that an Independent Verifier will automatically validate AST syntax and run the test suite on all your changes before task completion is accepted. Never claim a task is completed without passing verification.
"""


class AgentCallback:
    """Hooks for streaming execution steps to the terminal or UI."""

    def on_phase_change(self, phase: str, details: str = "") -> None:
        pass

    def on_thought(self, thought: str) -> None:
        pass

    def on_tool_call(self, name: str, args: Dict[str, Any]) -> None:
        pass

    def on_tool_result(self, name: str, result: str) -> None:
        pass

    def on_file_changed(self, file_path: str) -> None:
        pass

    def on_verification(self, passed: bool, summary: str, details: str = "") -> None:
        pass


class AstraAgent:
    """Autonomous software engineering agent with mandatory independent verification."""

    def __init__(
        self,
        workspace_path: Optional[Path] = None,
        model_name: Optional[str] = None,
        max_iterations: int = 15,
        max_verification_attempts: int = 3,
        callback: Optional[AgentCallback] = None,
    ):
        self.workspace_path = (workspace_path or Path.cwd()).resolve()
        self.tools = ToolExecutor(self.workspace_path)
        self.verifier = IndependentVerifier(self.workspace_path)
        self.llm = LLMClient(model_name=model_name)
        self.max_iterations = max_iterations
        self.max_verification_attempts = max_verification_attempts
        self.callback = callback or AgentCallback()
        self.files_modified: Set[str] = set()

    def _compress_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prune older lengthy tool outputs to save context window and token budget."""
        if len(messages) <= 6:
            return messages

        compressed = []
        cutoff = len(messages) - 4  # Keep last 4 messages completely uncompressed

        for idx, m in enumerate(messages):
            if idx >= cutoff or idx < 2:  # Keep system and initial user goal intact
                compressed.append(m)
                continue

            content = m.get("content") or ""
            role = m.get("role")

            if role == "tool" and len(content) > 350:
                head = content[:150]
                tail = content[-150:]
                trimmed = f"{head}\n... [Output trimmed for context: {len(content) - 300} chars omitted] ...\n{tail}"
                m_copy = dict(m)
                m_copy["content"] = trimmed
                compressed.append(m_copy)
            else:
                compressed.append(m)

        return compressed

    def run(self, goal: str) -> Dict[str, Any]:
        """Execute the goal autonomously with independent verification and self-healing."""
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Workspace directory: {self.workspace_path}\n\nTask Goal:\n{goal}"},
        ]

        self.callback.on_phase_change("PLAN", "Analyzing task goal and architecture")

        iteration = 0
        verification_attempts = 0
        final_summary = ""
        verification_result: Optional[VerificationResult] = None

        while iteration < self.max_iterations:
            iteration += 1

            # Prune older messages if context is getting heavy
            compressed_msgs = self._compress_messages(messages)

            # Call LLM
            try:
                response = self.llm.complete(compressed_msgs, tools=TOOL_DEFINITIONS)
            except Exception as exc:
                return {
                    "status": "error",
                    "error": str(exc),
                    "iterations": iteration,
                    "files_modified": list(self.files_modified),
                }

            # If model returned thoughts / explanation
            if response.content:
                final_summary = response.content.strip()
                if response.has_tool_calls():
                    self.callback.on_thought(final_summary)

            # Check if model has finished proposing tool calls
            if not response.has_tool_calls():
                # Model says it's done — TRIGGER INDEPENDENT VERIFIER!
                if self.files_modified:
                    self.callback.on_phase_change("VERIFY", "Running mandatory independent AST & test verification...")
                    verification_result = self.verifier.verify(self.files_modified)

                    if verification_result.passed:
                        self.callback.on_verification(True, verification_result.summary, verification_result.details)
                        self.callback.on_phase_change("DONE", "Verification passed successfully.")
                        return {
                            "status": "completed",
                            "summary": final_summary,
                            "iterations": iteration,
                            "files_modified": list(self.files_modified),
                            "verification": "passed",
                            "verification_details": verification_result.details,
                        }
                    else:
                        # Verification failed! Enter FIX loop
                        verification_attempts += 1
                        self.callback.on_verification(False, verification_result.summary, verification_result.details)

                        if verification_attempts < self.max_verification_attempts:
                            self.callback.on_phase_change(
                                "FIX",
                                f"Autonomous fix attempt {verification_attempts}/{self.max_verification_attempts}"
                            )
                            # Inject verification failure back into conversation to force self-healing
                            fix_prompt = (
                                f"[INDEPENDENT VERIFICATION FAILED]\n"
                                f"Stage: {verification_result.phase}\n"
                                f"Error Details:\n{verification_result.details}\n\n"
                                f"The task CANNOT be marked complete until these errors are fixed and all tests pass.\n"
                                f"Please diagnose the failure, inspect the code, modify the files to fix it, and verify."
                            )
                            messages.append({"role": "user", "content": fix_prompt})
                            continue
                        else:
                            # Exceeded fix attempts
                            return {
                                "status": "verification_failed",
                                "summary": final_summary,
                                "error": f"Independent verification failed after {verification_attempts} fix attempts:\n{verification_result.details}",
                                "iterations": iteration,
                                "files_modified": list(self.files_modified),
                                "verification": "failed",
                            }
                else:
                    # No files were modified (e.g. read-only query or search)
                    self.callback.on_phase_change("DONE", "Task complete.")
                    return {
                        "status": "completed",
                        "summary": final_summary,
                        "iterations": iteration,
                        "files_modified": [],
                    }

            # Process tool calls
            self.callback.on_phase_change("ACT", f"Executing {len(response.tool_calls)} tool call(s)")
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

        # Max iterations reached
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
