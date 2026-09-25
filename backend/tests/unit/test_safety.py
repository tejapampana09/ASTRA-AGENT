from __future__ import annotations

from app.safety.permissions import ActionPermissionManager, RiskLevel
from app.safety.policies import SecurityPolicies
from app.safety.approvals import ApprovalManager


def test_permission_risk_levels():
    assert ActionPermissionManager.get_risk_level("read_file") == RiskLevel.READ
    assert ActionPermissionManager.get_risk_level("create_file") == RiskLevel.LOW
    assert ActionPermissionManager.get_risk_level("git_commit") == RiskLevel.MEDIUM
    assert ActionPermissionManager.get_risk_level("git_push", {"branch": "feature-1"}) == RiskLevel.HIGH
    assert ActionPermissionManager.get_risk_level("git_push", {"branch": "main"}) == RiskLevel.CRITICAL

    # Test auto approval check
    assert ActionPermissionManager.requires_approval("read_file") is False
    assert ActionPermissionManager.requires_approval("git_push", {"branch": "main"}) is True


def test_security_command_validation():
    allowed, _ = SecurityPolicies.validate_command("pytest -v")
    assert allowed is True

    blocked, reason = SecurityPolicies.validate_command("rm -rf /")
    assert blocked is False
    assert "blocked" in reason


def test_approval_manager_lifecycle():
    mgr = ApprovalManager()
    ticket = mgr.create_request("t-123", "git_push", {"branch": "main"})
    assert ticket.status == "pending"
    assert ticket.risk_level == RiskLevel.CRITICAL

    approved = mgr.approve(ticket.id, comment="Approved by lead engineer")
    assert approved.status == "approved"
    assert approved.comment == "Approved by lead engineer"
