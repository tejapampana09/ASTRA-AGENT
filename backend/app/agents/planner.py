from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.state import AstraAgentState
from app.analysis.impact import ChangeImpactAnalyzer, ImpactAnalysisReport
from app.memory.engineering import get_engineering_memory_store
from app.observability.logging import logger


def plan_task(state: AstraAgentState) -> Dict[str, Any]:
    """
    INTELLIGENT PLANNER (Phase 3):
    Generates a structured, repository-aware execution plan with:
    1. Task Decomposition into dependency-ordered stages.
    2. Change Impact Analysis (affected files, symbols, downstream dependents).
    3. Long-term Engineering Decisions and Architectural Rules.
    4. Risk Estimation & Blast Radius Analysis.
    5. Implementation Strategy, Verification Strategy, and Rollback Strategy.
    """
    goal = state.get("user_goal", "")
    task_id = state.get("task_id", "")
    repo_id = state.get("repository_id") or "default_repo"
    context = state.get("repository_context", {})
    summary = context.get("summary", {})
    files = context.get("files", [])
    symbols = context.get("symbols", [])
    test_cmd = summary.get("test_command") or context.get("test_command") or "pytest"
    backend = summary.get("backend") or "Application"
    workspace_path_str = state.get("workspace_path")

    logger.info(f"[{task_id}] Intelligent Planner formulating plan for: {goal}")

    # 1. Identify primary candidate files based on goal keywords, flow chain, and past memories
    target_files: List[str] = []
    goal_words = set(w for w in goal.lower().split() if len(w) > 3)
    flow_chain = context.get("flow_chain")
    past_memories = context.get("past_memories", [])

    for f in files:
        f_lower = f.lower()
        if any(w in f_lower for w in goal_words):
            target_files.append(f)

    # Add candidate files from architectural call chain if available
    if flow_chain and isinstance(flow_chain, dict):
        chain_files = flow_chain.get("files", [])
        for cf in chain_files:
            if cf not in target_files and cf in files:
                target_files.append(cf)

    # Add files from past episodic memory
    for mem in past_memories:
        for mf in mem.get("files_modified", []):
            if mf not in target_files and mf in files:
                target_files.append(mf)

    if not target_files and files:
        target_files = files[:3]

    # 2. Perform Change Impact Analysis
    impact_report: Optional[ImpactAnalysisReport] = None
    if workspace_path_str:
        ws_p = Path(workspace_path_str)
        if ws_p.exists():
            analyzer = ChangeImpactAnalyzer(ws_p)
            impact_report = analyzer.analyze_impact(target_files=target_files[:4], all_repo_files=files)

    # 3. Retrieve long-term engineering decisions and rules
    eng_store = get_engineering_memory_store()
    relevant_decisions = eng_store.find_relevant_decisions(
        repo_id=repo_id,
        target_files=target_files,
        goal=goal,
        top_k=3
    )

    # 4. Multi-Stage Task Decomposition with Dependency Ordering
    plan_steps: List[Dict[str, Any]] = []

    # Stage 1: Inspection & Impact Assessment
    affected_files_preview = impact_report.affected_files[:3] if impact_report else []
    relevant_tests = impact_report.relevant_tests if impact_report else []
    plan_steps.append({
        "step": 1,
        "stage": "inspection",
        "description": (
            f"Inspect target modules ({', '.join(target_files[:3])}) and review architectural conventions for {backend}. "
            f"Impact blast radius: {len(affected_files_preview)} downstream dependents."
            + (f" Flow: {flow_chain['summary']}" if flow_chain and isinstance(flow_chain, dict) and flow_chain.get("summary") else "")
        ),
        "status": "pending",
        "targets": target_files[:3],
        "flow_chain": flow_chain.get("summary") if flow_chain and isinstance(flow_chain, dict) else None,
        "depends_on": [],
        "risk": "READ",
    })

    # Prior Task Experience Reflection (Episodic Memory)
    if past_memories:
        top_mem = past_memories[0]
        disc_text = "; ".join(top_mem.get("discoveries", []))[:150]
        plan_steps.append({
            "step": len(plan_steps) + 1,
            "stage": "prior_experience_reflection",
            "description": f"Apply prior task memory from {top_mem.get('task_id')}: {disc_text or 'utilize past solution patterns'}",
            "status": "pending",
            "past_task_id": top_mem.get("task_id"),
            "depends_on": [1],
            "risk": "READ",
        })

    # Stage 2: Long-Term Engineering Memory Alignment (if applicable)
    if relevant_decisions:
        top_rule = relevant_decisions[0]
        plan_steps.append({
            "step": len(plan_steps) + 1,
            "stage": "architectural_alignment",
            "description": f"Apply repository rule [{top_rule.subject}]: {top_rule.decision}",
            "status": "pending",
            "depends_on": [1],
            "risk": "READ",
            "decision_id": top_rule.decision_id,
        })

    # Stage 3: Core Implementation
    step_impl_id = len(plan_steps) + 1
    plan_steps.append({
        "step": step_impl_id,
        "stage": "implementation",
        "description": f"Implement required changes for goal: '{goal}' in {target_files[0] if target_files else 'target modules'}.",
        "status": "pending",
        "targets": target_files[:2],
        "depends_on": [1],
        "risk": "LOW",
        "strategy": f"Adhere to {backend} patterns. Keep interfaces backward compatible.",
    })

    # Stage 4: Downstream Integration / Wiring (if downstream dependents exist)
    if affected_files_preview:
        step_wire_id = len(plan_steps) + 1
        plan_steps.append({
            "step": step_wire_id,
            "stage": "integration_wiring",
            "description": f"Verify and update downstream dependents: {', '.join(affected_files_preview)}.",
            "status": "pending",
            "targets": affected_files_preview,
            "depends_on": [step_impl_id],
            "risk": "LOW",
        })
        last_code_step = step_wire_id
    else:
        last_code_step = step_impl_id

    # Stage 5: Targeted Unit Test Verification
    step_target_test = len(plan_steps) + 1
    target_test_targets = relevant_tests[:2] if relevant_tests else target_files[:2]
    plan_steps.append({
        "step": step_target_test,
        "stage": "targeted_verification",
        "description": f"Execute targeted test suite covering modified components: {', '.join(target_test_targets)}.",
        "status": "pending",
        "command": f"{test_cmd} {' '.join(relevant_tests[:2])}" if relevant_tests else test_cmd,
        "depends_on": [last_code_step],
        "risk": "LOW",
    })

    # Stage 6: Full Regression Verification
    step_regress = len(plan_steps) + 1
    plan_steps.append({
        "step": step_regress,
        "stage": "regression_verification",
        "description": f"Execute full repository test and build suite to ensure zero unintended regressions: '{test_cmd}'.",
        "status": "pending",
        "command": test_cmd,
        "depends_on": [step_target_test],
        "risk": "LOW",
    })

    # Stage 7: Evidence Synthesis & Diff Audit
    plan_steps.append({
        "step": len(plan_steps) + 1,
        "stage": "audit_and_report",
        "description": "Inspect git diff, audit change boundaries against blast radius, and generate empirical evidence report.",
        "status": "pending",
        "depends_on": [step_regress],
        "risk": "READ",
    })

    # Rollback Strategy definition
    rollback_strategy = {
        "command": f"git checkout -- {' '.join(target_files)}" if target_files else "git checkout -- .",
        "rationale": "Discard uncommitted working tree modifications if verification reveals unresolvable regressions.",
    }

    # Strategy metadata attached to state
    plan_metadata = {
        "target_files": target_files,
        "impact_analysis": impact_report.to_dict() if impact_report else {},
        "relevant_tests": relevant_tests,
        "decisions_applied": [d.decision_id for d in relevant_decisions],
        "rollback_strategy": rollback_strategy,
    }

    messages = list(state.get("messages", []))
    messages.append({
        "role": "assistant",
        "content": (
            f"Intelligent Plan generated: {len(plan_steps)} dependency-ordered steps for {backend}. "
            f"Impact blast radius: {len(affected_files_preview)} downstream files. "
            f"Targeted test suite: {len(relevant_tests)} test files identified."
        )
    })

    try:
        from app.runtime.lifecycle import event_broker
        from app.runtime.events import TaskEvent
        event_broker.publish_sync(TaskEvent(
            task_id=task_id,
            event_type="PLAN_GENERATED",
            message=f"Plan formulated: {len(plan_steps)} stages ({backend})",
            payload={
                "steps_count": len(plan_steps),
                "plan": [s.get("description") for s in plan_steps],
                "target_files": target_files,
                "relevant_tests": relevant_tests,
            }
        ))
    except Exception as e:
        logger.debug(f"Failed to emit PLAN_GENERATED: {e}")

    return {
        "plan": plan_steps,
        "current_step": 1,
        "plan_metadata": plan_metadata,
        "messages": messages,
        "observations": list(state.get("observations", [])) + [
            f"Planner: Formulated {len(plan_steps)}-stage execution plan with dependency ordering and blast-radius safeguards."
        ]
    }


