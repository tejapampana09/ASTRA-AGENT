from __future__ import annotations

import asyncio
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.config import settings
from app.observability.logging import logger
from app.runtime.workspace import IsolatedWorkspace, LocalExecutionWorkspace
from app.llm.resolver import resolve_model, ResolvedModel


@dataclass
class AstraToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]
    result: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AstraAgentEvent:
    event_type: str
    message: str
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class AstraExecutionResult:
    success: bool
    task_id: str
    message: str
    tool_calls: List[AstraToolCall] = field(default_factory=list)
    modified_files: List[str] = field(default_factory=list)
    error: Optional[str] = None
    total_iterations: int = 0
    duration_seconds: float = 0.0
import re

# OpenHands SDK LiteLLM telemetry compatibility patch for Gemini
try:
    import openhands.sdk.llm.utils.telemetry as _oh_telemetry
    _orig_normalize_usage = _oh_telemetry.normalize_usage

    def _safe_normalize_usage(usage):
        try:
            return _orig_normalize_usage(usage)
        except Exception:
            if usage is not None:
                p_tok = getattr(usage, "prompt_tokens", 0) or 0
                c_tok = getattr(usage, "completion_tokens", 0) or 0
                return _oh_telemetry.UsageSnapshot(
                    prompt_tokens=int(p_tok),
                    completion_tokens=int(c_tok),
                    reasoning_tokens=0,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                )
            return None

    _oh_telemetry.normalize_usage = _safe_normalize_usage
except Exception:
    pass

# OpenHands FileEditor automatic path resolution & security containment patch
try:
    from openhands.tools.file_editor.editor import FileEditor, is_host_absolute_path, FileEditorObservation
    _orig_file_editor_call = FileEditor.__call__

    def _safe_file_editor_call(self, *, command, path, **kwargs):
        _p = Path(path)
        if not is_host_absolute_path(_p) and self._cwd is not None:
            _p = (Path(self._cwd) / _p).resolve()
        else:
            _p = _p.resolve()

        active_ws = getattr(AgentRuntime, "_current_active_workspace", None)
        if active_ws is not None and hasattr(active_ws, "validate_path"):
            try:
                active_ws.validate_path(_p)
            except Exception as e:
                logger.warning(f"FileEditor path security violation blocked: {_p} outside workspace ({e})")
                return FileEditorObservation.from_text(
                    text=f"Security violation: path '{path}' is outside repository root ({e})",
                    command=command,
                    path=str(_p),
                    is_error=True,
                )

        return _orig_file_editor_call(self, command=command, path=str(_p), **kwargs)

    FileEditor.__call__ = _safe_file_editor_call
except Exception:
    pass

