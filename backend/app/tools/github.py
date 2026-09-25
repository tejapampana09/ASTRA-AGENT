from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import httpx

from app.config import settings
from app.observability.logging import logger
from app.safety.permissions import RiskLevel
from app.tools.registry import AstraTool, ToolExecutionResult, tool_registry


class GitHubClient:
    """Wrapper around GitHub REST API with authorization header."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.GITHUB_TOKEN
        self.base_url = settings.GITHUB_API_URL

    @property
    def headers(self) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github.v3+json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h


class GitHubIssuesTool(AstraTool):
    name = "github_issues"
    description = "Retrieves details of a GitHub issue or lists issues."
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository in owner/repo format"},
            "issue_number": {"type": "integer", "description": "Issue number (optional)"}
        },
        "required": ["repo"]
    }
    permission_level = RiskLevel.READ

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        repo = kwargs.get("repo", "")
        issue_number = kwargs.get("issue_number")
        client = GitHubClient()

        url = f"{client.base_url}/repos/{repo}/issues"
        if issue_number:
            url += f"/{issue_number}"

        try:
            with httpx.Client(timeout=15.0) as http_client:
                resp = http_client.get(url, headers=client.headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if issue_number:
                        summary = f"Issue #{data.get('number')}: {data.get('title')}\n\n{data.get('body')}"
                    else:
                        summary = "\n".join([f"#{i.get('number')}: {i.get('title')}" for i in data[:10]])
                    return ToolExecutionResult(success=True, output=summary)
                else:
                    return ToolExecutionResult(success=False, output="", error=f"GitHub API HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


class GitHubPullRequestsTool(AstraTool):
    name = "github_pull_requests"
    description = "Creates or inspects GitHub pull requests."
    input_schema = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "owner/repo"},
            "action": {"type": "string", "enum": ["list", "create"], "default": "list"},
            "title": {"type": "string", "description": "PR title"},
            "head": {"type": "string", "description": "Branch containing changes"},
            "base": {"type": "string", "description": "Target branch (e.g. main)", "default": "main"},
            "body": {"type": "string", "description": "PR description"}
        },
        "required": ["repo"]
    }
    permission_level = RiskLevel.HIGH

    def execute(self, workspace_path: Path, **kwargs: Any) -> ToolExecutionResult:
        repo = kwargs.get("repo", "")
        action = kwargs.get("action", "list")
        client = GitHubClient()

        url = f"{client.base_url}/repos/{repo}/pulls"
        try:
            with httpx.Client(timeout=15.0) as http_client:
                if action == "create":
                    payload = {
                        "title": kwargs.get("title", "ASTRA Automated PR"),
                        "head": kwargs.get("head", ""),
                        "base": kwargs.get("base", "main"),
                        "body": kwargs.get("body", "PR prepared autonomously by ASTRA 2.0 with verification evidence.")
                    }
                    resp = http_client.post(url, headers=client.headers, json=payload)
                    if resp.status_code in [200, 201]:
                        pr_data = resp.json()
                        return ToolExecutionResult(success=True, output=f"Created PR #{pr_data.get('number')}: {pr_data.get('html_url')}")
                    return ToolExecutionResult(success=False, output="", error=f"GitHub API Error: {resp.text}")
                else:
                    resp = http_client.get(url, headers=client.headers)
                    if resp.status_code == 200:
                        prs = resp.json()
                        summary = "\n".join([f"PR #{p.get('number')}: {p.get('title')} ({p.get('html_url')})" for p in prs[:5]])
                        return ToolExecutionResult(success=True, output=summary or "No open PRs found.")
                    return ToolExecutionResult(success=False, output="", error=f"GitHub API Error: {resp.text}")
        except Exception as e:
            return ToolExecutionResult(success=False, output="", error=str(e))


tool_registry.register(GitHubIssuesTool())
tool_registry.register(GitHubPullRequestsTool())
