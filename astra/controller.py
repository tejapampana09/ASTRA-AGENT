"""ASTRA V5 Deterministic Agent Controller.

Central runtime controller that enforces state transitions, loop breaking,
progress verification, checkpointing, and dynamic replanning independently
of the LLM model weights.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from astra.approval import ApprovalManager, approval_manager as global_approval_manager
from astra.checkpoints import CheckpointManager
from astra.events import AgentEvent, AgentState, EventType, event_bus
from astra.planner import Planner
from astra.progress import ProgressAction, ProgressReport, ProgressTracker
from astra.session import SessionManager, session_manager as global_session_manager
from astra.state import ActionRecord, StagnationAndLoopDetector, StepStatus, TaskPlan, TaskState, TaskStep
from astra.tools import ToolExecutor, ToolRegistry, ToolResult
from astra.verifier import IndependentVerifier, VerificationResult


class DeterministicAgentController:
    """The authoritative execution governor for ASTRA tasks.
    
    Decouples deterministic lifecycle, security, progress, and safety
    from the probabilistic LLM completions.
    """

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
    ):
        self.workspace_path = workspace_path.resolve()
        self.session_id = session_id
        self.goal = goal
        self.model_name = model_name
        self.max_iterations = max_iterations

        self.session_manager = session_manager or global_session_manager
        self.approval_manager = approval_manager or global_approval_manager
        self.tool_registry = tool_registry or ToolRegistry(self.workspace_path)
        self.checkpoint_manager = CheckpointManager(self.workspace_path, self.session_manager)
        self.verifier = IndependentVerifier(self.workspace_path)
        self.loop_detector = StagnationAndLoopDetector()
        self.progress_tracker = ProgressTracker(self.workspace_path)
        self.planner = Planner()

        # Initialize or restore TaskState
        existing = self.session_manager.get_task_state(self.session_id)
        if existing:
            self.task_state = TaskState.from_dict(existing)
        else:
            initial_plan = self.planner.create_initial_plan(self.goal)
            self.task_state = TaskState(
                session_id=self.session_id,
                goal=self.goal,
                workspace_path=str(self.workspace_path),
                model_name=self.model_name,
                state=AgentState.IDLE,
                plan=initial_plan,
            )
            self.session_manager.save_task_state(self.task_state.to_dict())

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

    def set_state(self, new_state: AgentState, details: Optional[Dict[str, Any]] = None) -> None:
        self.task_state.state = new_state
        self.task_state.updated_at = time.time()
        self.emit_event(EventType.STATE_CHANGED, {
            "state": new_state.value,
            **(details or {}),
        })
        self.session_manager.save_task_state(self.task_state.to_dict())

    def validate_and_prepare_action(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Tuple[bool, str, Optional[str]]:
        """Determine whether the proposed action is permitted, safe, and progressive.
        
        Returns: (allowed: bool, reason/error: str, action_guidance: Optional[str])
        """
        # 1. Loop and Stagnation check
        is_loop, loop_msg = self.loop_detector.check_loop(tool_name, tool_args)
        if is_loop:
            # Action is stagnant duplicate
            return (
                False,
                f"Controller rejected duplicate action: {loop_msg}",
                "Observation: Operation has already completed with identical parameters. Proceed to verification or next plan step.",
            )

        # 2. Checkpoint creation for mutating actions
        if tool_name in ("write_file", "create_file", "edit_file", "delete_file"):
            fp = tool_args.get("file_path") or tool_args.get("path")
            if fp:
                chk = self.checkpoint_manager.create_checkpoint(
                    session_id=self.session_id,
                    description=f"Auto-checkpoint before {tool_name} on {fp}",
                    files=[str(fp)],
                )
                self.emit_event("checkpoint_created", {
                    "checkpoint_id": chk.checkpoint_id,
                    "target_file": str(fp),
                    "action": tool_name,
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
        """Record executed action, update TaskState, and evaluate progress."""
        out_str = tool_result.to_string()
        self.loop_detector.record_action(
            tool_name=tool_name,
            args=tool_args,
            success=tool_result.success,
            output_summary=out_str,
        )

        # Update file sets in TaskState
        fp = tool_args.get("file_path") or tool_args.get("path")
        if fp and tool_result.success:
            s_fp = str(fp)
            if tool_name in ("write_file", "edit_file"):
                self.task_state.files_modified.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "modified")
            elif tool_name == "create_file":
                self.task_state.files_created.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "created")
            elif tool_name == "delete_file":
                self.task_state.files_deleted.add(s_fp)
                self.session_manager.add_file_change(self.session_id, s_fp, "deleted")

        if tool_name == "run_command" and "command" in tool_args:
            self.task_state.commands_executed.append(str(tool_args["command"]))

        # Progress tracking evaluation
        report = self.progress_tracker.record_step(
            tool_name=tool_name,
            args=tool_args,
            success=tool_result.success,
            output=out_str,
            plan=self.task_state.plan,
        )

        # If stagnation detected, trigger replanner
        if report.recommended_action == ProgressAction.REPLAN:
            self.planner.replan(
                current_plan=self.task_state.plan,
                failure_reason=report.reason,
                error_details=out_str,
            )
            self.emit_event("plan_updated", {
                "reason": report.reason,
                "plan": self.task_state.plan.to_dict(),
            })

        self.task_state.updated_at = time.time()
        self.session_manager.save_task_state(self.task_state.to_dict())
        return report

    def verify(self) -> Tuple[VerificationResult, ProgressReport]:
        """Perform mandatory independent verification across touched files."""
        all_changed = list(self.task_state.files_modified | self.task_state.files_created)
        self.set_state(AgentState.VERIFYING, {"files": all_changed})
        self.emit_event(EventType.VERIFICATION_STARTED, {"files": all_changed})

        vres = self.verifier.verify(all_changed)
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
            self.emit_event(EventType.VERIFICATION_PASSED, {
                "summary": vres.summary,
                "details": vres.details,
            })
        else:
            self.emit_event(EventType.VERIFICATION_FAILED, {
                "summary": vres.summary,
                "details": vres.details,
                "recommended_action": prep.recommended_action.value,
            })
            if prep.recommended_action == ProgressAction.REPLAN:
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