def risk_assessment(state: AstraAgentState) -> Dict[str, Any]:
    """
    AUTONOMOUS SAFETY & RISK ASSESSMENT (Phase 3):
    Categorizes operations into 5 risk levels:
    - READ     -> Automatic (read files, inspect AST, list directories)
    - LOW      -> Automatic (edit source code, run tests, run build)
    - MEDIUM   -> Configurable / Automatic in isolated sandbox (install dependency, git commit)
    - HIGH     -> Approval Required (git push, delete branch, PR creation)
    - CRITICAL -> Explicit Human Approval Required (production deploy, drop database, rm -rf, force push)
    """
    goal = state.get("user_goal", "").lower()
    task_id = state.get("task_id", "")
    plan_metadata = state.get("plan_metadata", {})
    impact_data = plan_metadata.get("impact_analysis", {})

    critical_keywords = [
        "drop database", "drop table", "truncate", "rm -rf", "git push --force",
        "deploy to prod", "production deploy", "delete production", "format disk"
    ]
    high_keywords = [
        "git push", "delete branch", "merge to main", "create pull request",
        "publish package", "modify secrets", "aws credentials"
    ]
    medium_keywords = [
        "pip install", "npm install", "poetry add", "git commit"
    ]

    approval_required = False
    risk_level = "LOW"
    rationale = "Routine software engineering task executing in sandbox workspace."

    # Check for Critical actions
    for kw in critical_keywords:
        if kw in goal:
            risk_level = "CRITICAL"
            approval_required = True
            rationale = f"Detected high-hazard operation matching critical keyword: '{kw}'."
            break

    # Check for High actions
    if not approval_required:
        for kw in high_keywords:
            if kw in goal:
                risk_level = "HIGH"
                approval_required = True
                rationale = f"Action modifies external or shared repository state matching: '{kw}'."
                break

    # Check for Medium actions
    if not approval_required:
        for kw in medium_keywords:
            if kw in goal:
                risk_level = "MEDIUM"
                rationale = f"Operation involves dependency installation or commit: '{kw}'."
                break

    # If impact analysis found high blast radius on core infrastructure
    if not approval_required and impact_data.get("risk_level") == "HIGH":
        risk_level = "MEDIUM"
        rationale = f"High blast radius detected ({impact_data.get('blast_radius_score')}) across core components."

    logger.info(f"[{task_id}] Autonomous Safety: level={risk_level}, approval_required={approval_required} ({rationale})")

    return {
        "approval_required": approval_required,
        "approval_status": "pending" if approval_required else "not_requested",
        "risk_level": risk_level,
        "risk_rationale": rationale,
    }
