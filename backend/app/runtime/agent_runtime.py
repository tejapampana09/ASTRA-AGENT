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
        key = api_key or os.environ.get("LLM_API_KEY")
        detected_base_url = base_url or os.environ.get("LLM_BASE_URL")

        # Auto-detect standard provider environment variables and match model prefix
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

            def openhands_event_listener(event: Event) -> None:
                # Capture action events (tool calls)
                event_name = type(event).__name__
                payload = {}
                if hasattr(event, "model_dump"):
                    try:
                        payload = event.model_dump()
                    except Exception:
                        payload = {"repr": repr(event)}

                emit("TOOL_EVENT", f"OpenHands event: {event_name}", {"event_type": event_name, "data": payload})

                # Check for actions / tool invocations
                if "Action" in event_name:
                    action_id = str(getattr(event, "id", uuid.uuid4()))
                    tool_name = getattr(event, "tool_name", event_name)
                    args = getattr(event, "args", {}) or getattr(event, "parameters", {})
                    tool_calls.append(AstraToolCall(id=action_id, name=str(tool_name), arguments=dict(args) if isinstance(args, dict) else {"raw": str(args)}))
                elif "Observation" in event_name:
                    obs_content = getattr(event, "content", "") or str(event)
                    if tool_calls:
                        tool_calls[-1].result = str(obs_content)[:2000]
                elif "Message" in event_name:
                    msg_text = getattr(event, "text", "") or getattr(event, "content", "")
                    if msg_text:
                        captured_messages.append(str(msg_text))

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
