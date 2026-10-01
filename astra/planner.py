"""ASTRA V5 Dynamic Planner and Replanning Engine.

Generates initial structured plans from user objectives and repository context,
and dynamically revises execution paths when blockers, test failures, or stagnation occur.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from astra.state import StepStatus, TaskPlan, TaskState, TaskStep


class Planner:
    """Creates initial plans and dynamically recalculates steps during failures."""

    def __init__(self):
        pass

    @staticmethod
    def create_initial_plan(goal: str, project_type: str = "generic") -> TaskPlan:
        """Construct a structured, measurable plan for an autonomous task."""
        plan = TaskPlan(goal=goal)
        goal_lower = goal.lower()

        # Check if the goal is architectural, explanatory, or documentation-oriented
        is_info_or_doc = any(kw in goal_lower for kw in [
            "architecture", "documentation", "document", "explain", "overview",
            "what is", "how does", "summarize", "walkthrough", "read and analyze",
            "diagram", "components", "structure", "audit", "review"
        ]) and not any(kw in goal_lower for kw in ["fix", "bug", "failing test", "implement", "refactor", "add feature"])

        if is_info_or_doc:
            plan.add_step(
                title="Explore Repository Architecture",
                description=f"Scan directories, read configuration manifests, README, and core entry points for {project_type} project.",
            )
            plan.add_step(
                title="Analyze Components & Design Patterns",
                description="Map module responsibilities, data flow, API endpoints, and dependencies.",
            )
            plan.add_step(
                title="Deliver Comprehensive Documentation",
                description="Synthesize and provide deep, professional architecture documentation answering the user request.",
            )
        else:
            # Code modification / implementation / bug fix workflow
            plan.add_step(
                title="Explore & Discover Context",
                description=f"Scan project structure, locate relevant files, and analyze error or feature requirements for {project_type} project.",
            )
            plan.add_step(
                title="Implement Solution",
                description=f"Apply clean surgical code modifications or create files required for: {goal}.",
            )
            plan.add_step(
                title="Verify & Conclude",
                description="Verify syntax and run tests if applicable to ensure regression-free completion.",
            )
        
        # Activate Step 1
        if plan.steps:
            plan.steps[0].status = StepStatus.IN_PROGRESS
            plan.steps[0].started_at = time.time()
            
        return plan

    @staticmethod
    def replan(
        current_plan: TaskPlan,
        failure_reason: str,
        error_details: str = "",
    ) -> TaskPlan:
        """Inject an adaptive recovery step into the plan when execution encounters blockers."""
        curr_step = current_plan.get_current_step()
        if curr_step:
            curr_step.status = StepStatus.FAILED
            curr_step.result_summary = f"Blocked: {failure_reason}"
            curr_step.completed_at = time.time()

        # Construct specific recovery step
        short_reason = (failure_reason or "Verification failed")[:60]
        step_id = len(current_plan.steps) + 1
        recovery_step = TaskStep(
            step_id=step_id,
            title=f"Resolve Blocker: {short_reason}",
            description=f"Diagnose and remediate root cause:\n{error_details[:300] if error_details else failure_reason}",
            status=StepStatus.IN_PROGRESS,
            started_at=time.time(),
        )
        
        # Insert recovery step before the final verification step if possible
        if len(current_plan.steps) >= 3 and current_plan.steps[-1].title.startswith("Verify"):
            current_plan.steps.insert(-1, recovery_step)
            # Reindex steps
            for idx, s in enumerate(current_plan.steps):
                s.step_id = idx + 1
            # Move index to recovery step
            current_plan.current_step_index = len(current_plan.steps) - 2
        else:
            current_plan.steps.append(recovery_step)
            current_plan.current_step_index = len(current_plan.steps) - 1

        return current_plan
