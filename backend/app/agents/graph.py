from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.debugger import debug_failure
from app.agents.executor import execute_step, observe_step
from app.agents.planner import plan_task, risk_assessment
from app.agents.replanner import replan_step
from app.agents.state import AstraAgentState
from app.agents.supervisor import load_repository_context, understand_task
from app.agents.verifier import verify_solution
from app.analysis.impact import ChangeImpactAnalyzer
from app.config import settings
from app.observability.logging import logger


def impact_analysis_node(state: AstraAgentState) -> Dict[str, Any]:
    """
    CHANGE IMPACT ANALYSIS NODE (Phase 3):
    Analyzes AST import dependencies and symbol call chains before planning.
    Predicts downstream affected files, blast radius, and relevant tests to run.
    """
    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")
    context = state.get("repository_context", {})
    files = context.get("files", [])
    goal = state.get("user_goal", "")

    # Identify candidate target files
    goal_words = set(w for w in goal.lower().split() if len(w) > 3)
    target_files = [f for f in files if any(w in f.lower() for w in goal_words)]
    if not target_files and files:
        target_files = files[:3]

    impact_report = None
    if workspace_path_str:
        ws_p = Path(workspace_path_str)
        if ws_p.exists():
            analyzer = ChangeImpactAnalyzer(ws_p)
            impact_report = analyzer.analyze_impact(target_files[:4], all_repo_files=files)

    plan_metadata = dict(state.get("plan_metadata") or {})
    if impact_report:
        plan_metadata["impact_analysis"] = impact_report.to_dict()
        plan_metadata["relevant_tests"] = impact_report.relevant_tests
        plan_metadata["target_files"] = target_files

    observations = list(state.get("observations", []))
    if impact_report:
        observations.append(
            f"ImpactAnalysis: Identified {len(impact_report.affected_files)} downstream files and "
            f"{len(impact_report.relevant_tests)} relevant tests (Risk: {impact_report.risk_level})."
        )

    return {
        "plan_metadata": plan_metadata,
        "observations": observations,
    }


def escalate_task(state: AstraAgentState) -> Dict[str, Any]:
    """
    ESCALATION NODE (Phase 3):
    Triggered when retry or iteration budget is exhausted.
    Marks task as escalated and compiles diagnostic triage report for human engineers.
    """
    task_id = state.get("task_id", "")
    retry_count = state.get("retry_count", 0)
    logger.warning(f"[{task_id}] Retry budget exhausted ({retry_count}/{settings.MAX_RETRIES}). Escalating task.")

    observations = list(state.get("observations", []))
    observations.append(
        f"Escalation: Retry budget ({retry_count}/{settings.MAX_RETRIES}) reached. "
        "Compiling comprehensive diagnostic root-cause summary for human engineering handoff."
    )

    return {
        "verification_status": "escalated",
        "observations": observations,
    }


def finalize_task(state: AstraAgentState) -> Dict[str, Any]:
    """
    Produces the final execution report with evidence, git diff, and verification data.
    Also records episodic memory and proven engineering fix patterns to durable memory.
    """
    task_id = state.get("task_id", "")
    verification_status = state.get("verification_status", "uncertain")
    test_results = state.get("test_results", {})
    build_results = state.get("build_results", {})
    files_changed = state.get("files_changed", [])
    diff = state.get("git_diff", "")
    verification_evidence = state.get("verification_evidence", {})
    failure_history = state.get("failure_history", [])

    final_report = {
        "task_id": task_id,
        "status": verification_status,
        "goal": state.get("user_goal", ""),
        "evidence": {
            "tests": {
                "passed": test_results.get("passed", 0),
                "failed": test_results.get("failed", 0),
                "errors": test_results.get("errors", 0),
                "command": test_results.get("command", ""),
            },
            "build": build_results.get("status", "skipped"),
            "files_changed_count": len(files_changed),
            "files_changed": files_changed,
            "verification_evidence": verification_evidence,
        },
        "git_diff": diff,
        "timeline": state.get("observations", []),
        "iterations": state.get("iteration_count", 0),
        "retries": state.get("retry_count", 0),
        "failures_diagnosed": len(failure_history),
        "failure_history": failure_history,
        "errors": state.get("errors", []),
    }

    logger.info(f"[{task_id}] Final report generated with status: {verification_status}")

    # Record task experience into episodic and engineering memory
    try:
        from app.memory.store import get_task_memory_store
        from app.memory.engineering import get_engineering_memory_store
        from app.rag.incremental import IncrementalIndexer

        repo_id = state.get("repository_id") or task_id or "default_repo"
        failures = list(failure_history)
        discoveries = []
        for f in failures:
            if isinstance(f, dict) and f.get("error"):
                cat = f.get("category", "failure").upper()
                root = f.get("root_cause", "")
                discoveries.append(f"[{cat}] {f['error'][:150]} (Root cause: {root})")

        solution = f"Modified {len(files_changed)} files: {', '.join(files_changed)}" if files_changed else "No file changes required"

        mem_store = get_task_memory_store()
        mem_store.record_task_experience(
            task_id=task_id,
            repo_id=repo_id,
            goal=state.get("user_goal", ""),
            files_modified=files_changed,
            test_status=verification_status,
            failure_history=failures,
            discoveries=discoveries,
            solution_summary=solution
        )

        # If task had failures and subsequently passed, permanently record proven fix pattern
        if failures and verification_status == "verified":
            try:
                eng_store = get_engineering_memory_store()
                primary_fail = failures[0]
                eng_store.record_decision(
                    repo_id=repo_id,
                    category="proven_fix",
                    subject=f"Resolved {primary_fail.get('category', 'runtime')} defect in {files_changed[0] if files_changed else 'module'}",
                    decision=f"Solution applied: {solution}. Root cause addressed: {primary_fail.get('hypothesis', '')}",
                    evidence={"task_id": task_id, "primary_failure": primary_fail, "files": files_changed}
                )
            except Exception as eng_e:
                logger.debug(f"Could not record proven fix in engineering memory: {eng_e}")

        # Incrementally update vector index for modified files
        workspace_path = state.get("workspace_path")
        if workspace_path and files_changed:
            ws_p = Path(workspace_path)
            if ws_p.exists():
                indexer = IncrementalIndexer()
                indexer.index_changes(ws_p, repo_id=repo_id, explicit_changed_files=files_changed)
    except Exception as mem_err:
        logger.warning(f"Error persisting task memory or incremental index: {mem_err}")

    return {
        "final_result": final_report
    }


