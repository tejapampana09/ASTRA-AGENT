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
    TOOL EXECUTOR (Applies file path policy and command approval)
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
from astra.quota import RequestBudgetExceeded
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

3. IMPLEMENT ACTIONABLE REQUESTS DIRECTLY:
   - When asked to create, implement, or write an algorithm, data structure, or script (e.g. FCFS scheduling, sorting, algorithms, utilities):
     IMMEDIATELY create ONLY the requested source file using `create_file` (e.g. `create_file("fcfs.py", ...)`).
   - Do NOT create separate `test_*.py` files in `tests/` unless the user explicitly asks for unit tests.
   - Do NOT spend multiple turns reading unrelated repository files when asked to create a standalone algorithm or solution.
   - Write clean, runnable code with a self-contained `if __name__ == "__main__":` demonstration block.

4. DELIVER REAL VALUE (NO ROBOTIC META-LOGS):
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
- ask_question(question, options): Ask the user an interactive question with selectable options
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

    def on_tool_result(self, name: str, result: str, duration_ms: float = 0.0, exit_code: Optional[int] = None) -> None:
        pass

    def on_file_changed(self, file_path: str, action: str = "modified", diff: str = "") -> None:
        pass

    def on_verification(self, passed: bool, summary: str, details: str = "") -> None:
        pass

    def on_plan_updated(self, steps: List[Any]) -> None:
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

        self.llm.budget_key = self.session_id
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

        if not existing_messages:
            self.session_manager.add_message(self.session_id, "system", SYSTEM_PROMPT)
            self.session_manager.add_message(self.session_id, "user", goal)

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

        if hasattr(self.controller, "task_state") and self.controller.task_state.plan:
            self.callback.on_plan_updated(self.controller.task_state.plan.steps)

        if existing_messages:
            messages: List[Dict[str, Any]] = list(existing_messages)
            if not any(m.get("role") == "system" for m in messages):
                messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
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
            except RequestBudgetExceeded as exc:
                msg = str(exc)
                self.controller.set_phase(ControllerPhase.BLOCKED, {"reason": msg})
                self._set_state(AgentState.BLOCKED, {"message": msg})
                self._emit_event(EventType.TASK_BLOCKED, {"reason": msg})
                return self._build_result("budget_exhausted", msg, iteration, start_time, error=msg)
            except Exception as exc:
                err_msg = f"LLM error: {exc}"
                self.controller.set_phase(ControllerPhase.BLOCKED, {"error": err_msg})
                self._set_state(AgentState.FAILED, {"error": err_msg})
                self._emit_event(EventType.AGENT_FAILED, {"error": err_msg})
                return self._build_result("error", err_msg, iteration, start_time, error=err_msg)

            if self._is_cancelled:
                return self._build_result("cancelled", "Task cancelled by user.", iteration, start_time)

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
            self.session_manager.add_message(self.session_id, "assistant", response.content, response.tool_calls, raw_content=response.raw_content)

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
                    self.session_manager.add_message(self.session_id, "tool", block_content, name=fn_name, tool_call_id=tc.get("id"))
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

                if self._is_cancelled:
                    return self._build_result("cancelled", "Task cancelled by user.", iteration, start_time)

                tool_out = tool_res.to_string()
                self.callback.on_tool_result(
                    fn_name,
                    tool_out,
                    duration_ms=tool_res.duration_ms,
                    exit_code=tool_res.exit_code,
                )

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
                if hasattr(self.controller, "task_state") and self.controller.task_state.plan:
                    self.callback.on_plan_updated(self.controller.task_state.plan.steps)

                # 4. TRACK WORKSPACE FILE MODIFICATIONS
                if fn_name in ("write_file", "edit_file"):
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_modified.add(s_fp)
                        self.callback.on_file_changed(s_fp, "modified", diff=tool_res.diff or "")
                elif fn_name == "create_file":
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_created.add(s_fp)
                        self.callback.on_file_changed(s_fp, "created", diff=tool_res.diff or "")
                elif fn_name == "delete_file":
                    fp = fn_args.get("file_path") or fn_args.get("path")
                    if fp and tool_res.success:
                        s_fp = str(fp)
                        self.files_deleted.add(s_fp)
                        self.callback.on_file_changed(s_fp, "deleted", diff="")

                messages.append({
                    "role": "tool",
                    "name": fn_name,
                    "tool_call_id": tc.get("id"),
                    "content": tool_out,
                })
                self.session_manager.add_message(self.session_id, "tool", tool_out, name=fn_name, tool_call_id=tc.get("id"))

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
        """Return the actual answer and recorded verification; no extra API call."""
        summary = current_summary.strip() or f"Task processed: {goal}"
        if verification_result is not None:
            status = verification_result.status
            label = status.value if hasattr(status, "value") else str(status)
            summary += f"\n\nVerification: **{label}**. {verification_result.summary}"
        elif changed_files:
            summary += "\n\nVerification: **not run**."
        return summary

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
            "verification": verification or "not_run",
        }
        if error:
            res["error"] = error
        self.session_manager.update_session(self.session_id, summary=summary)
        return res
