"""ASTRA V4 Task State, Deterministic Plan Engine, and Loop/Stagnation Detector.

Provides structured execution planning, step tracking, action deduplication,
and intelligent stagnation detection to prevent local models from infinite loops.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from astra.events import AgentState, ControllerPhase


class TaskType(str, Enum):
    DEBUG = "DEBUG"
    IMPLEMENTATION = "IMPLEMENTATION"
    INVESTIGATION = "INVESTIGATION"
    DOCUMENTATION = "DOCUMENTATION"
    REFACTOR = "REFACTOR"
    CONVERSATION = "CONVERSATION"


@dataclass
class Hypothesis:
    id: str
    statement: str
    status: str = "UNTESTED"  # UNTESTED, TESTING, LIKELY, CONFIRMED, REJECTED
    evidence_ids: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "status": self.status,
            "evidence_ids": list(self.evidence_ids),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Hypothesis:
        return cls(
            id=data.get("id", ""),
            statement=data.get("statement", ""),
            status=data.get("status", "UNTESTED"),
            evidence_ids=list(data.get("evidence_ids", [])),
            created_at=data.get("created_at", time.time()),
        )


@dataclass
class Evidence:
    id: str
    fact: str
    source: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fact": self.fact,
            "source": self.source,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Evidence:
        return cls(
            id=data.get("id", ""),
            fact=data.get("fact", ""),
            source=data.get("source", ""),
            timestamp=data.get("timestamp", time.time()),
        )


@dataclass
class CognitiveState:
    """Full persistent cognitive state for autonomous engineering agents."""
    goal: str = ""
    task_type: TaskType = TaskType.DEBUG
    constraints: List[str] = field(default_factory=list)
    known_facts: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    hypotheses: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    current_objective: str = ""
    next_action: Optional[str] = None
    blockers: List[str] = field(default_factory=list)
    progress: float = 0.0
    confidence: float = 0.5
    actions_taken: List[str] = field(default_factory=list)
    successful_actions: List[str] = field(default_factory=list)
    failed_actions: List[str] = field(default_factory=list)
    last_tool: Optional[str] = None
    last_error: Optional[str] = None
    phase: ControllerPhase = ControllerPhase.UNDERSTAND

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "task_type": self.task_type.value if isinstance(self.task_type, TaskType) else str(self.task_type),
            "constraints": list(self.constraints),
            "known_facts": list(self.known_facts),
            "unknowns": list(self.unknowns),
            "observations": list(self.observations),
            "hypotheses": list(self.hypotheses),
            "evidence": list(self.evidence),
            "decisions": list(self.decisions),
            "current_objective": self.current_objective,
            "next_action": self.next_action,
            "blockers": list(self.blockers),
            "progress": self.progress,
            "confidence": self.confidence,
            "actions_taken": list(self.actions_taken),
            "successful_actions": list(self.successful_actions),
            "failed_actions": list(self.failed_actions),
            "last_tool": self.last_tool,
            "last_error": self.last_error,
            "phase": self.phase.value if isinstance(self.phase, ControllerPhase) else str(self.phase),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CognitiveState:
        tt = data.get("task_type", TaskType.DEBUG.value)
        try:
            task_type = TaskType(tt)
        except Exception:
            task_type = TaskType.DEBUG

        ph = data.get("phase", ControllerPhase.UNDERSTAND.value)
        try:
            phase = ControllerPhase(ph)
        except Exception:
            phase = ControllerPhase.UNDERSTAND

        return cls(
            goal=data.get("goal", ""),
            task_type=task_type,
            constraints=list(data.get("constraints", [])),
            known_facts=list(data.get("known_facts", [])),
            unknowns=list(data.get("unknowns", [])),
            observations=list(data.get("observations", [])),
            hypotheses=list(data.get("hypotheses", [])),
            evidence=list(data.get("evidence", [])),
            decisions=list(data.get("decisions", [])),
            current_objective=data.get("current_objective", ""),
            next_action=data.get("next_action"),
            blockers=list(data.get("blockers", [])),
            progress=float(data.get("progress", 0.0)),
            confidence=float(data.get("confidence", 0.5)),
            actions_taken=list(data.get("actions_taken", [])),
            successful_actions=list(data.get("successful_actions", [])),
            failed_actions=list(data.get("failed_actions", [])),
            last_tool=data.get("last_tool"),
            last_error=data.get("last_error"),
            phase=phase,
        )


class StepStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskStep:
    step_id: int
    title: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result_summary: str = ""
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "result_summary": self.result_summary,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskStep:
        return cls(
            step_id=data.get("step_id", 1),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=StepStatus(data.get("status", StepStatus.PENDING.value)),
            result_summary=data.get("result_summary", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
        )


@dataclass
class TaskPlan:
    goal: str
    steps: List[TaskStep] = field(default_factory=list)
    current_step_index: int = 0

    def add_step(self, title: str, description: str = "") -> TaskStep:
        step_id = len(self.steps) + 1
        step = TaskStep(step_id=step_id, title=title, description=description)
        self.steps.append(step)
        return step

    def get_current_step(self) -> Optional[TaskStep]:
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None

    def advance_to_next(self) -> Optional[TaskStep]:
        self.current_step_index += 1
        curr = self.get_current_step()
        if curr and curr.status == StepStatus.PENDING:
            curr.status = StepStatus.IN_PROGRESS
            curr.started_at = time.time()
        return curr

    def complete_current_step(self, summary: str = "") -> None:
        curr = self.get_current_step()
        if curr:
            curr.status = StepStatus.COMPLETED
            curr.result_summary = summary
            curr.completed_at = time.time()
            self.advance_to_next()

    def fail_current_step(self, error: str = "") -> None:
        curr = self.get_current_step()
        if curr:
            curr.status = StepStatus.FAILED
            curr.result_summary = f"Failed: {error}"
            curr.completed_at = time.time()

    def progress_percentage(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return round((completed / len(self.steps)) * 100.0, 1)

    def is_all_completed(self) -> bool:
        if not self.steps:
            return False
        return all(s.status == StepStatus.COMPLETED for s in self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_index": self.current_step_index,
            "progress_percentage": self.progress_percentage(),
            "is_all_completed": self.is_all_completed(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskPlan:
        steps = [TaskStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            goal=data.get("goal", ""),
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
        )


@dataclass
class ActionRecord:
    tool_name: str
    args_hash: str
    normalized_args: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    output_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "args_hash": self.args_hash,
            "normalized_args": self.normalized_args,
            "timestamp": self.timestamp,
            "success": self.success,
            "output_summary": self.output_summary,
        }


class StagnationAndLoopDetector:
    """Detects repetitive actions, duplicate commands, and stagnating execution loops."""

    def __init__(self, max_consecutive_duplicates: int = 2, max_identical_errors: int = 3):
        self.max_consecutive_duplicates = max_consecutive_duplicates
        self.max_identical_errors = max_identical_errors
        self.action_history: List[ActionRecord] = []
        self.error_counts: Dict[str, int] = {}

    @staticmethod
    def hash_action(tool_name: str, args: Dict[str, Any]) -> str:
        # Normalize args for stable hashing
        clean_args = {k: v for k, v in args.items() if k not in ("timestamp", "id", "_")}
        serialized = json.dumps({"tool": tool_name, "args": clean_args}, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]

    def record_action(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool = True,
        output_summary: str = "",
    ) -> ActionRecord:
        ahash = self.hash_action(tool_name, args)
        record = ActionRecord(
            tool_name=tool_name,
            args_hash=ahash,
            normalized_args=args,
            success=success,
            output_summary=output_summary[:200],
        )
        self.action_history.append(record)
        return record

    def check_loop(self, tool_name: str, args: Dict[str, Any]) -> tuple[bool, str]:
        """Check if proposed action is repeating a stagnant loop."""
        ahash = self.hash_action(tool_name, args)

        # Count consecutive identical calls
        consecutive = 0
        for rec in reversed(self.action_history):
            if rec.args_hash == ahash:
                consecutive += 1
            else:
                break

        if consecutive >= self.max_consecutive_duplicates:
            return (
                True,
                f"Loop detected: Tool '{tool_name}' was called {consecutive} times consecutively with identical arguments. "
                "The requested operation has already succeeded or produced the same result.",
            )

        return (False, "")

    def check_error_loop(self, error_text: str) -> tuple[bool, str]:
        if not error_text or not error_text.strip():
            return (False, "")
        norm = " ".join(error_text.strip().split())[:120]
        cnt = self.error_counts.get(norm, 0) + 1
        self.error_counts[norm] = cnt
        if cnt >= self.max_identical_errors:
            return (
                True,
                f"Stagnation detected: Identical failure occurred {cnt} times: '{norm}'.",
            )
        return (False, "")


@dataclass
class TaskState:
    """Full deterministic state of an autonomous task."""
    session_id: str
    goal: str
    workspace_path: str
    model_name: str
    state: AgentState = AgentState.IDLE
    plan: TaskPlan = field(default_factory=lambda: TaskPlan(goal=""))
    cognitive_state: CognitiveState = field(default_factory=CognitiveState)
    files_modified: Set[str] = field(default_factory=set)
    files_created: Set[str] = field(default_factory=set)
    files_deleted: Set[str] = field(default_factory=set)
    commands_executed: List[str] = field(default_factory=list)
    action_records: List[ActionRecord] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.cognitive_state.goal and self.goal:
            self.cognitive_state.goal = self.goal

    @property
    def cognitive(self) -> CognitiveState:
        return self.cognitive_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "goal": self.goal,
            "workspace_path": self.workspace_path,
            "model_name": self.model_name,
            "state": self.state.value if isinstance(self.state, AgentState) else self.state,
            "plan": self.plan.to_dict(),
            "cognitive_state": self.cognitive_state.to_dict(),
            "files_modified": list(self.files_modified),
            "files_created": list(self.files_created),
            "files_deleted": list(self.files_deleted),
            "commands_executed": self.commands_executed,
            "action_records": [a.to_dict() for a in self.action_records],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskState:
        cog_data = data.get("cognitive_state")
        if cog_data:
            cog_state = CognitiveState.from_dict(cog_data)
        else:
            cog_state = CognitiveState(goal=data.get("goal", ""))

        state = cls(
            session_id=data.get("session_id", ""),
            goal=data.get("goal", ""),
            workspace_path=data.get("workspace_path", ""),
            model_name=data.get("model_name", ""),
            state=AgentState(data.get("state", AgentState.IDLE.value)),
            plan=TaskPlan.from_dict(data.get("plan", {"goal": data.get("goal", "")})),
            cognitive_state=cog_state,
            files_modified=set(data.get("files_modified", [])),
            files_created=set(data.get("files_created", [])),
            files_deleted=set(data.get("files_deleted", [])),
            commands_executed=data.get("commands_executed", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
        return state
