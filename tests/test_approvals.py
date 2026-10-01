"""Unit tests for ASTRA V4 Approval Pipeline."""
import threading
import time
from astra.approval import ApprovalManager, ApprovalStatus


def test_approval_manager_approve_flow():
    mgr = ApprovalManager(default_timeout=5.0)
    req = mgr.create_request(
        session_id="sess_123",
        tool_name="run_command",
        arguments={"command": "rm -rf /"},
        description="Dangerous command deletion",
    )
    assert req.status == ApprovalStatus.PENDING

    # Asynchronous responder
    def _respond():
        time.sleep(0.1)
        mgr.respond(req.approval_id, approved=True)

    t = threading.Thread(target=_respond)
    t.start()

    decision = mgr.wait_for_decision(req)
    t.join()

    assert decision is True
    assert req.status == ApprovalStatus.APPROVED


def test_approval_manager_reject_flow():
    mgr = ApprovalManager(default_timeout=5.0)
    req = mgr.create_request(
        session_id="sess_456",
        tool_name="run_command",
        arguments={"command": "format c:"},
        description="Format drive",
    )
    assert req.status == ApprovalStatus.PENDING

    def _respond():
        time.sleep(0.1)
        mgr.respond(req.approval_id, approved=False)

    t = threading.Thread(target=_respond)
    t.start()

    decision = mgr.wait_for_decision(req)
    t.join()

    assert decision is False
    assert req.status == ApprovalStatus.REJECTED


def test_approval_manager_timeout_expiration():
    mgr = ApprovalManager(default_timeout=0.2)
    req = mgr.create_request(
        session_id="sess_789",
        tool_name="delete_file",
        arguments={"file_path": "critical.py"},
        description="Delete critical file",
        timeout_seconds=0.1,
    )
    decision = mgr.wait_for_decision(req)
    assert decision is False
    assert req.status == ApprovalStatus.EXPIRED
