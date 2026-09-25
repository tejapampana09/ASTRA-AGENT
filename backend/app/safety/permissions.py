from __future__ import annotations

from enum import Enum
from typing import Dict


class RiskLevel(str, Enum):
    READ = "READ"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ActionPermissionManager:
    """Manages risk classifications and auto-approval policies for agent operations."""

    DEFAULT_TOOL_RISK_MAP: Dict[str, RiskLevel] = {
        # Read-only operations
        "read_file": RiskLevel.READ,
        "search_files": RiskLevel.READ,
        "list_files": RiskLevel.READ,
        "git_status": RiskLevel.READ,
        "git_diff": RiskLevel.READ,
        "git_log": RiskLevel.READ,
        "github_get_issue": RiskLevel.READ,
        "github_list_prs": RiskLevel.READ,

        # Low risk
        "create_file": RiskLevel.LOW,
        "edit_file": RiskLevel.LOW,
        "run_test": RiskLevel.LOW,

        # Medium risk
        "git_branch": RiskLevel.MEDIUM,
        "git_checkout": RiskLevel.MEDIUM,
        "git_commit": RiskLevel.MEDIUM,
        "delete_file": RiskLevel.MEDIUM,

        # High risk
        "git_push": RiskLevel.HIGH,
        "github_create_pr": RiskLevel.HIGH,
        "run_command": RiskLevel.HIGH,  # Arbitrary commands default to HIGH unless recognized as safe test/build

        # Critical risk
        "deploy_production": RiskLevel.CRITICAL,
        "drop_database": RiskLevel.CRITICAL,
    }

    @classmethod
    def get_risk_level(cls, tool_name: str, arguments: Dict[str, object] = None) -> RiskLevel:
        args = arguments or {}
        if tool_name == "run_command":
            cmd = str(args.get("command", "")).strip().lower()
            if any(cmd.startswith(prefix) for prefix in ["pytest", "npm test", "cargo test", "go test", "python -m pytest", "ruff", "flake8"]):
                return RiskLevel.LOW
            if any(danger in cmd for danger in ["rm -rf", "format", "del /f /q", "mkfs"]):
                return RiskLevel.CRITICAL
            return RiskLevel.HIGH

        if tool_name == "git_push":
            branch = str(args.get("branch", "")).lower()
            if branch in ["main", "master", "prod", "production"]:
                return RiskLevel.CRITICAL
            return RiskLevel.HIGH

        return cls.DEFAULT_TOOL_RISK_MAP.get(tool_name, RiskLevel.MEDIUM)

    @classmethod
    def requires_approval(cls, tool_name: str, arguments: Dict[str, object] = None) -> bool:
        risk = cls.get_risk_level(tool_name, arguments)
        return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
