"""ASTRA V5 Deterministic Cognitive Agent Controller.

The central runtime governor that decouples deterministic execution,
cognitive state transitions, task classification, hypothesis & evidence
management, action gating, loop breaking, progress tracking, and verification
from probabilistic LLM completions.

Architecture:
    LLM = Reasoning Engine
    DeterministicAgentController = Execution Governor & Agent
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from astra.approval import ApprovalManager, approval_manager as global_approval_manager
from astra.checkpoints import CheckpointManager
from astra.events import AgentEvent, AgentState, ControllerPhase, EventType, event_bus
from astra.planner import Planner
from astra.progress import ProgressAction, ProgressReport, ProgressTracker
from astra.session import SessionManager, session_manager as global_session_manager
from astra.state import (
    ActionRecord,
    CognitiveState,
    Evidence,
    Hypothesis,
    StagnationAndLoopDetector,
    StepStatus,
    TaskPlan,
    TaskState,
    TaskStep,
    TaskType,
)
from astra.tools import ToolExecutor, ToolRegistry, ToolResult
from astra.verifier import IndependentVerifier, VerificationResult


@dataclass
class TaskModel:
    """Deterministic model of the inferred user task."""
    task_type: TaskType
    goal: str
    confidence: float = 1.0
    reason: str = ""
    target_subsystems: List[str] = field(default_factory=list)
    initial_objective: str = ""
    constraints: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type.value,
            "goal": self.goal,
            "confidence": self.confidence,
            "reason": self.reason,
            "target_subsystems": self.target_subsystems,
            "initial_objective": self.initial_objective,
            "constraints": self.constraints,
            "unknowns": self.unknowns,
        }


def classify_task_intent(
    goal: str,
    active_task: Optional[CognitiveState] = None,
    llm_client: Optional[Any] = None,
) -> TaskModel:
    """Deterministic natural language task classification.
    
    Infers task type (DEBUG, IMPLEMENTATION, INVESTIGATION, DOCUMENTATION,
    REFACTOR, CONVERSATION) from user intent without requiring explicit keywords.
    """
    cleaned = goal.strip()
    lowered = cleaned.lower()

    # 1. Check for conversational greetings / general assistance
    conversational_greetings = {
        "hi", "hello", "hey", "hola", "yo", "sup", "howdy",
        "good morning", "good afternoon", "good evening",
        "who are you", "what are you", "what can you do",
        "help", "thanks", "thank you", "nice to meet you"
    }
    words = lowered.rstrip("!?. ").split()
    if lowered.rstrip("!?. ") in conversational_greetings or (len(words) <= 2 and words and words[0] in {"hi", "hello", "hey", "yo"}):
        return TaskModel(
            task_type=TaskType.CONVERSATION,
            goal=cleaned,
            confidence=0.98,
            reason="User input is a conversational greeting or general introduction.",
            initial_objective="Respond naturally and ask what software task to work on.",
        )

    # 2. Check for conversation continuity / follow-up on existing active task
    follow_up_cues = {
        "what about", "how about", "try the other", "try another", "do that",
        "yes", "no", "proceed", "continue", "fix it", "check backend", "check frontend",
        "what did you find", "what else", "go ahead", "try it", "re-run", "rerun"
    }
    is_follow_up = False
    if active_task and active_task.goal and active_task.phase not in (ControllerPhase.DONE, ControllerPhase.CONVERSATION):
        if any(lowered.startswith(cue) or cue in lowered for cue in follow_up_cues) or len(words) <= 4:
            is_follow_up = True

    if is_follow_up and active_task is not None:
        return TaskModel(
            task_type=active_task.task_type,
            goal=cleaned,
            confidence=0.95,
            reason=f"Follow-up refinement for active task: '{active_task.goal}'",
            initial_objective=f"Investigate follow-up request: '{cleaned}' within task '{active_task.goal}'",
            unknowns=[f"Specific details regarding follow-up: {cleaned}"],
        )

    # 3. Documentation / Architecture / Explanation patterns
    doc_patterns = [
        r"\b(architecture|explain|overview|document|documentation|how does|what is|walkthrough|summarize|guide|describe)\b",
        r"\bexplain\s+(this|the|how|our|project)\b",
    ]
    is_doc = any(re.search(pat, lowered) for pat in doc_patterns) and not any(
        kw in lowered for kw in ["fix", "broken", "bug", "failing", "fail", "implement", "add"]
    )
    if is_doc:
        return TaskModel(
            task_type=TaskType.DOCUMENTATION,
            goal=cleaned,
            confidence=0.95,
            reason="User requested system documentation, explanation, or architecture overview.",
            initial_objective="Explore codebase layout, manifests, and core modules to synthesize documentation.",
            unknowns=["Workspace module structure", "Core execution entry points and data flow"],
        )

    # 4. Refactoring / Cleanup patterns
    refactor_patterns = [
        r"\b(clean\s*up|cleanup|refactor|restructure|reorganize|simplify|format|tidy)\b",
    ]
    if any(re.search(pat, lowered) for pat in refactor_patterns):
        return TaskModel(
            task_type=TaskType.REFACTOR,
            goal=cleaned,
            confidence=0.92,
            reason="User requested code cleanup, restructuring, or refactoring.",
            initial_objective="Inspect target module to identify complexity, dead code, or styling issues.",
            unknowns=["Current module dependencies and test coverage"],
        )

    # 5. Debugging / Bug fix / Broken functionality patterns
    debug_patterns = [
        r"\b(broken|bug|failing|fails|fail|error|exception|crash|traceback|not working|isn't working|is not working|issue)\b",
        r"\b(isn't sending|is not sending|disconnecting|disconnects|timed out|timing out|dropped)\b",
        r"\b(why is|why does|find why|fix|debug|resolve failure|solve error)\b",
    ]
    if any(re.search(pat, lowered) for pat in debug_patterns):
        return TaskModel(
            task_type=TaskType.DEBUG,
            goal=cleaned,
            confidence=0.94,
            reason="User reported broken behavior, failing tests, crashes, or requested debugging.",
            initial_objective="Trace execution path, inspect error logs/tests, and locate failure point.",
            unknowns=["Root cause of failure", "Subsystem where fault originates"],
        )

    # 6. Investigation / Verification / Flow check patterns
    investigation_patterns = [
        r"\b(check whether|investigate|audit|trace|inspect flow|is the .* correct|verify whether)\b",
        r"\bcheck if\b",
    ]
    if any(re.search(pat, lowered) for pat in investigation_patterns):
        return TaskModel(
            task_type=TaskType.INVESTIGATION,
            goal=cleaned,
            confidence=0.90,
            reason="User requested systematic inspection, flow verification, or investigation.",
            initial_objective="Inspect relevant symbols, APIs, and configuration to verify correctness.",
            unknowns=["Whether current flow matches expected specification"],
        )

    # 7. Implementation / Feature addition patterns
    impl_patterns = [
        r"\b(add|create|implement|build|integrate|support for|new feature|set up|setup|extend)\b",
    ]
    if any(re.search(pat, lowered) for pat in impl_patterns):
        return TaskModel(
            task_type=TaskType.IMPLEMENTATION,
            goal=cleaned,
            confidence=0.92,
            reason="User requested creation or implementation of new capability or feature.",
            initial_objective="Locate relevant integration point and draft surgical implementation.",
            unknowns=["Existing patterns and APIs to align the new feature with"],
        )

    # 8. Ambiguous fallback: If LLM is available, consult it for classification; otherwise default to IMPLEMENTATION
    if llm_client:
        try:
            classification_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Classify the following software engineering user request into one of these exact categories:\n"
                        "DEBUG, IMPLEMENTATION, INVESTIGATION, DOCUMENTATION, REFACTOR, CONVERSATION.\n"
                        "Respond with ONLY the category word in all caps."
                    ),
                },
                {"role": "user", "content": goal},
            ]
            resp = llm_client.complete(classification_prompt)
            cat_str = resp.content.strip().upper()
            for tt in TaskType:
                if tt.value in cat_str:
                    return TaskModel(
                        task_type=tt,
                        goal=cleaned,
                        confidence=0.85,
                        reason=f"Classified via LLM analysis as {tt.value}.",
                        initial_objective=f"Execute {tt.value.lower()} workflow for: {cleaned}",
                    )
        except Exception:
            pass

    return TaskModel(
        task_type=TaskType.IMPLEMENTATION,
        goal=cleaned,
        confidence=0.75,
        reason="Defaulted to implementation workflow for actionable engineering request.",
        initial_objective=f"Explore project context and implement: {cleaned}",
    )


class DeterministicAgentController:
    """The authoritative execution governor for ASTRA tasks.
    
    Decouples deterministic lifecycle, cognitive state, task classification,
    evidence & hypothesis management, action gating, loop breaking, progress tracking,
    and independent verification from probabilistic LLM completions.
    """

    @staticmethod
    def requires_investigation_first(task_type: TaskType) -> bool:
        """Return True if the task type requires investigation before mutation."""
        return task_type in (TaskType.DEBUG, TaskType.INVESTIGATION)

    def __init__(
        self,
        workspace_path: Path,
        session_id: str,
        goal: str = "",
        model_name: str = "default",
        tool_registry: Optional[ToolRegistry] = None,
        session_manager: Optional[SessionManager] = None,
        approval_manager: Optional[ApprovalManager] = None,
        max_iterations: int = 30,
        llm_client: Optional[Any] = None,
    ):
        self.workspace_path = workspace_path.resolve()
        self.session_id = session_id
        self.goal = goal
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.llm_client = llm_client

        self.session_manager = session_manager or global_session_manager
        self.approval_manager = approval_manager or global_approval_manager
        self.tool_registry = tool_registry or ToolRegistry(self.workspace_path)
        self.checkpoint_manager = CheckpointManager(self.workspace_path, self.session_manager)
        self.verifier = IndependentVerifier(self.workspace_path)
        self.loop_detector = StagnationAndLoopDetector()
        self.progress_tracker = ProgressTracker(self.workspace_path)
        self.planner = Planner()

        # Investigation tracking for gating
        self.investigation_steps_count: int = 0
        self.files_read_count: int = 0
        self.inspected_files: Set[str] = set()
        self.files_read: Set[str] = set()

        # Initialize or restore TaskState with CognitiveState
        existing = self.session_manager.get_task_state(self.session_id)
        if existing:
            self.task_state = TaskState.from_dict(existing)
            # Restore inspection counts from action records
            for rec in self.task_state.action_records:
                if rec.tool_name in ("read_file", "search_code", "list_dir"):
                    self.investigation_steps_count += 1
                if rec.tool_name in ("read_file", "search_code"):
                    self.files_read_count += 1
                fp = rec.normalized_args.get("file_path") or rec.normalized_args.get("path")
                if fp:
                    self.inspected_files.add(str(fp))
                    if rec.tool_name == "read_file":
                        self.files_read.add(str(fp))
        else:
            initial_plan = self.planner.create_initial_plan(self.goal)
            cog_state = CognitiveState(
                goal=self.goal,
                phase=ControllerPhase.UNDERSTAND,
            )
            self.task_state = TaskState(
                session_id=self.session_id,
                goal=self.goal,
                workspace_path=str(self.workspace_path),
                model_name=self.model_name,
                state=AgentState.IDLE,
                plan=initial_plan,
                cognitive_state=cog_state,
            )
            self.session_manager.save_task_state(self.task_state.to_dict())

    @property
    def cognitive_state(self) -> CognitiveState:
        return self.task_state.cognitive_state

    @property
    def cognitive(self) -> CognitiveState:
        return self.task_state.cognitive_state

    @property
    def phase(self) -> ControllerPhase:
        return self.cognitive_state.phase

    @property
    def task_type(self) -> TaskType:
        return self.cognitive_state.task_type

    def emit_event(self, event_type: EventType | str, data: Optional[Dict[str, Any]] = None) -> None:
        etype = event_type.value if isinstance(event_type, EventType) else str(event_type)
        ev = AgentEvent(
            event_type=etype,
            state=self.task_state.state,
            session_id=self.session_id,
            data=data or {},
        )
        event_bus.emit(ev)
        self.session_manager.add_event(self.session_id, ev)

    def set_phase(self, phase: ControllerPhase, details: Optional[Dict[str, Any]] = None) -> None:
        """Deterministic phase transition with structured event emission."""
        old_phase = self.cognitive_state.phase
        self.cognitive_state.phase = phase
        self.task_state.updated_at = time.time()

        # Map ControllerPhase to AgentState for UI and backwards-compatibility
        phase_to_state = {
            ControllerPhase.CONVERSATION: AgentState.IDLE,
            ControllerPhase.UNDERSTAND: AgentState.PLANNING,
            ControllerPhase.INVESTIGATE: AgentState.EXPLORING,
            ControllerPhase.DIAGNOSE: AgentState.OBSERVING,
            ControllerPhase.PLAN: AgentState.PLANNING,
            ControllerPhase.EXECUTE: AgentState.EXECUTING,
            ControllerPhase.OBSERVE: AgentState.OBSERVING,
            ControllerPhase.VERIFY: AgentState.VERIFYING,
            ControllerPhase.REPLAN: AgentState.PLANNING,
            ControllerPhase.RECOVER: AgentState.FIXING,
            ControllerPhase.DONE: AgentState.COMPLETED,
            ControllerPhase.BLOCKED: AgentState.FAILED,
        }
        self.task_state.state = phase_to_state.get(phase, AgentState.EXECUTING)

        event_data = {
            "previous_phase": old_phase.value,
            "phase": phase.value,
            "objective": self.cognitive_state.current_objective,
            **(details or {}),
        }
        self.emit_event(EventType.PHASE_CHANGED, event_data)
        self.emit_event(EventType.STATE_CHANGED, {"state": self.task_state.state.value, **event_data})
        self.session_manager.save_task_state(self.task_state.to_dict())

    def start_task(self, goal: str, is_follow_up: bool = False) -> TaskModel:
        """Start or refine an autonomous task through natural language classification."""
        self.goal = goal
        self.task_state.goal = goal

        # Classify task
        task_model = classify_task_intent(
            goal=goal,
            active_task=self.cognitive_state if is_follow_up else None,
            llm_client=self.llm_client,
        )

        self.cognitive_state.goal = goal
        self.cognitive_state.task_type = task_model.task_type
        self.cognitive_state.confidence = task_model.confidence
        self.cognitive_state.current_objective = task_model.initial_objective
        if task_model.constraints:
            self.cognitive_state.constraints.extend(task_model.constraints)
        if task_model.unknowns:
            self.cognitive_state.unknowns.extend(task_model.unknowns)
        if is_follow_up:
            self.cognitive_state.known_facts.append(f"User follow-up instruction: {goal}")

        # Emit task start and classification events
        self.emit_event(EventType.TASK_STARTED, {
            "goal": goal,
            "session_id": self.session_id,
            "workspace": str(self.workspace_path),
        })
        self.emit_event(EventType.TASK_CLASSIFIED, {
            "task_type": task_model.task_type.value,
            "confidence": task_model.confidence,
            "reason": task_model.reason,
            "initial_objective": task_model.initial_objective,
        })

        # Phase selection based on classification
        if task_model.task_type == TaskType.CONVERSATION:
            self.set_phase(ControllerPhase.CONVERSATION)
        elif task_model.task_type in (TaskType.DEBUG, TaskType.INVESTIGATION):
            self.set_phase(ControllerPhase.INVESTIGATE, {"reason": task_model.reason})
            self.emit_event(EventType.INVESTIGATION_STARTED, {
                "objective": task_model.initial_objective,
                "unknowns": task_model.unknowns,
            })
        elif task_model.task_type == TaskType.DOCUMENTATION:
            self.set_phase(ControllerPhase.INVESTIGATE, {"reason": "Explore architecture"})
            self.emit_event(EventType.INVESTIGATION_STARTED, {"objective": "Explore architecture and modules"})
        else:
            self.set_phase(ControllerPhase.PLAN, {"reason": task_model.reason})

        # Update initial plan
        self.task_state.plan = self.planner.create_initial_plan(goal)
        self.session_manager.save_task_state(self.task_state.to_dict())
        return task_model

    def add_observation(self, observation: str) -> None:
        """Record a validated runtime observation."""
        obs = observation.strip()
        if not obs:
            return
        if obs not in self.cognitive_state.observations:
            self.cognitive_state.observations.append(obs)
            self.emit_event(EventType.OBSERVATION_CREATED, {"observation": obs})
            self.session_manager.save_task_state(self.task_state.to_dict())

    def add_evidence(self, fact: str, source: str = "") -> str:
        """Add an immutable piece of evidence ground in observation."""
        fact_str = fact.strip()
        ev_id = f"E{len(self.cognitive_state.evidence) + 1}"
        ev = Evidence(id=ev_id, fact=fact_str, source=source)
        self.cognitive_state.evidence.append(ev.to_dict())
        if fact_str not in self.cognitive_state.known_facts:
            self.cognitive_state.known_facts.append(fact_str)
        self.emit_event(EventType.EVIDENCE_FOUND, {
            "evidence_id": ev_id,
            "fact": fact_str,
            "source": source,
        })
        self.session_manager.save_task_state(self.task_state.to_dict())
        return ev_id

    def add_hypothesis(self, statement: str) -> str:
        """Formulate a testable hypothesis."""
        stmt = statement.strip()
        h_id = f"H{len(self.cognitive_state.hypotheses) + 1}"
        hyp = Hypothesis(id=h_id, statement=stmt, status="UNTESTED")
        self.cognitive_state.hypotheses.append(hyp.to_dict())
        self.emit_event(EventType.HYPOTHESIS_CREATED, {
            "hypothesis_id": h_id,
            "statement": stmt,
            "status": "UNTESTED",
        })
        self.session_manager.save_task_state(self.task_state.to_dict())
        return h_id

    def update_hypothesis(
        self,
        hypothesis_id: str,
        status: str,
        evidence_id: Optional[str] = None,
    ) -> bool:
        """Update hypothesis status (e.g. TESTING, LIKELY, CONFIRMED, REJECTED)."""
        valid_statuses = {"UNTESTED", "TESTING", "LIKELY", "CONFIRMED", "REJECTED"}
        clean_status = status.upper()
        if clean_status not in valid_statuses:
            clean_status = "TESTING"

        for h in self.cognitive_state.hypotheses:
            if h.get("id") == hypothesis_id:
                h["status"] = clean_status
                if evidence_id and evidence_id not in h.get("evidence_ids", []):
                    h.setdefault("evidence_ids", []).append(evidence_id)
                self.emit_event(EventType.HYPOTHESIS_CREATED, {
                    "hypothesis_id": hypothesis_id,
                    "statement": h.get("statement"),
                    "status": clean_status,
                    "evidence_id": evidence_id,
                })
                self.session_manager.save_task_state(self.task_state.to_dict())
                return True
        return False

    def add_decision(self, decision: str) -> None:
        """Record an architectural or implementation decision."""
        dec = decision.strip()
        if dec and dec not in self.cognitive_state.decisions:
            self.cognitive_state.decisions.append(dec)
            self.session_manager.save_task_state(self.task_state.to_dict())

    def set_objective(self, objective: str) -> None:
        """Update current micro-objective."""
        self.cognitive_state.current_objective = objective
        self.session_manager.save_task_state(self.task_state.to_dict())

    def action_allowed(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Core Tool Action Gating.
        
        Evaluates whether an action is permitted, safe, non-repetitive,
        relevant, and not premature according to the current cognitive state.
        """
        # 1. Repetitive / Loop check
        is_loop, loop_msg = self.loop_detector.check_loop(tool_name, arguments)
        if is_loop:
            return (False, f"Controller rejected duplicate action: {loop_msg}")

        # 2. Security & Workspace Containment check
        if tool_name in ("read_file", "write_file", "create_file", "edit_file", "delete_file"):
            target_path = arguments.get("file_path") or arguments.get("path")
            if target_path:
                try:
                    self.tool_registry.security_manager.resolve_and_validate_path(str(target_path))
                except Exception as exc:
                    return (False, f"Security restriction: {exc}")

        if tool_name == "run_command":
            cmd = arguments.get("command", "")
            if not cmd or not str(cmd).strip():
                return (False, "Command cannot be empty.")

        # 3. Investigation-First Debugging Gating
        is_mutating = tool_name in ("write_file", "edit_file", "delete_file")
        if is_mutating and self.cognitive_state.task_type in (TaskType.DEBUG, TaskType.INVESTIGATION):
            if self.investigation_steps_count == 0 and not self.cognitive_state.evidence:
                return (
                    False,
                    f"Investigation-First Rule: In a {self.cognitive_state.task_type.value} task, "
                    "you must first investigate (search_code, read_file, or run reproduction commands) "
                    "and formulate evidence/hypothesis before modifying files.",
                )

        # 4. Documentation Gating
        if self.cognitive_state.task_type == TaskType.DOCUMENTATION and tool_name in ("delete_file", "edit_file"):
            target_path = str(arguments.get("file_path") or arguments.get("path") or "").lower()
            allowed_doc_exts = (".md", ".txt", ".rst", ".adoc")
            if not any(target_path.endswith(ext) for ext in allowed_doc_exts) and "doc" not in target_path:
                return (
                    False,
                    "Documentation Gating: Documentation tasks should not mutate application source code. "
                    "Create or edit documentation markdown files instead.",
                )

        return (True, "")

    def validate_and_prepare_action(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Determine whether the proposed action is permitted, safe, and progressive.
        
        Returns: (allowed: bool, reason/error: str, action_guidance: Optional[str])
        """
        allowed, reason = self.action_allowed(tool_name, tool_args)
        if not allowed:
            self.emit_event(EventType.ACTION_BLOCKED, {
                "tool": tool_name,
                "arguments": tool_args,
                "reason": reason,
            })
            return (False, f"Controller rejected action: {reason}", f"Observation: {reason}")

        # Checkpoint creation for mutating actions
        if tool_name in ("write_file", "create_file", "edit_file", "delete_file"):
            fp = tool_args.get("file_path") or tool_args.get("path")
            if fp:
                chk = self.checkpoint_manager.create_checkpoint(
                    session_id=self.session_id,
                    description=f"Auto-checkpoint before {tool_name} on {fp}",
                    files=[str(fp)],
                )
                self.emit_event(EventType.CHECKPOINT_CREATED, {
                    "checkpoint_id": chk.checkpoint_id,
                    "target_file": str(fp),
                    "action": tool_name,
                })

        self.emit_event(EventType.ACTION_PROPOSED, {
            "tool": tool_name,
            "arguments": tool_args,
        })
        return (True, "", None)

    def execute_action(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        approval_handler: Optional[Callable] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> ToolResult:
        """Execute action via tool registry with approval and cancellation guards."""
        self.emit_event(EventType.TOOL_STARTED, {"name": tool_name, "arguments": tool_args})
        res: ToolResult = self.tool_registry.execute(
            name=tool_name,
            args=tool_args,
            approval_callback=approval_handler,
            cancel_check=cancel_check,
            session_id=self.session_id,
        )
        return res

    def record_and_evaluate_action(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool_result: ToolResult,
    ) -> ProgressReport:
        """Record executed action, update CognitiveState and TaskState, and evaluate progress."""
        out_str = tool_result.to_string()
        self.loop_detector.record_action(
            tool_name=tool_name,
            args=tool_args,
            success=tool_result.success,
            output_summary=out_str,
        )

        # Track cognitive execution history
        act_summary = f"{tool_name}({json.dumps(tool_args, default=str)[:80]})"
        self.cognitive_state.actions_taken.append(act_summary)
        self.cognitive_state.last_tool = tool_name

        if tool_result.success:
            self.cognitive_state.successful_actions.append(tool_name)
        else:
            self.cognitive_state.failed_actions.append(tool_name)
            self.cognitive_state.last_error = tool_result.error or out_str[:200]

        # Update file sets in TaskState & track investigations
        fp = tool_args.get("file_path") or tool_args.get("path")
        if tool_name == "read_file":
            self.investigation_steps_count += 1
            self.files_read_count += 1
            if fp:
                s_fp = str(fp)
                self.inspected_files.add(s_fp)
                self.files_read.add(s_fp)
                self.add_observation(f"Read file content: {s_fp}")
        elif tool_name == "search_code":
            self.investigation_steps_count += 1
            self.files_read_count += 1
            q = tool_args.get("query", "")
            self.add_observation(f"Searched codebase for: {q}")
        elif tool_name == "list_dir":
            self.investigation_steps_count += 1
            if fp:
                self.add_observation(f"Listed directory structure: {fp}")
        elif tool_result.success and fp:
            s_fp = str(fp)
            if tool_name in ("write_file", "edit_file"):
                self.task_state.files_modified.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "modified")
                self.emit_event(EventType.FILE_CHANGED, {"file_path": s_fp, "action": "modified"})
                self.add_observation(f"Modified file: {s_fp}")
            elif tool_name == "create_file":
                self.task_state.files_created.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "created")
                self.emit_event(EventType.FILE_CHANGED, {"file_path": s_fp, "action": "created"})
                self.add_observation(f"Created file: {s_fp}")
            elif tool_name == "delete_file":
                self.task_state.files_deleted.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "deleted")
                self.emit_event(EventType.FILE_CHANGED, {"file_path": s_fp, "action": "deleted"})
                self.add_observation(f"Deleted file: {s_fp}")

        if tool_name == "search_code":
            self.investigation_steps_count += 1
            query = tool_args.get("query", "")
            self.add_observation(f"Searched codebase for: '{query}'")

        if tool_name == "run_command":
            cmd = str(tool_args.get("command", ""))
            self.task_state.commands_executed.append(cmd)
            self.add_observation(f"Executed command: {cmd} (Exit {tool_result.exit_code})")
            if any(k in cmd.lower() for k in ["pytest", "test", "npm test"]):
                self.investigation_steps_count += 1

        self.emit_event(EventType.TOOL_COMPLETED, {
            "name": tool_name,
            "success": tool_result.success,
            "output": out_str[:1000],
            "duration_ms": tool_result.duration_ms,
        })

        # Evaluate progress
        report = self.progress_tracker.record_step(
            tool_name=tool_name,
            args=tool_args,
            success=tool_result.success,
            output=out_str,
            plan=self.task_state.plan,
        )

        # Update cognitive progress score
        self.cognitive_state.progress = self.task_state.plan.progress_percentage()

        # If stagnation detected, trigger replanner & diagnosis
        if report.recommended_action == ProgressAction.REPLAN:
            self.set_phase(ControllerPhase.DIAGNOSE, {"stagnation_reason": report.reason})
            self.emit_event(EventType.DIAGNOSIS_CREATED, {"diagnosis": report.reason})
            self.set_phase(ControllerPhase.REPLAN, {"reason": report.reason})
            self.emit_event(EventType.REPLAN_STARTED, {"reason": report.reason})
            self.planner.replan(
                current_plan=self.task_state.plan,
                failure_reason=report.reason,
                error_details=out_str,
            )

        self.task_state.updated_at = time.time()
        self.session_manager.save_task_state(self.task_state.to_dict())
        return report

    def verify(self) -> Tuple[VerificationResult, ProgressReport]:
        """Perform mandatory independent verification across touched files."""
        all_changed = list(self.task_state.files_modified | self.task_state.files_created)
        self.set_phase(ControllerPhase.VERIFY, {"files": all_changed})
        self.emit_event(EventType.VERIFICATION_STARTED, {"files": all_changed})

        vres = self.verifier.verify(all_changed, goal=self.goal)
        self.session_manager.add_verification(
            session_id=self.session_id,
            passed=vres.passed,
            summary=vres.summary,
            details=vres.details,
            phase=vres.phase,
        )

        prep = self.progress_tracker.record_verification(vres.passed, vres.details)

        if vres.passed:
            self.task_state.plan.complete_current_step("Verification passed successfully.")
            self.set_phase(ControllerPhase.DONE, {"summary": vres.summary})
            self.emit_event(EventType.VERIFICATION_PASSED, {
                "summary": vres.summary,
                "details": vres.details,
            })
            self.emit_event(EventType.TASK_COMPLETED, {"summary": vres.summary})
        else:
            self.set_phase(ControllerPhase.DIAGNOSE, {"details": vres.details})
            self.emit_event(EventType.VERIFICATION_FAILED, {
                "summary": vres.summary,
                "details": vres.details,
                "category": vres.error_category.value if vres.error_category else None,
            })
            self.emit_event(EventType.DIAGNOSIS_CREATED, {
                "diagnosis": f"Verification failed: {vres.details[:300]}",
                "phase": vres.phase,
            })

            # Check if rollback is recommended due to repeated failures
            if prep.recommended_action == ProgressAction.ROLLBACK:
                self.set_phase(ControllerPhase.RECOVER, {"reason": "Rollback to clean checkpoint"})
                self.rollback()

            self.set_phase(ControllerPhase.REPLAN, {"reason": "Verification failed"})
            self.emit_event(EventType.REPLAN_STARTED, {"reason": "Verification failed"})
            self.planner.replan(
                current_plan=self.task_state.plan,
                failure_reason="Verification failed",
                error_details=vres.details,
            )

        self.task_state.updated_at = time.time()
        self.session_manager.save_task_state(self.task_state.to_dict())
        return vres, prep

    def rollback(self, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
        """Revert changes safely to a known good checkpoint."""
        res = self.checkpoint_manager.rollback(checkpoint_id)
        if res.get("success"):
            self.emit_event("rollback_completed", res)
        return res

    def check_completion(self, llm_content: str, files_changed: List[str]) -> Tuple[bool, str]:
        """Evaluate whether the task can genuinely be concluded, rejecting premature completion."""
        tt = self.cognitive_state.task_type

        if tt == TaskType.CONVERSATION:
            return (True, "Conversational turn completed.")

        if tt == TaskType.DOCUMENTATION:
            goal_lower = self.goal.lower()
            wants_code_summary = any(
                kw in goal_lower
                for kw in ["code", "script", "logic", "how it works", "architecture", "what does", "summarize", "explain", "overview"]
            )
            # If user wanted code summary / architecture, reading actual files is mandatory!
            if wants_code_summary and self.files_read_count == 0:
                return (
                    False,
                    "You have only explored the directory structure, but have not inspected any actual code files yet. "
                    "Use `read_file` to read the key source files (e.g. main entry points, core modules, or README.md) "
                    "so you can explain what the code actually does rather than just listing file names."
                )

            # Check if output is merely a list of file paths/bullets without actual code explanation
            is_mere_file_listing = (
                ("The current directory contains" in llm_content or "# Folder Contents" in llm_content or "contains the following files" in llm_content)
                and not any(term in llm_content.lower() for term in ["architecture", "pipeline", "component", "function", "handles", "implements", "logic", "module", "entry point", "purpose", "responsibilit"])
            )
            if is_mere_file_listing:
                return (
                    False,
                    "You provided a listing of file names instead of summarizing what the code does. "
                    "Use `read_file` to read the primary code files and provide a meaningful summary of the code's functionality, purpose, and architecture."
                )

            if self.files_read_count >= 1 or (self.investigation_steps_count >= 1 and len(llm_content.split()) >= 40):
                return (True, "Documentation synthesized from workspace.")
            return (False, "Explore the repository files (e.g. read_file on README or config files) before generating documentation.")

        if tt in (TaskType.DEBUG, TaskType.IMPLEMENTATION, TaskType.REFACTOR):
            # If files were modified, independent verification must be completed!
            if files_changed:
                if self.cognitive_state.phase != ControllerPhase.DONE:
                    return (False, "Code modifications have been made but independent verification has not passed yet. Proceed to verify.")
                return (True, "Changes verified successfully.")

            # No files modified yet
            if self.investigation_steps_count == 0:
                return (False, f"Task '{self.goal}' requires taking action. Inspect relevant files or run tests using tools.")

            if tt == TaskType.DEBUG:
                return (False, "Subsystem investigated but fix has not been implemented yet. Apply the necessary code modification.")

        if tt == TaskType.INVESTIGATION:
            if self.investigation_steps_count >= 1:
                return (True, "Investigation findings established.")
            return (False, "Investigate relevant components before concluding.")

        return (True, "Task finished.")

    def build_turn_prompt(self, iteration: int) -> str:
        """Construct a structured, low-overhead cognitive prompt for local models and cloud LLMs."""
        facts_str = "\n".join(f"- {f}" for f in self.cognitive_state.known_facts[-5:]) or "- (None yet)"
        unknowns_str = "\n".join(f"- {u}" for u in self.cognitive_state.unknowns[-3:]) or "- (None)"
        hyp_str = "\n".join(
            f"- [{h.get('status', 'UNTESTED')}] {h.get('statement')}"
            for h in self.cognitive_state.hypotheses[-3:]
        ) or "- (None formulated yet)"
        obs_str = "\n".join(f"- {o}" for o in self.cognitive_state.observations[-3:]) or "- (None yet)"

        all_changed = list(self.task_state.files_modified | self.task_state.files_created)
        changed_str = ", ".join(all_changed) if all_changed else "None"

        if self.cognitive_state.task_type == TaskType.DOCUMENTATION and self.files_read_count == 0:
            phase_guidance = (
                "CURRENT PHASE: INVESTIGATE / DOCUMENTATION. To summarize or explain code, you MUST use `read_file` "
                "on the key source files (e.g. README.md, main entry points, or core modules). "
                "Do NOT simply output a list of file names — inspect the code and explain its functionality."
            )
        else:
            phase_guidance = {
                ControllerPhase.INVESTIGATE: (
                    "CURRENT PHASE: INVESTIGATE. Use `search_code`, `read_file`, or run reproduction commands. "
                    "Do NOT edit code yet. Trace execution, locate the fault, and identify the root cause."
                ),
                ControllerPhase.DIAGNOSE: (
                    "CURRENT PHASE: DIAGNOSE. Analyze previous errors or blockers. Formulate a clear hypothesis on why the failure occurred."
                ),
                ControllerPhase.PLAN: (
                    "CURRENT PHASE: PLAN. Review known facts and choose the most targeted file or command to advance."
                ),
                ControllerPhase.EXECUTE: (
                    "CURRENT PHASE: EXECUTE. Apply surgical edits (`edit_file`, `write_file`) to resolve the root cause."
                ),
                ControllerPhase.VERIFY: (
                    "CURRENT PHASE: VERIFY. Verify all modifications with syntax checks or test suites."
                ),
                ControllerPhase.REPLAN: (
                    "CURRENT PHASE: REPLAN. The previous strategy stalled or failed. Choose an alternative approach."
                ),
            }.get(
                self.cognitive_state.phase,
                f"CURRENT PHASE: {self.cognitive_state.phase.value}. Take the next most purposeful action."
            )

        prompt = (
            f"[ASTRA V5 COGNITIVE STATE]\n"
            f"Goal: {self.cognitive_state.goal}\n"
            f"Task Type: {self.cognitive_state.task_type.value}\n"
            f"Phase: {self.cognitive_state.phase.value}\n"
            f"Current Objective: {self.cognitive_state.current_objective}\n\n"
            f"Known Facts:\n{facts_str}\n\n"
            f"Active Hypotheses:\n{hyp_str}\n\n"
            f"Recent Observations:\n{obs_str}\n\n"
            f"Files Changed: {changed_str}\n\n"
            f"Directive: {phase_guidance}\n"
            f"Do NOT instruct the user to execute tools or commands. Invoke the required tool yourself."
        )
        return prompt