# OpenHands Terminal security containment & policy validation patch
try:
    from openhands.tools.terminal import TerminalExecutor, TerminalAction, TerminalObservation
    from app.safety.policies import SecurityPolicies
    _orig_terminal_call = TerminalExecutor.__call__

    def _safe_terminal_call(self, action: TerminalAction, conversation=None) -> TerminalObservation:
        active_ws = getattr(AgentRuntime, "_current_active_workspace", None)

        if not action.is_input and action.command:
            cmd = action.command.strip()

            # 1. Enforce blocked dangerous commands (e.g. rm -rf /, fork bombs, disk writes)
            is_allowed, reason = SecurityPolicies.validate_command(cmd)
            if not is_allowed:
                logger.warning(f"Terminal command blocked by policy: {cmd} ({reason})")
                return TerminalObservation.from_text(
                    f"Command blocked by ASTRA security policy: {reason}",
                    is_error=True,
                    command=cmd,
                    exit_code=1,
                )

            # 2. Enforce workspace directory containment on commands attempting to escape
            if active_ws is not None and hasattr(active_ws, "path"):
                ws_root = Path(active_ws.path).resolve()

                # Check cd attempts that escape root
                cd_match = re.search(r"\bcd\s+([^;&|]+)", cmd)
                if cd_match:
                    target_dir = cd_match.group(1).strip().strip("'\"")
                    if target_dir in ["..", "../..", "/"] or target_dir.startswith("..") or target_dir.startswith("~"):
                        logger.warning(f"Terminal cd escape blocked: {target_dir} outside {ws_root}")
                        return TerminalObservation.from_text(
                            f"Security violation: directory escape '{target_dir}' outside workspace root '{ws_root}'",
                            is_error=True,
                            command=cmd,
                            exit_code=1,
                        )

                # Check for explicit external paths (e.g. cat C:\somewhere\outside)
                for token in cmd.split():
                    clean_token = token.strip("'\"").strip()
                    if (
                        (clean_token.startswith("/") and not clean_token.startswith("/c/"))
                        or (len(clean_token) >= 3 and clean_token[1:3] in [":\\", ":/"])
                    ):
                        try:
                            p = Path(clean_token).resolve()
                            p.relative_to(ws_root)
                        except (ValueError, Exception):
                            logger.warning(f"Terminal path security violation: {clean_token} outside {ws_root}")
                            return TerminalObservation.from_text(
                                f"Security violation: path '{clean_token}' is outside repository root '{ws_root}'",
                                is_error=True,
                                command=cmd,
                                exit_code=1,
                            )

        # Execute command through OpenHands
        obs = _orig_terminal_call(self, action, conversation=conversation)

        # 3. Post-execution working directory containment check
        if active_ws is not None and hasattr(active_ws, "path") and hasattr(self, "session"):
            ws_root = Path(active_ws.path).resolve()
            sess_cwd = getattr(self.session, "cwd", None) or getattr(self.session, "_cwd", None)
            if sess_cwd:
                try:
                    Path(sess_cwd).resolve().relative_to(ws_root)
                except (ValueError, Exception):
                    logger.warning(f"Terminal working directory escaped to {sess_cwd}. Resetting back to {ws_root}")
                    if hasattr(self.session, "execute"):
                        self.session.execute(TerminalAction(command=f'cd "{ws_root}"', is_input=False))

        return obs

    TerminalExecutor.__call__ = _safe_terminal_call
except Exception as e:
    pass



