from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, START, StateGraph

from app.agents.debugger import debug_failure
from app.agents.executor import execute_step, observe_step
from app.agents.planner import plan_task, risk_assessment
from app.agents.replanner import replan_step
from app.agents.state import AstraAgentState
from app.agents.supervisor import load_repository_context, understand_task
from app.agents.verifier import verify_solution
from app.config import settings
from app.observability.logging import logger


def finalize_task(state: AstraAgentState) -> Dict[str, Any]:
    """
    Produces the final execution report with evidence, git diff, and verification data.
    """
    task_id = state.get("task_id", "")
    verification_status = state.get("verification_status", "uncertain")
    test_results = state.get("test_results", {})
    build_results = state.get("build_results", {})
    files_changed = state.get("files_changed", [])
    diff = state.get("git_diff", "")

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
        },
        "git_diff": diff,
        "timeline": state.get("observations", []),
        "iterations": state.get("iteration_count", 0),
        "retries": state.get("retry_count", 0),
        "errors": state.get("errors", []),
    }

    logger.info(f"[{task_id}] Final report generated with status: {verification_status}")

    # Record task experience into episodic memory
    try:
        from app.memory.store import get_task_memory_store
        from app.rag.incremental import IncrementalIndexer

        repo_id = state.get("repository_id") or task_id or "default_repo"
        failures = list(state.get("failure_history", []))
        discoveries = []
        for f in failures:
            if isinstance(f, dict) and f.get("error"):
                discoveries.append(f"Observed failure: {f['error'][:200]}")

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
    Terminates if verified or if safety limits (MAX_ITERATIONS / MAX_RETRIES) are reached.
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


def approval_wait(state: AstraAgentState) -> Dict[str, Any]:
    """
    Halts graph execution when an action requires human approval.
    """
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
    with support for human-in-the-loop interruption and memory checkpointing.
    """
    from langgraph.checkpoint.memory import MemorySaver

    workflow = StateGraph(AstraAgentState)

    # Register Nodes
    workflow.add_node("understand_task", understand_task)
    workflow.add_node("load_repository_context", load_repository_context)
    workflow.add_node("plan", plan_task)
    workflow.add_node("risk_assessment", risk_assessment)
    workflow.add_node("approval_wait", approval_wait)
    workflow.add_node("execute", execute_step)
    workflow.add_node("observe", observe_step)
    workflow.add_node("verify", verify_solution)
    workflow.add_node("debug", debug_failure)
    workflow.add_node("replan", replan_step)
    workflow.add_node("finalize", finalize_task)

    # Establish Edges
    workflow.add_edge(START, "understand_task")
    workflow.add_edge("understand_task", "load_repository_context")
    workflow.add_edge("load_repository_context", "plan")
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

    # Loop back from debug -> replan -> execute
    workflow.add_edge("debug", "replan")
    workflow.add_edge("replan", "execute")

    # Finalize -> END
    workflow.add_edge("finalize", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Compiled application graph
astra_graph = build_astra_graph()
