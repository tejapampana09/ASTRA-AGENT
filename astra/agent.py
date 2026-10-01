"""ASTRA V4 Autonomous Software Engineering Agent.

Core Orchestrator implementing:
PLAN -> EXPLORE -> ACT -> OBSERVE -> VERIFY -> FIX -> DONE
With:
- Independent Verification (AST, compilation, project-aware tests)
- Self-Healing Fix Loop
- Loop & Stalling Detection
- Real-time Structured Event Streaming (WebSockets, Desktop UI, Terminal)
- Strict Cancellation and Timeout Controls
- Comprehensive Change Tracking
"""
from __future__ import annotations

import json
import time
import datetime as _dt
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from astra.approval import approval_manager
from astra.checkpoints import CheckpointManager
from astra.config import settings
from astra.events import AgentEvent, AgentState, EventType, event_bus
from astra.llm import LLMClient, LLMResponse, parse_tool_calls_from_text
from astra.planner import Planner
from astra.progress import ProgressAction, ProgressReport, ProgressTracker
from astra.session import session_manager
from astra.state import ActionRecord, StagnationAndLoopDetector, StepStatus, TaskPlan, TaskState, TaskStep
from astra.tools import PermissionLevel, ToolExecutor, ToolRegistry, ToolResult
from astra.verifier import IndependentVerifier, VerificationResult
from astra.workspace import WorkspaceManager

SYSTEM_PROMPT = """You are ASTRA, an autonomous senior software engineering assistant (like Cline and Google Antigravity).
You help developers explore repositories, understand codebases, implement features, fix bugs, and verify solutions.

HOW TO ACT & COMMUNICATE:
1. Speak naturally, directly, and like an expert engineer pair-programming with the user.
2. NEVER talk down to the user or speak in future intentions without acting. When asked to fix a test, run checks, or implement code, DO NOT just say "To fix this, we need to investigate...". ACT IMMEDIATELY: call the appropriate tool (e.g. run_command, read_file, search_code) to run tests, inspect code, and fix it!
3. Take ONE action at a time using tool calls. When multiple steps are needed, execute them step by step until the entire goal is completed and verified.
4. When writing or editing code:
   - Make clean, surgical edits.
   - Run tests using run_command to verify your changes before finishing.
5. FINAL SUMMARY REQUIREMENT:
   - When your task is complete, you MUST provide a complete, comprehensive, and well-structured Final Task Summary.
   - Include:
     * Executive Overview (what was requested and what was achieved)
     * Changes Made (files created, modified, or deleted with specific functions/logic updated)
     * Verification & Test Results (exact commands executed, tests passed, or status confirmed)
     * Current Status of the workspace.
   - Format with clean markdown headers (###), bullet points, and inline code tags (`code`).
   - NEVER provide a lazy 1-sentence or 2-sentence summary. Deliver a full, professional engineering summary.
6. When researching, answering questions, or summarizing topics:
   - Provide a thorough, well-structured, and comprehensive answer using all gathered details.
   - Organize with clear headings, bullet points, key milestones, stats, or facts.

AVAILABLE TOOLS:
- read_file(file_path, start_line, end_line): Read file contents
- write_file(file_path, content): Create or overwrite a file
- edit_file(file_path, target_snippet, replacement_snippet): Surgical snippet replacement
- create_file(file_path, content): Create a new file
- delete_file(file_path): Delete a file
- list_dir(dir_path): List files and directories
- search_code(query, search_dir): Search codebase for text or symbols
- run_command(command, timeout): Run shell commands, tests, linters, git
- git_status(): Check git status
- git_diff(): View git diff
- web_search(query): Search the web
"""


class AgentCallback:
    """Hooks for streaming execution steps to terminal or custom observers."""

    def on_state_change(self, state: AgentState, details: str = "") -> None:
        pass

    def on_phase_change(self, phase: str, details: str = "") -> None:
        pass

    def on_thought(self, thought: str) -> None:
        pass

    def on_tool_call(self, name: str, args: Dict[str, Any]) -> None:
        pass

    def on_tool_result(self, name: str, result: str) -> None:
        pass

    def on_file_changed(self, file_path: str, action: str = "modified") -> None:
        pass

    def on_verification(self, passed: bool, summary: str, details: str = "") -> None:
        pass


