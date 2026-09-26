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
from app.runtime.workspace import IsolatedWorkspace


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

# OpenHands FileEditor automatic path resolution patch for relative paths
try:
    from openhands.tools.file_editor.editor import FileEditor, is_host_absolute_path
    _orig_file_editor_call = FileEditor.__call__

    def _safe_file_editor_call(self, *, command, path, **kwargs):
        _p = Path(path)
        if not is_host_absolute_path(_p) and self._cwd is not None:
            path = str((Path(self._cwd) / _p).resolve())
        return _orig_file_editor_call(self, command=command, path=path, **kwargs)

    FileEditor.__call__ = _safe_file_editor_call
except Exception:
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
        """Configures the OpenHands LLM client."""
        from openhands.sdk import LLM
        from pydantic import SecretStr

        selected_model = model or os.environ.get("LLM_MODEL")
        key = api_key or os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
        detected_base_url = base_url or os.environ.get("LLM_BASE_URL")

        # Explicit model prioritization
        if model and ("ollama" in model.lower() or "qwen" in model.lower()):
            selected_model = "ollama/qwen2.5-coder:3b"
            detected_base_url = detected_base_url or "http://localhost:11434"
            key = key or "ollama-local"
        elif model and "gemini" in model.lower():
            selected_model = model if "/" in model else f"gemini/{model}"
            key = key or os.environ.get("GEMINI_API_KEY")

        # Detect Gemini key prefix (AQ. or AIza)
        if key and (str(key).startswith("AQ.") or str(key).startswith("AIza")):
            os.environ["GEMINI_API_KEY"] = str(key)
            if not model and (not selected_model or "claude" in selected_model):
                selected_model = os.environ.get("LLM_MODEL") or "gemini/gemini-3.1-flash-lite"

        # Auto-detect standard provider environment variables and match model prefix
        if not model:
            if not key:
                if os.environ.get("OPENROUTER_API_KEY") or (key and str(key).startswith("sk-or-v1")):
                    key = os.environ.get("OPENROUTER_API_KEY") or key
                    detected_base_url = detected_base_url or "https://openrouter.ai/api/v1"
                    if not selected_model or "claude" in selected_model:
                        selected_model = "openrouter/anthropic/claude-3.5-sonnet"
                elif os.environ.get("GEMINI_API_KEY"):
                    key = os.environ.get("GEMINI_API_KEY")
                    if not selected_model or "claude" in selected_model:
                        selected_model = "gemini/gemini-2.5-flash"
                elif os.environ.get("ANTHROPIC_API_KEY"):
                    key = os.environ.get("ANTHROPIC_API_KEY")
                    if not selected_model:
                        selected_model = "anthropic/claude-sonnet-4-5-20250929"
                elif os.environ.get("OPENAI_API_KEY"):
                    key = os.environ.get("OPENAI_API_KEY")
                    if not selected_model:
                        selected_model = "openai/gpt-4o"

            # Respect explicitly configured LLM_MODEL from environment if present
            env_model = os.environ.get("LLM_MODEL")
            if env_model:
                selected_model = env_model
            elif key and str(key).startswith("sk-or-v1-"):
                detected_base_url = detected_base_url or "https://openrouter.ai/api/v1"
                if not selected_model:
                    selected_model = "openrouter/nvidia/nemotron-3-super-120b-a12b:free"

        selected_model = selected_model or self.settings.LLM_MODEL

        llm_kwargs: Dict[str, Any] = {
            "model": selected_model,
            "timeout": self.settings.LLM_TIMEOUT_SECONDS,
            "temperature": self.settings.LLM_TEMPERATURE,
        }
        if key:
            llm_kwargs["api_key"] = SecretStr(key)
        effective_base_url = detected_base_url or self.settings.LLM_BASE_URL
        if str(selected_model).startswith("gemini/"):
            effective_base_url = None
        if effective_base_url:
            llm_kwargs["base_url"] = effective_base_url

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
        workspace: IsolatedWorkspace,
        prompt: str,
        on_event: Optional[Callable[[AstraAgentEvent], None]] = None,
        max_iterations: Optional[int] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AstraExecutionResult:
        """
        Executes a coding task within an isolated workspace using the OpenHands SDK.
        Streams events, tracks tool calls, and returns a structured AstraExecutionResult.
        """
        start_time = datetime.now(timezone.utc)
        self._cancelled = False
        tool_calls: List[AstraToolCall] = []
        captured_messages: List[str] = []
        error_msg: Optional[str] = None

        def emit(event_type: str, message: str, payload: Optional[Dict[str, Any]] = None):
            ev = AstraAgentEvent(event_type=event_type, message=message, payload=payload or {})
            if on_event:
                try:
                    on_event(ev)
                except Exception as cb_err:
                    logger.warning(f"Error in on_event callback: {cb_err}")

        emit("TASK_STARTED", f"Initializing agent workspace for task {workspace.task_id}")

        try:
            from openhands.sdk import Agent, Conversation, LocalWorkspace
            from openhands.sdk.event.base import Event

            llm = self._configure_llm(model=model, api_key=api_key)
            tools = self._configure_tools()

            agent = Agent(
                llm=llm,
                tools=tools,
            )

            openhands_event_listener = self.create_openhands_listener(
                emit_fn=emit,
                tool_calls=tool_calls,
                captured_messages=captured_messages,
                workspace_path=str(workspace.path) if workspace else None,
            )

            conversation = Conversation(
                agent=agent,
                workspace=LocalWorkspace(working_dir=workspace.path),
                callbacks=[openhands_event_listener],
                max_iteration_per_run=max_iterations or self.settings.MAX_ITERATIONS,
                delete_on_close=False,
            )

            with self._lock:
                self._active_conversation = conversation

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
