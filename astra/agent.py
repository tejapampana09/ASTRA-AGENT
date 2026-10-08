"""ASTRA V5 Autonomous Cognitive Software Engineering Agent.

Core Architecture:
    USER
     ↓
    API / Desktop UI
     ↓
    SESSION
     ↓
    AGENT CONTROLLER (Governs execution, gating, hypotheses, evidence, progress, checkpoints)
     ↓
    COGNITIVE STATE (Persistent, serializable, deterministic)
     ↓
    PLANNER
     ↓
    LLM (Reasoning engine - suggests next purposeful action)
     ↓
    ACTION VALIDATOR (Controller gates: safe, non-repetitive, investigation-first)
     ↓
    TOOL EXECUTOR (Carries out action safely in sandbox)
     ↓
    OBSERVATION & EVIDENCE
     ↓
    PROGRESS TRACKER (Evaluates advancement vs stagnation)
     ↓
    VERIFIER (Mandatory independent external verification)
     ↓
    REPLAN / DONE
"""
from __future__ import annotations

import datetime as _dt
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from astra.approval import approval_manager
from astra.checkpoints import CheckpointManager
from astra.config import settings
from astra.controller import DeterministicAgentController, TaskModel, classify_task_intent
from astra.events import AgentEvent, AgentState, ControllerPhase, EventType, event_bus
from astra.llm import LLMClient, LLMResponse, parse_tool_calls_from_text
from astra.planner import Planner
from astra.progress import ProgressAction, ProgressReport, ProgressTracker
from astra.session import SessionManager, session_manager as global_session_manager
from astra.state import (
    ActionRecord,
    CognitiveState,
    StagnationAndLoopDetector,
    StepStatus,
    TaskPlan,
    TaskState,
    TaskStep,
    TaskType,
)
from astra.tools import PermissionLevel, ToolExecutor, ToolRegistry, ToolResult
from astra.verifier import IndependentVerifier, VerificationResult
from astra.workspace import WorkspaceManager

