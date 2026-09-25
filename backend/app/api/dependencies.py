from __future__ import annotations

from typing import Any
from fastapi import Header, HTTPException

from app.config import settings
from app.runtime.lifecycle import task_lifecycle, TaskLifecycleManager
from app.safety.approvals import approval_manager, ApprovalManager


def get_task_lifecycle() -> TaskLifecycleManager:
    return task_lifecycle


def get_approval_manager() -> ApprovalManager:
    return approval_manager