class AgentRuntime:
    """
    ASTRA Adapter for the OpenHands Software Agent SDK.
    Decouples ASTRA's LangGraph orchestration and repository intelligence
    from the underlying OpenHands agent execution engine.
    """

    def __init__(self, custom_settings: Optional[Any] = None):
        self.settings = custom_settings or settings
        self._active_conversation: Optional[Any] = None
        self._cancelled = False
        self._lock = threading.Lock()

    def _configure_llm(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Any:
        """Configures the OpenHands LLM client using canonical resolve_model."""
        from openhands.sdk import LLM
        from pydantic import SecretStr

        resolved = resolve_model(requested_model=model, api_key=api_key, base_url=base_url)

        llm_kwargs: Dict[str, Any] = {
            "model": resolved.model,
            "timeout": resolved.timeout,
            "temperature": resolved.temperature,
            "drop_params": resolved.drop_params,
        }
        if resolved.api_key:
            llm_kwargs["api_key"] = SecretStr(resolved.api_key)
        if resolved.base_url:
            llm_kwargs["base_url"] = resolved.base_url

        if resolved.provider == "ollama":
            llm_kwargs["extended_thinking_budget"] = None
            llm_kwargs["reasoning_effort"] = None

        return LLM(**llm_kwargs)

    def _configure_tools(self, requested_tools: Optional[List[str]] = None) -> List[Any]:
        """Configures tools for the OpenHands Agent."""
        from openhands.sdk import Tool
        from openhands.tools.file_editor import FileEditorTool
        from openhands.tools.terminal import TerminalTool

        tool_map = {
            "file_editor": FileEditorTool.name,
            "terminal": TerminalTool.name,
        }

        selected_keys = requested_tools or ["file_editor", "terminal"]
        tools = []
        for key in selected_keys:
            if key in tool_map:
                tools.append(Tool(name=tool_map[key]))
            else:
                tools.append(Tool(name=key))
        return tools

    def create_openhands_listener(
        self,
        emit_fn: Callable[[str, str, Optional[Dict[str, Any]]], None],
        tool_calls: Optional[List[AstraToolCall]] = None,
        captured_messages: Optional[List[str]] = None,
        workspace_path: Optional[str] = None,
    ) -> Callable[[Any], None]:
        """
        Creates an OpenHands event listener callback that translates raw OpenHands SDK
        Action, Observation, and Message events into structured, readable ASTRA events.
        """
        import re
        import uuid
        calls = tool_calls if tool_calls is not None else []
        messages = captured_messages if captured_messages is not None else []
        last_action_time = [datetime.now(timezone.utc)]
        last_tool_info = [{"tool": "terminal", "command": "", "path": "", "op": "edit"}]

        def openhands_event_listener(event: Any) -> None:
            event_name = type(event).__name__

            # Check for actions / tool invocations
            if "Action" in event_name:
                last_action_time[0] = datetime.now(timezone.utc)
                action_id = str(getattr(event, "id", uuid.uuid4()))
                tool_name = str(getattr(event, "tool_name", event_name)).lower()
                args = getattr(event, "args", {}) or getattr(event, "parameters", {})
                action_dict = dict(args) if isinstance(args, dict) else {"raw": str(args)}
                calls.append(AstraToolCall(id=action_id, name=str(tool_name), arguments=action_dict))

                action_obj = getattr(event, "action", None)
                cmd = action_dict.get("command", "")
                if not cmd and hasattr(action_obj, "command"):
                    cmd = getattr(action_obj, "command", "")

                path = action_dict.get("path", "")
                if not path and hasattr(action_obj, "path"):
                    path = getattr(action_obj, "path", "")

                editor_cmd = action_dict.get("command", "") or getattr(action_obj, "command", "") or "edit"

                is_file = bool(path) or "file" in tool_name or "file" in event_name.lower()
                is_terminal = not is_file and (bool(cmd) or "terminal" in tool_name or "cmd" in tool_name or "bash" in tool_name)
                canonical_tool = "file_editor" if is_file else ("terminal" if is_terminal else tool_name)

                last_tool_info[0] = {
                    "tool": canonical_tool,
                    "command": cmd if is_terminal else "",
                    "path": path,
                    "op": editor_cmd,
                }

                # Check if test command
                is_test_cmd = is_terminal and any(t in cmd.lower() for t in ["pytest", "npm test", "vitest", "cargo test", "go test", "unittest"])
                if is_test_cmd:
                    emit_fn("TEST_STARTED", f"Running {cmd}", {"command": cmd, "tool": "terminal"})

                if is_file and path:
                    verb = "Reading" if editor_cmd in ["view", "cat", "open"] else "Editing"
                    emit_fn("TOOL_CALL_STARTED", f"{verb} {path}", {"tool": "file_editor", "command": editor_cmd, "path": path})
                elif is_terminal:
                    emit_fn("TOOL_CALL_STARTED", f"Running {cmd}", {"tool": "terminal", "command": cmd})
                else:
                    emit_fn("TOOL_CALL_STARTED", f"Running {canonical_tool}", {"tool": canonical_tool, "command": cmd or editor_cmd})

            elif "Observation" in event_name:
                obs_content = getattr(event, "content", "") or str(event)
                if calls:
                    calls[-1].result = str(obs_content)[:2000]

                dur_ms = max(50, int((datetime.now(timezone.utc) - last_action_time[0]).total_seconds() * 1000))
                info = last_tool_info[0]
                tool = info.get("tool", "tool")
                cmd = info.get("command", "")
                path = info.get("path", "")
                op = info.get("op", "")

                # Check if test completion
                passed_m = re.search(r"(\d+)\s+passed", obs_content)
                failed_m = re.search(r"(\d+)\s+failed", obs_content)
                errors_m = re.search(r"(\d+)\s+error", obs_content)

                if passed_m or failed_m or errors_m:
                    p_cnt = int(passed_m.group(1)) if passed_m else 0
                    f_cnt = int(failed_m.group(1)) if failed_m else 0
                    e_cnt = int(errors_m.group(1)) if errors_m else 0
                    summ = f"{p_cnt} passed" + (f", {f_cnt} failed" if f_cnt else "")
                    emit_fn("TEST_COMPLETED", f"Tests {summ}", {
                        "command": cmd or "pytest",
                        "passed": p_cnt,
                        "failed": f_cnt,
                        "errors": e_cnt,
                        "duration_ms": dur_ms,
                        "exit_code": 1 if f_cnt > 0 else 0,
                    })

                # Check for file modification
                if path and op in ["create", "edit", "str_replace", "write", "insert"] and "error" not in obs_content.lower()[:100]:
                    rel_path = path
                    try:
                        if workspace_path and workspace_path in rel_path:
                            rel_path = rel_path.split(workspace_path)[-1].lstrip("/\\")
                    except Exception:
                        pass
                    file_op = "created" if op == "create" else "modified"
                    emit_fn("FILE_CHANGED", f"{file_op.capitalize()} {rel_path}", {
                        "path": rel_path,
                        "operation": file_op,
                    })

                # Emit canonical tool call completed
                exit_code = 1 if "error" in obs_content.lower()[:60] else 0
                first_line = obs_content.strip().split("\n")[0][:120] if obs_content else "completed"
                emit_fn("TOOL_CALL_COMPLETED", f"Completed {cmd or path or tool}: {first_line}", {
                    "tool": tool,
                    "command": cmd or path or tool,
                    "exit_code": exit_code,
                    "duration_ms": dur_ms,
                    "summary": first_line,
                    "output": str(obs_content)[:2000],
                })

            elif "Message" in event_name:
                msg_text = getattr(event, "text", "") or getattr(event, "content", "")
                if msg_text:
                    messages.append(str(msg_text))

        return openhands_event_listener

    def cancel(self) -> None:
        """Interrupts and cancels the active agent run."""
        with self._lock:
            self._cancelled = True
            if self._active_conversation:
                try:
                    logger.info("Cancelling active OpenHands conversation")
                    self._active_conversation.interrupt()
                except Exception as e:
                    logger.warning(f"Error interrupting conversation: {e}")

    def execute_task(
        self,
        workspace: IsolatedWorkspace | LocalExecutionWorkspace,
        prompt: str,
        on_event: Optional[Callable[[AstraAgentEvent], None]] = None,
        max_iterations: Optional[int] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AstraExecutionResult:
        """
        Executes a coding task within an execution workspace (Local or Isolated) using the OpenHands SDK.
        Streams events, tracks tool calls, and returns a structured AstraExecutionResult.
        """
        start_time = datetime.now(timezone.utc)
        self._cancelled = False
        tool_calls: List[AstraToolCall] = []
        captured_messages: List[str] = []
        error_msg: Optional[str] = None

        # Phase 5 Requirement: Log execution mode and workspace path
        is_local = isinstance(workspace, LocalExecutionWorkspace) or not ("workspaces" in str(workspace.path) and workspace.task_id in str(workspace.path))
        exec_mode = "LOCAL" if is_local else "SANDBOX"
        logger.info(f"ASTRA EXECUTION MODE: {exec_mode}")
        logger.info(f"ASTRA WORKSPACE: {workspace.path.resolve()}")

        def emit(event_type: str, message: str, payload: Optional[Dict[str, Any]] = None):
            ev = AstraAgentEvent(event_type=event_type, message=message, payload=payload or {})
            if on_event:
                try:
                    on_event(ev)
                except Exception as cb_err:
                    logger.warning(f"Error in on_event callback: {cb_err}")

        AgentRuntime._current_active_workspace = workspace

        try:
            from openhands.sdk import Agent, Conversation, LocalWorkspace
            from openhands.sdk.event.base import Event

            try:
                from openhands.sdk.conversation.visualizer import ConversationVisualizerBase
                class SilentVisualizer(ConversationVisualizerBase):
                    def on_event(self, event):
                        pass
                    def close(self):
                        pass
            except Exception:
                class SilentVisualizer:
                    def __getattr__(self, name):
                        return lambda *args, **kwargs: None

            llm = self._configure_llm(model=model, api_key=api_key)
            tools = self._configure_tools()

            agent_kwargs: Dict[str, Any] = {
                "llm": llm,
                "tools": tools,
                "system_prompt": (
                    "You are ASTRA, a helpful, direct, and practical autonomous software engineer.\n"
                    "Your primary goal is to fulfill the user's exact request directly and efficiently in this workspace.\n"
                    "- If asked to create a folder or directory: execute `mkdir <folder_name>` directly via the `terminal` tool and finish. If no folder name was given, create a folder named `new_folder`.\n"
                    "- If asked to create, write, or modify code, HTML, CSS, frontend files, documentation, or scripts: write the files directly using `file_editor` or `terminal` and finish.\n"
                    "- Do NOT run exploratory commands (like ls -R, ls -F, Get-ChildItem), do NOT edit unrelated files, and do NOT create unrequested test suites unless explicitly asked.\n"
                    "- If asked to fix a bug or run tests: inspect the relevant files, fix the bug, and verify.\n"
                    "- Always take direct action to produce the user's requested deliverable cleanly and concisely."
                ),
            }

            agent = Agent(**agent_kwargs)

            openhands_event_listener = self.create_openhands_listener(
                emit_fn=emit,
                tool_calls=tool_calls,
                captured_messages=captured_messages,
                workspace_path=str(workspace.path) if workspace else None,
            )

            # Decouple OpenHands Local vs Isolated workspace execution
            if is_local:
                oh_workspace = LocalWorkspace(working_dir=workspace.path)
                delete_workspace_on_close = False
            else:
                oh_workspace = LocalWorkspace(working_dir=workspace.path)
                delete_workspace_on_close = True

            conversation = Conversation(
                agent=agent,
                workspace=oh_workspace,
                callbacks=[openhands_event_listener],
                max_iteration_per_run=max_iterations or self.settings.MAX_ITERATIONS,
                delete_on_close=delete_workspace_on_close,
                visualizer=SilentVisualizer(),
            )

            with self._lock:
                self._active_conversation = conversation

            emit("TASK_STARTED", f"Task execution started for {workspace.task_id}", {"task_id": workspace.task_id})
            emit("AGENT_RUNNING", f"Agent dispatched task prompt to OpenHands: {prompt[:100]}...")
            conversation.send_message(prompt)

            if not self._cancelled:
                conversation.run()

            # Record files actually modified
            diff = workspace.get_git_diff()
            files_changed = workspace.get_modified_files()

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            emit("TASK_COMPLETED", "Task execution finished successfully")

            return AstraExecutionResult(
                success=True,
                task_id=workspace.task_id,
                message="\n".join(captured_messages) if captured_messages else "Task executed by OpenHands Agent.",
                tool_calls=tool_calls,
                modified_files=files_changed,
                duration_seconds=duration,
                total_iterations=len(tool_calls)
            )

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            error_msg = str(e)
            logger.error(f"OpenHands task execution failed: {e}", exc_info=True)
            emit("ERROR", f"Agent execution error: {error_msg}", {"error": error_msg})

            return AstraExecutionResult(
                success=False,
                task_id=workspace.task_id,
                message=f"Agent execution encountered an error: {error_msg}",
                tool_calls=tool_calls,
                error=error_msg,
                duration_seconds=duration,
            )
        finally:
            with self._lock:
                self._active_conversation = None
            AgentRuntime._current_active_workspace = None

