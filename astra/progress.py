"""ASTRA V5 Progress Tracking Engine.

Monitors real workspace progress, error transitions, test evolution,
and plan execution to differentiate genuine progress from unproductive loops.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from astra.state import StepStatus, TaskPlan, TaskState


class ProgressAction(str, Enum):
    CONTINUE = "CONTINUE"
    REPLAN = "REPLAN"
    VERIFY = "VERIFY"
    ROLLBACK = "ROLLBACK"
    ABORT = "ABORT"


@dataclass
class ProgressReport:
    is_progressing: bool
    stagnation_score: int
    reason: str
    recommended_action: ProgressAction
    details: Dict[str, Any] = field(default_factory=dict)


class ProgressTracker:
    """Calculates whether execution is actually advancing the project towards completion."""

    def __init__(self, workspace_path: Optional[Path] = None, max_stagnant_steps: int = 3):
        self.workspace_path = workspace_path
        self.max_stagnant_steps = max_stagnant_steps
        self.stagnation_score = 0
        self.history: List[Dict[str, Any]] = []
        self.seen_errors: Dict[str, int] = {}
        self.files_touched: Set[str] = set()
        self.last_verification_error: Optional[str] = None
        self.last_plan_percentage: float = 0.0

    @staticmethod
    def _normalize_error(err: str) -> str:
        if not err:
            return ""
        # Collapse whitespace and take first 200 chars for matching
        return " ".join(err.strip().split())[:200]

    def record_step(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool,
        output: str,
        plan: Optional[TaskPlan] = None,
    ) -> ProgressReport:
        """Evaluate whether a tool invocation made demonstrable progress."""
        now = time.time()
        is_mutating = tool_name in ("write_file", "create_file", "edit_file", "delete_file")
        is_command = tool_name == "run_command"
        is_reading = tool_name in ("read_file", "list_dir", "search_code", "web_search", "git_status", "git_diff")

        file_path = args.get("file_path") or args.get("path")
        if file_path:
            self.files_touched.add(str(file_path))

        step_record = {
            "timestamp": now,
            "tool": tool_name,
            "args": args,
            "success": success,
            "output_len": len(output),
            "is_mutating": is_mutating,
        }
        self.history.append(step_record)

        current_percentage = plan.progress_percentage() if plan else 0.0
        plan_advanced = current_percentage > self.last_plan_percentage
        if plan_advanced:
            self.last_plan_percentage = current_percentage
            self.stagnation_score = max(0, self.stagnation_score - 1)
            return ProgressReport(
                is_progressing=True,
                stagnation_score=self.stagnation_score,
                reason=f"Plan advanced to {current_percentage}%.",
                recommended_action=ProgressAction.CONTINUE,
                details={"plan_percentage": current_percentage},
            )

        # Check for repeated read operations without actions
        if len(self.history) >= 4:
            recent_tools = [h["tool"] for h in self.history[-4:]]
            if all(t in ("read_file", "search_code", "list_dir") for t in recent_tools):
                # 4 consecutive reads on potentially same items
                self.stagnation_score += 1
                if self.stagnation_score >= self.max_stagnant_steps:
                    return ProgressReport(
                        is_progressing=False,
                        stagnation_score=self.stagnation_score,
                        reason="Agent has performed 4 consecutive exploratory read calls without writing or executing code.",
                        recommended_action=ProgressAction.REPLAN,
                        details={"recent_tools": recent_tools},
                    )

        # Check for failed command loops
        if is_command and not success:
            norm_err = self._normalize_error(output)
            count = self.seen_errors.get(norm_err, 0) + 1
            self.seen_errors[norm_err] = count
            if count >= 2:
                self.stagnation_score += 2
                return ProgressReport(
                    is_progressing=False,
                    stagnation_score=self.stagnation_score,
                    reason=f"Identical command error repeated {count} times.",
                    recommended_action=ProgressAction.REPLAN,
                    details={"error": norm_err, "count": count},
                )

        # If a mutation occurred successfully, genuine progress was made
        if is_mutating and success:
            self.stagnation_score = 0
            return ProgressReport(
                is_progressing=True,
                stagnation_score=0,
                reason=f"File mutation succeeded: {tool_name} on {file_path}",
                recommended_action=ProgressAction.CONTINUE,
                details={"file": file_path},
            )

        # Otherwise healthy continuation
        return ProgressReport(
            is_progressing=True,
            stagnation_score=self.stagnation_score,
            reason="Step executed normally.",
            recommended_action=ProgressAction.CONTINUE,
        )

    def record_verification(self, passed: bool, details: str) -> ProgressReport:
        """Assess progress from independent verification outcomes."""
        if passed:
            self.stagnation_score = 0
            self.last_verification_error = None
            return ProgressReport(
                is_progressing=True,
                stagnation_score=0,
                reason="Verification PASSED. All tests and checks succeeded.",
                recommended_action=ProgressAction.CONTINUE,
            )

        norm_err = self._normalize_error(details)
        if self.last_verification_error == norm_err:
            self.stagnation_score += 2
            return ProgressReport(
                is_progressing=False,
                stagnation_score=self.stagnation_score,
                reason=f"Verification failed with unchanged blocker: {norm_err[:120]}",
                recommended_action=ProgressAction.REPLAN if self.stagnation_score < 4 else ProgressAction.ROLLBACK,
                details={"repeated_error": norm_err},
            )
        else:
            # Different error means fixing is actively changing code behavior (learning/adapting)
            self.last_verification_error = norm_err
            self.stagnation_score = max(0, self.stagnation_score - 1)
            return ProgressReport(
                is_progressing=True,
                stagnation_score=self.stagnation_score,
                reason="Verification failure changed; error state is evolving.",
                recommended_action=ProgressAction.CONTINUE,
                details={"new_error": norm_err},
            )

    def reset(self) -> None:
        self.stagnation_score = 0
        self.history.clear()
        self.seen_errors.clear()
        self.files_touched.clear()
        self.last_verification_error = None
        self.last_plan_percentage = 0.0