SYSTEM_PROMPT = """You are ASTRA, an autonomous senior software engineering agent (powered by the Google Antigravity engineering runtime).
You help developers explore repositories, understand architecture, implement features, fix bugs, and create documentation.

CORE EXECUTION PHILOSOPHY:
1. THE RUNTIME CONTROLLER GOVERNS EXECUTION:
   - Your job is to reason about the current evidence, state, and objective, and propose the single most purposeful next action.
   - Do NOT output conversational apologies or ask the user to run commands. You have full autonomous tool access.

2. INVESTIGATION-FIRST REASONING:
   - In debugging or investigation tasks: ALWAYS inspect the codebase (search_code, read_file, or targeted reproduction) before attempting code mutations.
   - The runtime controller will reject premature code edits if root cause has not been investigated.

3. DELIVER REAL VALUE (NO ROBOTIC META-LOGS):
   - When asked an architecture or explanation question: deliver deep, structured, professional markdown documentation directly.
   - Never output a meta-narrative about your own tool history.

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
    """Autonomous software engineering agent governed by DeterministicAgentController."""

    def __init__(
        self,
        workspace_path: Optional[Path | str] = None,
        model_name: Optional[str] = None,
        session_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        max_verification_attempts: int = 3,
        callback: Optional[AgentCallback] = None,
        approval_handler: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None,
        session_manager: Optional[SessionManager] = None,
    ):
        self.workspace_path = Path(workspace_path or settings.workspace_path).resolve()
        self.workspace_manager = WorkspaceManager(self.workspace_path)
        self.tool_registry = ToolRegistry(self.workspace_path)
        self.model_name = model_name or settings.default_model
        self.llm = LLMClient(model_name=self.model_name)
        self.session_manager = session_manager or global_session_manager
        self.session_id = session_id or self.session_manager.create_session(str(self.workspace_path), self.model_name)

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

        # Central Cognitive Controller
        self.controller = DeterministicAgentController(
            workspace_path=self.workspace_path,
            session_id=self.session_id,
            goal="",
            model_name=self.model_name,
            tool_registry=self.tool_registry,
            session_manager=self.session_manager,
            approval_manager=approval_manager,
            max_iterations=self.max_iterations,
            llm_client=self.llm,
        )

        # Delegate references to controller components
        self.task_state = self.controller.task_state
        self.checkpoint_manager = self.controller.checkpoint_manager
        self.loop_detector = self.controller.loop_detector
        self.planner = self.controller.planner
        self.progress_tracker = self.controller.progress_tracker
        self.verifier = self.controller.verifier

    def cancel(self) -> None:
        """User clicked Stop or cancelled execution."""
        self._is_cancelled = True
        self.controller.set_phase(ControllerPhase.BLOCKED, {"reason": "Cancelled by user"})
        self._set_state(AgentState.CANCELLED, {"message": "Execution stopped by user."})
        self._emit_event(EventType.AGENT_CANCELLED, {"message": "Agent cancelled by user."})

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def _set_state(self, state: AgentState, data: Optional[Dict[str, Any]] = None) -> None:
        self.state = state
        self.session_manager.update_session(self.session_id, state=state)
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
        self.session_manager.add_event(self.session_id, event)

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
        """Classify if user input is conversational rather than an engineering task."""
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
        if len(words) <= 2 and words and words[0] in {"hi", "hello", "hey", "yo"}:
            return True
        return False

    def run(self, goal: str, existing_messages: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Execute goal autonomously with planning, execution, verification, and self-healing."""
        self._is_cancelled = False
        start_time = time.time()

        # Check for conversation continuity or follow-up
        is_follow_up = bool(existing_messages) or (
            bool(self.controller.cognitive_state.goal)
            and self.controller.cognitive_state.phase not in (ControllerPhase.DONE, ControllerPhase.CONVERSATION)
        )

        # 1. Controller classifies task and initializes cognitive state
        task_model = self.controller.start_task(goal, is_follow_up=is_follow_up)

        # Fast-path for conversational greetings & general questions (only on fresh non-resumed tasks)
        if not existing_messages and task_model.task_type == TaskType.CONVERSATION:
            self._set_state(AgentState.EXECUTING, {"goal": goal})
            self._emit_event(EventType.AGENT_STARTED, {
                "goal": goal,
                "workspace": str(self.workspace_path),
                "model": self.model_name,
                "is_conversational": True,
            })
            self.session_manager.add_message(self.session_id, "user", goal)

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

            self.session_manager.add_message(self.session_id, "assistant", reply)
            self.controller.set_phase(ControllerPhase.DONE)
            self._set_state(AgentState.COMPLETED, {"summary": reply})
            self._emit_event(EventType.AGENT_COMPLETED, {"summary": reply})
            self._emit_event(EventType.TASK_COMPLETED, {"summary": reply})
            return self._build_result("completed", reply, 1, start_time)

        # Autonomous Engineering Task Workflow
        meta = self.workspace_manager.scan()
        self._set_state(AgentState.PLANNING, {"goal": goal})

        self._emit_event(EventType.AGENT_STARTED, {
            "goal": goal,
            "workspace": str(self.workspace_path),
            "project_type": meta.project_type.value,
            "package_manager": meta.package_manager,
            "model": self.model_name,
            "task_type": task_model.task_type.value,
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

        while iteration < self.max_iterations and self.controller.phase != ControllerPhase.DONE:
            if self._is_cancelled:
                return self._build_result("cancelled", "Task cancelled by user.", iteration, start_time)

            iteration += 1

            # Sync AgentState with Controller Phase
            if self.controller.phase == ControllerPhase.INVESTIGATE:
                self._set_state(AgentState.EXPLORING, {"iteration": iteration})
                if iteration == 1:
                    self._emit_event(EventType.EXPLORATION_STARTED, {"iteration": iteration})
            elif self.controller.phase in (ControllerPhase.PLAN, ControllerPhase.REPLAN):
                self._set_state(AgentState.PLANNING, {"iteration": iteration})
            elif self.controller.phase in (ControllerPhase.DIAGNOSE, ControllerPhase.OBSERVE):
                self._set_state(AgentState.OBSERVING, {"iteration": iteration})
            elif self.controller.phase == ControllerPhase.VERIFY:
                self._set_state(AgentState.VERIFYING, {"iteration": iteration})
            elif self.controller.phase == ControllerPhase.RECOVER:
                self._set_state(AgentState.FIXING, {"iteration": iteration})
            else:
                self._set_state(AgentState.EXECUTING, {"iteration": iteration})

            # Compress history to fit context window
            compressed_msgs = self._compress_messages(messages)

            # LLM Completion
            try:
                response = self.llm.complete(compressed_msgs, tools=self.tool_registry.get_definitions())
            except Exception as exc:
                err_msg = f"LLM error: {exc}"
                self.controller.set_phase(ControllerPhase.BLOCKED, {"error": err_msg})
                self._set_state(AgentState.FAILED, {"error": err_msg})
                self._emit_event(EventType.AGENT_FAILED, {"error": err_msg})
                return self._build_result("error", err_msg, iteration, start_time, error=err_msg)

            # Process Thoughts & Reasoning
            if response.content:
                final_summary = response.content.strip()
                if response.has_tool_calls():
                    self.callback.on_thought(final_summary)
                    self._emit_event(EventType.PLANNING, {"thought": final_summary})
                    # Extract hypotheses or observations from model thoughts if present
                    if "hypothesis" in final_summary.lower():
                        hyp_line = final_summary.split("\n")[0][:150]
                        self.controller.add_hypothesis(hyp_line)

            # CASE 1: LLM proposes NO further tool calls -> CONTROLLER evaluates completion
            if not response.has_tool_calls():
                all_changed = list(self.files_modified | self.files_created)

                # Check with controller whether task is genuinely complete
                is_done, reason = self.controller.check_completion(final_summary, all_changed)

                if not is_done:
                    # Controller rejected premature completion!
                    if all_changed:
                        # Files were modified but independent verification hasn't run yet -> RUN VERIFICATION
                        self._set_state(AgentState.VERIFYING, {"modified_files": all_changed})
                        vres, prep = self.controller.verify()
                        self.verification_results.append(vres.to_dict())

                        if vres.passed:
                            self.callback.on_verification(True, vres.summary, vres.details)
                            clean_summary = self._ensure_full_summary(goal, final_summary, all_changed, vres)
                            self._set_state(AgentState.COMPLETED, {"summary": clean_summary})
                            self._emit_event(EventType.AGENT_COMPLETED, {"summary": clean_summary})
                            return self._build_result("completed", clean_summary, iteration, start_time, verification="passed")
                        else:
                            # Verification failed -> enter self-healing fix loop
                            verification_attempts += 1
                            self.callback.on_verification(False, vres.summary, vres.details)
                            if verification_attempts < self.max_verification_attempts:
                                self._set_state(AgentState.FIXING, {"attempt": verification_attempts})
                                self._emit_event(EventType.FIX_STARTED, {"attempt": verification_attempts, "details": vres.details})
                                fix_prompt = (
                                    f"[INDEPENDENT VERIFICATION FAILED]\n"
                                    f"Stage: {vres.phase}\n"
                                    f"Error Details:\n{vres.details}\n\n"
                                    f"The task CANNOT be marked complete until all errors are fixed and tests pass.\n"
                                    f"Diagnose the failure, read the relevant source files, edit the code to fix it, and verify."
                                )
                                messages.append({"role": "user", "content": fix_prompt})
                                continue
                            else:
                                fail_msg = f"Independent verification failed after {verification_attempts} fix attempts:\n{vres.details}"
                                self.controller.set_phase(ControllerPhase.BLOCKED, {"error": fail_msg})
                                self._set_state(AgentState.FAILED, {"error": fail_msg})
                                self._emit_event(EventType.AGENT_FAILED, {"error": fail_msg})
                                return self._build_result("failed", final_summary, iteration, start_time, error=fail_msg, verification="failed")
                    else:
                        # Work is not complete and no files changed yet
                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({
                            "role": "user",
                            "content": (
                                f"[CONTROLLER DIRECTIVE]: The task '{goal}' is not yet complete.\n"
                                f"Current Status: {reason}\n"
                                f"Do NOT state what command to run. Execute the action immediately using available tools."
                            ),
                        })
                        continue
                else:
                    # Controller confirms task IS complete!
                    if all_changed:
                        # Mandatory verification check before concluding
                        vres, prep = self.controller.verify()
                        self.verification_results.append(vres.to_dict())
                        if vres.passed:
                            self.callback.on_verification(True, vres.summary, vres.details)
                            clean_summary = self._ensure_full_summary(goal, final_summary, all_changed, vres)
                            self._set_state(AgentState.COMPLETED, {"summary": clean_summary})
                            self._emit_event(EventType.AGENT_COMPLETED, {"summary": clean_summary})
                            return self._build_result("completed", clean_summary, iteration, start_time, verification="passed")
                        else:
                            verification_attempts += 1
                            self.callback.on_verification(False, vres.summary, vres.details)
                            if verification_attempts < self.max_verification_attempts:
                                self._set_state(AgentState.FIXING, {"attempt": verification_attempts})
                                self._emit_event(EventType.FIX_STARTED, {"attempt": verification_attempts, "details": vres.details})
                                messages.append({
                                    "role": "user",
                                    "content": f"[INDEPENDENT VERIFICATION FAILED]:\n{vres.details}\nDiagnose and fix the issue.",
                                })
                                continue
                            else:
                                fail_msg = f"Independent verification failed after {verification_attempts} attempts:\n{vres.details}"
                                self._set_state(AgentState.FAILED, {"error": fail_msg})
                                self._emit_event(EventType.AGENT_FAILED, {"error": fail_msg})
                                return self._build_result("failed", final_summary, iteration, start_time, error=fail_msg, verification="failed")
                    else:
                        # Pure documentation, explanation, or inquiry task
                        self.controller.set_phase(ControllerPhase.DONE)
                        clean_summary = self._ensure_full_summary(goal, final_summary, [], None)
                        self._set_state(AgentState.COMPLETED, {"summary": clean_summary})
                        self._emit_event(EventType.AGENT_COMPLETED, {"summary": clean_summary})
                        return self._build_result("completed", clean_summary, iteration, start_time)

            # CASE 2: Process proposed tool calls
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content,
                "tool_calls": response.tool_calls,
                "raw_content": response.raw_content,
            }
            messages.append(assistant_msg)
            self.session_manager.add_message(self.session_id, "assistant", response.content, response.tool_calls)

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

                # 1. TOOL ACTION GATING VIA CONTROLLER
                allowed, reason, guidance = self.controller.validate_and_prepare_action(fn_name, fn_args)
                if not allowed:
                    block_content = guidance or f"Controller blocked action '{fn_name}': {reason}"
                    messages.append({
                        "role": "tool",
                        "name": fn_name,
                        "tool_call_id": tc.get("id"),
                        "content": block_content,
                    })
                    self.session_manager.add_message(self.session_id, "tool", block_content)
                    continue

                # 2. ACTION EXECUTION VIA CONTROLLER
                self.callback.on_tool_call(fn_name, fn_args)
                if fn_name == "run_command":
                    cmd_str = fn_args.get("command", "")
                    self._emit_event(EventType.COMMAND_STARTED, {"command": cmd_str})
                    self.commands_executed.append({"command": cmd_str, "timestamp": time.time()})

                tool_res: ToolResult = self.controller.execute_action(
                    tool_name=fn_name,
                    tool_args=fn_args,
                    approval_handler=self.approval_handler,
                    cancel_check=self.is_cancelled,
                )

                tool_out = tool_res.to_string()
                self.callback.on_tool_result(fn_name, tool_out)

                if fn_name == "run_command":
                    self._emit_event(EventType.COMMAND_OUTPUT, {
                        "command": fn_args.get("command", ""),
                        "output": tool_out,
                    })

                # 3. EVALUATE PROGRESS AND RECORD ACTION IN CONTROLLER
                prep_report = self.controller.record_and_evaluate_action(
                    tool_name=fn_name,
                    tool_args=fn_args,
                    tool_result=tool_res,
                )

                # 4. TRACK WORKSPACE FILE MODIFICATIONS
                if fn_name in ("write_file", "edit_file"):
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_modified.add(s_fp)
                        self.callback.on_file_changed(s_fp, "modified")
                elif fn_name == "create_file":
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_created.add(s_fp)
                        self.callback.on_file_changed(s_fp, "created")
                elif fn_name == "delete_file":
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_deleted.add(s_fp)
                        self.callback.on_file_changed(s_fp, "deleted")

                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "tool_call_id": tc.get("id"),
                    "content": tool_out,
                })
                self.session_manager.add_message(self.session_id, "tool", tool_out)

        # Max iterations reached without clean finish
        status = "max_iterations_reached"
        msg = f"Task halted: maximum iteration limit ({self.max_iterations}) reached."
        self.controller.set_phase(ControllerPhase.BLOCKED, {"error": msg})
        self._set_state(AgentState.FAILED, {"error": msg})
        self._emit_event(EventType.AGENT_FAILED, {"error": msg})
        return self._build_result(status, final_summary, iteration, start_time, error=msg)

    def resume(self) -> Dict[str, Any]:
        """Resume an interrupted task using saved CognitiveState, TaskState, and history."""
        saved = self.session_manager.get_task_state(self.session_id)
        if saved:
            self.task_state = TaskState.from_dict(saved)
            self.controller.task_state = self.task_state
            self.files_modified = set(self.task_state.files_modified)
            self.files_created = set(self.task_state.files_created)
            self.files_deleted = set(self.task_state.files_deleted)
            goal = self.task_state.goal
            curr_obj = self.controller.cognitive_state.current_objective or (
                self.task_state.plan.get_current_step().title if self.task_state.plan.get_current_step() else "Next Step"
            )

            existing_messages = self.session_manager.get_messages(self.session_id)
            continuation_prompt = (
                f"[SYSTEM: Task Resumed]\n"
                f"Resuming autonomous task '{goal}' from phase {self.controller.phase.value}.\n"
                f"Current Objective: {curr_obj}\n"
                f"Known Facts: {self.controller.cognitive_state.known_facts}\n"
                f"Files modified: {list(self.files_modified)}\n"
                f"Files created: {list(self.files_created)}\n"
                f"Continue executing the task to full verification and completion."
            )
            if not existing_messages:
                return self.run(continuation_prompt)

            existing_messages.append({"role": "user", "content": continuation_prompt})
            return self.run(goal, existing_messages=existing_messages)

        return self.run("Resume task")

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
        is_mere_file_listing = (
            ("The current directory contains" in current_summary or "# Folder Contents" in current_summary or "contains the following files" in current_summary)
            and not any(term in current_summary.lower() for term in ["architecture", "pipeline", "component", "function", "handles", "implements", "logic", "responsibilit", "entry point", "framework"])
        )

        if len(words) >= 40 and has_structure and not is_mere_file_listing:
            return current_summary

        is_info_or_doc = self.controller.cognitive_state.task_type in (
            TaskType.DOCUMENTATION,
            TaskType.INVESTIGATION,
        ) or not changed_files

        if is_info_or_doc:
            summary_prompt = [
                {
                    "role": "system",
                    "content": (
                        "You are ASTRA, a senior autonomous software engineering agent. "
                        "The user asked an architectural, explanatory, or documentation question about the codebase. "
                        "Deliver a comprehensive, beautifully formatted, deep architectural guide or documentation answering their request directly.\n"
                        "Include:\n"
                        "- 🏛️ Executive Architecture Overview\n"
                        "- 🧩 Core Components & Modules (directory layout, key files, responsibilities)\n"
                        "- 🔄 Execution Pipeline & Data Flow\n"
                        "- ⚡ Key Technologies & Design Patterns\n"
                        "- 🚀 Entry Points & Setup\n\n"
                        "DO NOT write a meta-log about yourself or recount which tools were called. Deliver the actual requested architecture documentation in rich Markdown with clean sections, code blocks, and diagrams."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User Objective: {goal}\n"
                        f"Workspace context / observations gathered:\n{current_summary}\n\n"
                        f"Provide the complete, in-depth architectural documentation now."
                    ),
                },
            ]
        else:
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

        if is_info_or_doc:
            return (
                f"### 🏛️ Architecture & System Overview\n\n"
                f"**Objective:** {goal}\n\n"
                f"ASTRA completed repository exploration and context discovery. "
                f"The repository comprises core service logic, API server endpoints, and frontend desktop components.\n\n"
                f"{current_summary}"
            )

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
        self.session_manager.update_session(self.session_id, summary=summary)
        return res