def should_continue_or_finalize(
    state: AstraAgentState
) -> Literal["finalize", "debug"]:
    """
    Conditional routing edge after verification.
    Terminates if verified or if safety limits are reached.
    """
    status = state.get("verification_status")
    iteration_count = state.get("iteration_count", 0)
    retry_count = state.get("retry_count", 0)

    if status in ["verified", "VERIFIED"]:
        logger.info("Verification passed with empirical evidence. Routing to finalize.")
        return "finalize"

    if status in ["partially_verified", "PARTIALLY_VERIFIED"] and iteration_count >= 2:
        logger.info("Task partially verified and iteration complete. Routing to finalize.")
        return "finalize"

    if iteration_count >= settings.MAX_ITERATIONS:
        logger.warning(f"Iteration limit reached ({iteration_count}/{settings.MAX_ITERATIONS}). Routing to finalize.")
        return "finalize"

    if retry_count >= settings.MAX_RETRIES:
        logger.warning(f"Retry limit reached ({retry_count}/{settings.MAX_RETRIES}). Routing to finalize.")
        return "finalize"

    logger.info(f"Verification {status}. Routing to autonomous debugger.")
    return "debug"


def should_reexecute_or_escalate(
    state: AstraAgentState
) -> Literal["execute", "escalate"]:
    """
    Conditional routing edge after replanning.
    Escalates gracefully if retry budget is exhausted.
    """
    retry_count = state.get("retry_count", 0)
    if retry_count > settings.MAX_RETRIES:
        logger.warning(f"Retry count {retry_count} exceeds limit {settings.MAX_RETRIES}. Escalating.")
        return "escalate"
    return "execute"


def approval_wait(state: AstraAgentState) -> Dict[str, Any]:
    """Halts graph execution when an action requires human approval."""
    task_id = state.get("task_id", "")
    logger.warning(f"[{task_id}] Execution paused pending human approval.")
    return {
        "verification_status": "paused_for_approval",
        "observations": list(state.get("observations", [])) + [
            "Workflow paused: Human authorization required before execution."
        ]
    }


def should_execute_or_pause(state: AstraAgentState) -> Literal["execute", "approval_wait"]:
    if state.get("approval_required") and state.get("approval_status") == "pending":
        return "approval_wait"
    return "execute"


def build_astra_graph() -> StateGraph:
    """
    Builds and compiles the ASTRA 2.0 autonomous engineering workflow graph
    implementing the full Phase 3 state machine.
    """
    from langgraph.checkpoint.memory import MemorySaver

    workflow = StateGraph(AstraAgentState)

    # Register Nodes
    workflow.add_node("understand_task", understand_task)
    workflow.add_node("load_repository_context", load_repository_context)
    workflow.add_node("impact_analysis", impact_analysis_node)
    workflow.add_node("plan", plan_task)
    workflow.add_node("risk_assessment", risk_assessment)
    workflow.add_node("approval_wait", approval_wait)
    workflow.add_node("execute", execute_step)
    workflow.add_node("observe", observe_step)
    workflow.add_node("verify", verify_solution)
    workflow.add_node("debug", debug_failure)
    workflow.add_node("replan", replan_step)
    workflow.add_node("escalate", escalate_task)
    workflow.add_node("finalize", finalize_task)

    # Establish Edges
    workflow.add_edge(START, "understand_task")
    workflow.add_edge("understand_task", "load_repository_context")
    workflow.add_edge("load_repository_context", "impact_analysis")
    workflow.add_edge("impact_analysis", "plan")
    workflow.add_edge("plan", "risk_assessment")

    # Human-in-the-loop conditional pause before execution
    workflow.add_conditional_edges(
        "risk_assessment",
        should_execute_or_pause,
        {
            "execute": "execute",
            "approval_wait": "approval_wait",
        }
    )
    workflow.add_edge("approval_wait", END)

    workflow.add_edge("execute", "observe")
    workflow.add_edge("observe", "verify")

    # Conditional branching from Verify
    workflow.add_conditional_edges(
        "verify",
        should_continue_or_finalize,
        {
            "finalize": "finalize",
            "debug": "debug",
        }
    )

    # Loop back from debug -> replan -> conditional (execute or escalate)
    workflow.add_edge("debug", "replan")
    workflow.add_conditional_edges(
        "replan",
        should_reexecute_or_escalate,
        {
            "execute": "execute",
            "escalate": "escalate",
        }
    )

    workflow.add_edge("escalate", "finalize")
    workflow.add_edge("finalize", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Compiled application graph
astra_graph = build_astra_graph()
