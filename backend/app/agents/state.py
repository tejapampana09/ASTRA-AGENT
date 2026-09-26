from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class AstraAgentState(TypedDict, total=False):
    """
    Strongly typed state for the ASTRA 2.0 autonomous agent.
    Maintains complete context across the LangGraph orchestration cycle.
    """
    task_id: str
    repository_id: str
    user_goal: str
    repository_context: Dict[str, Any]
    plan: List[Dict[str, Any]]
    plan_metadata: Dict[str, Any]
    current_step: int
    messages: List[Dict[str, Any]]
    observations: List[str]
    tool_calls: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    files_changed: List[str]
    test_results: Dict[str, Any]
    build_results: Dict[str, Any]
    verification_evidence: Dict[str, Any]
    last_failure_diagnosis: Dict[str, Any]
    errors: List[str]
    retry_count: int
    iteration_count: int
    verification_status: str  # "pending", "verified", "partially_verified", "failed", "uncertain", "escalated"
    risk_level: str           # "READ", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    risk_rationale: str
    approval_required: bool
    approval_status: str      # "not_requested", "pending", "approved", "rejected"
    final_result: Optional[Dict[str, Any]]
    workspace_path: Optional[str]
    failure_history: List[Dict[str, Any]]
    git_diff: str
    agent_message: str
    final_summary: str