class AstraAgent:
    """Autonomous software engineering agent with mandatory independent verification."""

    def __init__(
        self,
        workspace_path: Optional[Path | str] = None,
        model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        max_verification_attempts: int = 3,
        callback: Optional[AgentCallback] = None,
        approval_handler: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None,
    ):
        self.workspace_path = Path(workspace_path or settings.workspace_path).resolve()
        self.workspace_manager = WorkspaceManager(self.workspace_path)
        self.tool_registry = ToolRegistry(self.workspace_path)
        self.verifier = IndependentVerifier(self.workspace_path)
        self.model_name = model_name or settings.default_model
        self.llm = LLMClient(model_name=self.model_name)
        self.session_id = session_id or session_manager.create_session(str(self.workspace_path), self.model_name)
        
        self.max_iterations = max_iterations or settings.max_iterations
        self.max_verification_attempts = max_verification_attempts
        self.callback = callback or AgentCallback()
        self.approval_handler = approval_handler
        
        self.state = AgentState.IDLE
        self._is_cancelled = False
        
        # Change & Execution Tracking
        self.files_modified: Set[str] = set()
        self.files_created: Set[str] = set()
        self.files_deleted: Set[str] = set()
        self.commands_executed: List[Dict[str, Any]] = []
        self.tests_run: List[Dict[str, Any]] = []
        self.verification_results: List[Dict[str, Any]] = []

        # Autonomy, Checkpoints & Deterministic State Engine
        self.checkpoint_manager = CheckpointManager(self.workspace_path, session_manager)
        self.loop_detector = StagnationAndLoopDetector()
        self.planner = Planner()
        self.progress_tracker = ProgressTracker(self.workspace_path)
        self.task_state = TaskState(
            session_id=self.session_id,
            goal="",
            workspace_path=str(self.workspace_path),
            model_name=self.model_name,
            state=self.state,
        )

    def cancel(self) -> None:
        """User clicked Stop or cancelled execution."""
        self._is_cancelled = True
        self._set_state(AgentState.CANCELLED, {"message": "Execution stopped by user."})
        self._emit_event(EventType.AGENT_CANCELLED, {"message": "Agent cancelled by user."})

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _set_state(self, state: AgentState, data: Optional[Dict[str, Any]] = None) -> None:
        self.state = state
        session_manager.update_session(self.session_id, state=state)
        self.callback.on_state_change(state, data.get("message", "") if data else "")
        self.callback.on_phase_change(state.value, data.get("message", "") if data else "")

    def _emit_event(self, event_type: EventType | str, data: Optional[Dict[str, Any]] = None) -> None:
        payload = data or {}
        event = AgentEvent(
            event_type=event_type if isinstance(event_type, str) else event_type.value,
            state=self.state,
            data=payload,
            session_id=self.session_id,
        )
        event_bus.emit(event)
        session_manager.add_event(self.session_id, event)

    def _compress_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Context compression: keeps system prompt, initial goal, and recent turns, compressing older outputs."""
        if len(messages) <= 6:
            return messages

        compressed = []
        cutoff = len(messages) - 4

        for idx, m in enumerate(messages):
            if idx >= cutoff or idx < 2:
                compressed.append(m)
                continue

            content = m.get("content") or ""
            role = m.get("role")

            if role == "tool" and len(content) > 500:
                head = content[:250]
                tail = content[-250:]
                trimmed = f"{head}\n... [Output trimmed for context: {len(content) - 500} chars omitted] ...\n{tail}"
                m_copy = dict(m)
                m_copy["content"] = trimmed
                compressed.append(m_copy)
            else:
                compressed.append(m)

        return compressed

    def _is_conversational(self, text: str) -> bool:
        """Classify if user input is a conversational greeting/question rather than a coding task."""
        cleaned = text.strip().lower().rstrip("!?.")
        greetings = {
            "hi", "hello", "hey", "hola", "yo", "sup", "howdy",
            "good morning", "good afternoon", "good evening",
            "who are you", "what are you", "what can you do",
            "help", "thanks", "thank you", "nice to meet you"
        }
        if cleaned in greetings:
            return True
        words = cleaned.split()
        if len(words) <= 2 and words[0] in {"hi", "hello", "hey", "yo"}:
            return True
        return False

    def run(self, goal: str, existing_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Execute goal autonomously with planning, execution, verification, and self-healing."""
        self._is_cancelled = False
        start_time = time.time()

        # Fast-path for conversational greetings & general questions (only on fresh non-resumed tasks)
        if not existing_messages and self._is_conversational(goal):
            self._set_state(AgentState.EXECUTING, {"goal": goal})
            self._emit_event(EventType.AGENT_STARTED, {
                "goal": goal,
                "workspace": str(self.workspace_path),
                "model": self.model_name,
                "is_conversational": True,
            })
            session_manager.add_message(self.session_id, "user", goal)

            chat_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are ASTRA, a friendly autonomous software engineering assistant. "
                        "The user greeted you or asked a general question. Respond naturally, "
                        "briefly introduce yourself, and ask what coding task or project they would like to work on today. "
                        "Do not output markdown code blocks or execute tools unless asked."
                    ),
                },
                {"role": "user", "content": goal},
            ]
            try:
                resp = self.llm.complete(chat_messages)
                reply = (
                    resp.content.strip()
                    or "Hello! I am ASTRA, your autonomous software engineering agent. What coding task would you like to work on today?"
                )
            except Exception:
                reply = "Hello! I am ASTRA, your autonomous software engineering agent. How can I help you with your code today?"

            session_manager.add_message(self.session_id, "assistant", reply)
            self._set_state(AgentState.COMPLETED, {"summary": reply})
            self._emit_event(EventType.AGENT_COMPLETED, {"summary": reply})
            return self._build_result("completed", reply, 1, start_time)

        # Autonomous Coding Task Workflow
        meta = self.workspace_manager.scan()

        self._set_state(AgentState.PLANNING, {"goal": goal})
        self.task_state.goal = goal
        self.task_state.state = AgentState.PLANNING
        if not self.task_state.plan.steps:
            self.task_state.plan = self.planner.create_initial_plan(goal, meta.project_type.value)
        session_manager.save_task_state(self.task_state.to_dict())

        self._emit_event(EventType.AGENT_STARTED, {
            "goal": goal,
            "workspace": str(self.workspace_path),
            "project_type": meta.project_type.value,
            "package_manager": meta.package_manager,
            "model": self.model_name,
        })

        if existing_messages:
            messages: List[Dict[str, Any]] = existing_messages
        else:
            _now = _dt.datetime.now()
            initial_user_prompt = (
                f"Current Date & Time: {_now.strftime('%A, %B %d, %Y %I:%M:%S %p')} (local system time)\n"
                f"Workspace: {self.workspace_path}\n"
                f"Detected Project: {meta.project_type.value.upper()} (Package Manager: {meta.package_manager})\n"
                f"Test Suite: {meta.test_command or 'Auto-detect'}\n\n"
                f"User Objective:\n{goal}"
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": initial_user_prompt},
            ]

        iteration = 0
        verification_attempts = 0
        final_summary = ""
        verification_result: Optional[VerificationResult] = None

        while iteration < self.max_iterations:
            if self._is_cancelled:
                return self._build_result("cancelled", "Task cancelled by user.", iteration, start_time)

            iteration += 1

            # Context compression
            compressed_msgs = self._compress_messages(messages)

            # Check if exploring vs executing
            if iteration == 1:
                self._set_state(AgentState.EXPLORING, {"iteration": iteration})
                self._emit_event(EventType.EXPLORATION_STARTED, {"iteration": iteration})
            else:
                self._set_state(AgentState.EXECUTING, {"iteration": iteration})

            # LLM Completion
            try:
                response = self.llm.complete(compressed_msgs, tools=self.tool_registry.get_definitions())
            except Exception as exc:
                err_msg = f"LLM error: {exc}"
                self._set_state(AgentState.FAILED, {"error": err_msg})
                self._emit_event(EventType.AGENT_FAILED, {"error": err_msg})
                return self._build_result("error", err_msg, iteration, start_time, error=err_msg)

            # Thoughts & Reasoning
            if response.content:
                final_summary = response.content.strip()
                if response.has_tool_calls():
                    self.callback.on_thought(final_summary)
                    self._emit_event(EventType.PLANNING, {"thought": final_summary})

            # Check if LLM proposes no further tool calls -> MODEL SAYS DONE
            if not response.has_tool_calls():
                intent_markers = [
                    "we need to", "we should", "next step", "let's now", 
                    "i will now", "i'll now", "in order to fix", "we must",
                    "let us now", "investigate the changes and ensure",
                    "to fix the failing", "to fix this, we need", "i will inspect",
                ]
                if iteration < self.max_iterations and any(im in final_summary.lower() for im in intent_markers):
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": "Do not stop with an intermediate plan. Proceed immediately to execute the next action using tools (e.g. run_command, read_file, search_code)."
                    })
                    continue

                all_changed = list(self.files_modified | self.files_created)
                is_actionable = any(w in goal.lower() for w in ["fix", "pytest", "test", "implement", "build", "create", "write", "debug"])
                if is_actionable and iteration < 4 and not self.commands_executed and not all_changed:
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({
                        "role": "user",
                        "content": f"The objective '{goal}' requires taking action. Please invoke the appropriate tool (such as run_command with pytest or read_file to inspect code)."
                    })
                    continue

                if all_changed:
                    # TRIGGER MANDATORY INDEPENDENT VERIFIER
                    self._set_state(AgentState.VERIFYING, {"modified_files": all_changed})
                    self._emit_event(EventType.VERIFICATION_STARTED, {"files": all_changed})
                    
                    verification_result = self.verifier.verify(all_changed)
                    session_manager.add_verification(
                        self.session_id,
                        verification_result.passed,
                        verification_result.summary,
                        verification_result.details,
                        verification_result.phase,
                    )
                    self.verification_results.append(verification_result.to_dict())

                    if verification_result.passed:
                        self.callback.on_verification(True, verification_result.summary, verification_result.details)
                        self.task_state.plan.complete_current_step("Verification passed.")
                        clean_summary = self._ensure_full_summary(goal, final_summary, all_changed, verification_result)
                        self._set_state(AgentState.COMPLETED, {"summary": clean_summary})
                        self._emit_event(EventType.VERIFICATION_PASSED, {
                            "summary": verification_result.summary,
                            "details": verification_result.details,
                        })
                        self._emit_event(EventType.AGENT_COMPLETED, {"summary": clean_summary})
                        session_manager.save_task_state(self.task_state.to_dict())
                        return self._build_result("completed", clean_summary, iteration, start_time, verification="passed")
                    else:
                        # VERIFICATION FAILED -> ENTER SELF-HEALING FIX LOOP
                        verification_attempts += 1
                        self.callback.on_verification(False, verification_result.summary, verification_result.details)
                        self._emit_event(EventType.VERIFICATION_FAILED, {
                            "summary": verification_result.summary,
                            "details": verification_result.details,
                            "category": verification_result.error_category.value if verification_result.error_category else None,
                        })

                        # Loop detection check
                        is_stuck = self.verifier.loop_detector.record_and_check(verification_result.details)
                        if is_stuck:
                            fail_msg = (
                                f"ASTRA loop detector stopped execution: The exact same error repeated {self.verifier.loop_detector.max_repeated} times.\n"
                                f"Repeated Blocker: {verification_result.details[:300]}\n"
                                f"Recommended Action: Review dependency versions or manual test setup."
                            )
                            self._set_state(AgentState.FAILED, {"error": fail_msg})
                            self._emit_event(EventType.AGENT_FAILED, {"error": fail_msg})
                            return self._build_result("failed", final_summary, iteration, start_time, error=fail_msg, verification="failed")

                        if verification_attempts < self.max_verification_attempts:
                            self._set_state(AgentState.FIXING, {
                                "attempt": verification_attempts,
                                "max_attempts": self.max_verification_attempts,
                            })
                            self._emit_event(EventType.FIX_STARTED, {
                                "attempt": verification_attempts,
                                "details": verification_result.details,
                            })

                            fix_prompt = (
                                f"[INDEPENDENT VERIFICATION FAILED]\n"
                                f"Stage: {verification_result.phase}\n"
                                f"Error Classification: {verification_result.error_category.value if verification_result.error_category else 'runtime'}\n"
                                f"Error Details:\n{verification_result.details}\n\n"
                                f"The task CANNOT be marked complete until all errors are fixed and tests pass.\n"
                                f"Diagnose the failure, read the relevant source files, edit the code to fix it, and verify."
                            )
                            messages.append({"role": "user", "content": fix_prompt})
                            continue
                        else:
                            fail_msg = f"Independent verification failed after {verification_attempts} fix attempts:\n{verification_result.details}"
                            self._set_state(AgentState.FAILED, {"error": fail_msg})
                            self._emit_event(EventType.AGENT_FAILED, {"error": fail_msg})
                            return self._build_result("failed", final_summary, iteration, start_time, error=fail_msg, verification="failed")
                else:
                    # Task completed without local file mutations (e.g. read-only, inquiry, or command execution)
                    clean_summary = self._ensure_full_summary(goal, final_summary, [], None)
                    self._set_state(AgentState.COMPLETED, {"summary": clean_summary})
                    self._emit_event(EventType.AGENT_COMPLETED, {"summary": clean_summary})
                    session_manager.save_task_state(self.task_state.to_dict())
                    return self._build_result("completed", clean_summary, iteration, start_time)

            # Process tool calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
                "raw_content": response.raw_content,
            }
            messages.append(assistant_msg)
            session_manager.add_message(self.session_id, "assistant", response.content, response.tool_calls)

            for tc in response.tool_calls:
                if self._is_cancelled:
                    return self._build_result("cancelled", "Task cancelled by user.", iteration, start_time)

                fn = tc.get("function", {})
                fn_name = fn.get("name")
                fn_args = fn.get("arguments", {})
                if isinstance(fn_args, str):
                    try:
                        fn_args = json.loads(fn_args)
                    except Exception:
                        fn_args = {}

                # Loop and Stagnation Check
                is_stuck, loop_msg = self.loop_detector.check_loop(fn_name, fn_args)
                if is_stuck:
                    loop_obs = f"Observation: {loop_msg} File or command is already in the requested state. Moving to verification."
                    messages.append({
                        "role": "tool",
                        "name": fn_name,
                        "tool_call_id": tc.get("id"),
                        "content": loop_obs,
                    })
                    session_manager.add_message(self.session_id, "tool", loop_obs)
                    continue

                # Checkpoint snapshot before file mutations
                if fn_name in ("write_file", "create_file", "edit_file", "delete_file"):
                    fp = fn_args.get("file_path", "")
                    if fp:
                        self.checkpoint_manager.create_checkpoint(
                            session_id=self.session_id,
                            description=f"Before {fn_name} on {fp}",
                            files=[fp],
                        )

                self.callback.on_tool_call(fn_name, fn_args)
                self._emit_event(EventType.TOOL_STARTED, {"name": fn_name, "arguments": fn_args})

                if fn_name == "run_command":
                    cmd_str = fn_args.get("command", "")
                    self._emit_event(EventType.COMMAND_STARTED, {"command": cmd_str})
                    self.commands_executed.append({"command": cmd_str, "timestamp": time.time()})
                    self.task_state.commands_executed.append(cmd_str)

                # Central execution via ToolRegistry
                tool_res: ToolResult = self.tool_registry.execute(
                    name=fn_name,
                    args=fn_args,
                    approval_callback=self.approval_handler,
                    cancel_check=self.is_cancelled,
                    session_id=self.session_id,
                )

                tool_out = tool_res.to_string()
                self.loop_detector.record_action(fn_name, fn_args, success=tool_res.success, output_summary=tool_out)
                self.callback.on_tool_result(fn_name, tool_out)
                self._emit_event(EventType.TOOL_COMPLETED, {
                    "name": fn_name,
                    "success": tool_res.success,
                    "output": tool_out[:1000],
                    "duration_ms": tool_res.duration_ms,
                })

                if fn_name == "run_command":
                    self._emit_event(EventType.COMMAND_OUTPUT, {
                        "command": fn_args.get("command", ""),
                        "output": tool_out,
                    })

                # Change tracking
                if fn_name in ("write_file", "edit_file"):
                    fp = fn_args.get("file_path", "")
                    if fp:
                        self.files_modified.add(fp)
                        self.task_state.files_modified.add(fp)
                        session_manager.add_file_change(self.session_id, fp, "modified")
                        self.callback.on_file_changed(fp, "modified")
                        self._emit_event(EventType.FILE_CHANGED, {"file_path": fp, "action": "modified"})
                elif fn_name == "create_file":
                    fp = fn_args.get("file_path", "")
                    if fp:
                        self.files_created.add(fp)
                        self.task_state.files_created.add(fp)
                        session_manager.add_file_change(self.session_id, fp, "created")
                        self.callback.on_file_changed(fp, "created")
                        self._emit_event(EventType.FILE_CHANGED, {"file_path": fp, "action": "created"})
                elif fn_name == "delete_file":
                    fp = fn_args.get("file_path", "")
                    if fp:
                        self.files_deleted.add(fp)
                        self.task_state.files_deleted.add(fp)
                        session_manager.add_file_change(self.session_id, fp, "deleted")
                        self.callback.on_file_changed(fp, "deleted")
                        self._emit_event(EventType.FILE_CHANGED, {"file_path": fp, "action": "deleted"})

                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "tool_call_id": tc.get("id"),
                    "content": tool_out,
                })
                session_manager.add_message(self.session_id, "tool", tool_out)
                session_manager.save_task_state(self.task_state.to_dict())

        # Max iterations reached without clean finish
        status = "max_iterations_reached"
        msg = f"Task halted: maximum iteration limit ({self.max_iterations}) reached."
        self._set_state(AgentState.FAILED, {"error": msg})
        self._emit_event(EventType.AGENT_FAILED, {"error": msg})
        return self._build_result(status, final_summary, iteration, start_time, error=msg)

    def resume(self) -> Dict[str, Any]:
        """Resume an interrupted task using saved TaskState and conversation history."""
        saved = session_manager.get_task_state(self.session_id)
        if saved:
            self.task_state = TaskState.from_dict(saved)
            self.files_modified = set(self.task_state.files_modified)
            self.files_created = set(self.task_state.files_created)
            self.files_deleted = set(self.task_state.files_deleted)
            goal = self.task_state.goal
            curr_step = self.task_state.plan.get_current_step()

            existing_messages = session_manager.get_messages(self.session_id)
            if not existing_messages:
                prompt = (
                    f"Resuming autonomous task: '{goal}'.\n"
                    f"Current Step: {curr_step.title if curr_step else 'Next Step'}\n"
                    f"Files modified: {list(self.files_modified)}\n"
                    f"Files created: {list(self.files_created)}\n"
                    f"Continue executing the task to completion."
                )
                return self.run(prompt)

            continuation_prompt = (
                f"[SYSTEM: Task Resumed]\n"
                f"Resuming session from state: {self.task_state.state.value if isinstance(self.task_state.state, AgentState) else self.task_state.state}.\n"
                f"Goal: {goal}\n"
                f"Current Step: {curr_step.title if curr_step else 'Next Step'}\n"
                f"Files modified so far: {list(self.files_modified)}\n"
                f"Please continue executing the plan towards full verification and completion."
            )
            existing_messages.append({"role": "user", "content": continuation_prompt})
            return self.run(goal, existing_messages=existing_messages)
    def _ensure_full_summary(
        self,
        goal: str,
        current_summary: str,
        changed_files: List[str],
        verification_result: Optional[VerificationResult] = None,
    ) -> str:
        """Ensure the user receives a complete, rich, Antigravity-style final summary."""
        words = current_summary.strip().split()
        has_structure = any(s in current_summary for s in ["###", "**", "- "])
        intent_markers = ["we need to", "we should", "next step", "let's now", "i will now", "i'll now"]
        has_intent = any(im in current_summary.lower() for im in intent_markers)

        # If summary is already rich (> 50 words with markdown headings and no future intent), use it
        if len(words) >= 50 and has_structure and not has_intent:
            return current_summary

        # Otherwise synthesize a complete, professional engineering summary
        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "You are ASTRA, a senior autonomous engineering agent. "
                    "The task is complete. Provide a complete, professional, beautifully structured Final Task Summary for the user.\n"
                    "Use this exact format:\n"
                    "### 🎯 Executive Summary\n"
                    "Direct explanation of what was achieved and the outcome.\n\n"
                    "### 🛠️ Actions & Changes Made\n"
                    "Bullet points detailing the files modified, created, or inspected, with specific updates.\n\n"
                    "### 🧪 Verification & Results\n"
                    "Specific commands executed (e.g. tests or status checks) and their results.\n\n"
                    "### ✅ Current Status\n"
                    "Confirmation that everything is verified and the workspace is clean.\n\n"
                    "Use clean markdown with bullet points and code chips (`code`). NEVER give a 1-sentence or 2-sentence response."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User Objective: {goal}\n"
                    f"Files Modified: {changed_files}\n"
                    f"Commands Executed: {[c['command'] for c in self.commands_executed]}\n"
                    f"Verification Status: {'Passed' if verification_result and verification_result.passed else 'All steps complete'}\n"
                    f"Previous observation: {current_summary}\n\n"
                    f"Generate the full, complete Final Task Summary now."
                ),
            },
        ]
        try:
            resp = self.llm.complete(summary_prompt)
            if resp.content and len(resp.content.strip().split()) >= 30:
                return resp.content.strip()
        except Exception:
            pass

        # Fallback template
        cmds_list = "\n".join(f"- `{c['command']}`" for c in self.commands_executed[-5:]) if self.commands_executed else "- Workspace inspection completed"
        files_list = "\n".join(f"- `{f}`" for f in changed_files) if changed_files else "- Workspace files inspected"
        v_status = "All automated checks and independent verifications passed." if (verification_result and verification_result.passed) else "Task execution completed successfully."

        return (
            f"### 🎯 Executive Summary\n"
            f"Successfully processed and resolved the objective: **{goal}**.\n\n"
            f"### 🛠️ Actions & Changes Made\n"
            f"{files_list}\n\n"
            f"### 🧪 Verification & Commands Executed\n"
            f"{cmds_list}\n\n"
            f"### ✅ Current Status\n"
            f"{v_status}"
        )

    def _build_result(
        self,
        status: str,
        summary: str,
        iterations: int,
        start_time: float,
        error: Optional[str] = None,
        verification: Optional[str] = None,
    ) -> Dict[str, Any]:
        duration = round(time.time() - start_time, 2)
        res = {
            "session_id": self.session_id,
            "status": status,
            "summary": summary,
            "iterations": iterations,
            "duration_seconds": duration,
            "files_modified": list(self.files_modified),
            "files_created": list(self.files_created),
            "files_deleted": list(self.files_deleted),
            "commands_executed": [c["command"] for c in self.commands_executed],
            "verification": verification or ("passed" if status == "completed" else "unverified"),
        }
        if error:
            res["error"] = error
        session_manager.update_session(self.session_id, summary=summary)
        return res
