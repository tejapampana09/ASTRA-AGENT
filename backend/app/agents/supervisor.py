from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.agents.state import AstraAgentState
from app.observability.logging import logger


def understand_task(state: AstraAgentState) -> Dict[str, Any]:
    """Analyzes user goal, extract intent, criteria, and objectives."""
    goal = state.get("user_goal", "")
    logger.info(f"[{state.get('task_id')}] Understanding task: {goal}")

    messages = list(state.get("messages", []))
    messages.append({
        "role": "system",
        "content": f"Task Goal parsed: {goal}"
    })

    return {
        "messages": messages,
        "iteration_count": state.get("iteration_count", 0),
        "retry_count": state.get("retry_count", 0),
    }


def load_repository_context(state: AstraAgentState) -> Dict[str, Any]:
    """Inspects workspace directory, manifests, and files to produce context."""
    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")
    repo_context: Dict[str, Any] = {
        "files": [],
        "languages": [],
        "test_framework": "unknown",
        "has_git": False
    }

    if workspace_path_str:
        ws_path = Path(workspace_path_str)
        if ws_path.exists():
            repo_context["has_git"] = (ws_path / ".git").exists()
            all_files = []
            for p in ws_path.rglob("*"):
                if p.is_file() and not any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                    rel = p.relative_to(ws_path).as_posix()
                    all_files.append(rel)
            repo_context["files"] = all_files[:100]

            # Detect language
            languages = set()
            for f in all_files:
                if f.endswith(".py"):
                    languages.add("Python")
                elif f.endswith((".ts", ".tsx")):
                    languages.add("TypeScript")
                elif f.endswith((".js", ".jsx")):
                    languages.add("JavaScript")
                elif f.endswith(".rs"):
                    languages.add("Rust")
                elif f.endswith(".go"):
                    languages.add("Go")
            repo_context["languages"] = list(languages)

            # Detect test framework
            if any("pytest" in f or "test_" in f or "_test.py" in f for f in all_files):
                repo_context["test_framework"] = "pytest"
            elif any("package.json" in f for f in all_files):
                repo_context["test_framework"] = "npm"

    logger.info(f"[{task_id}] Repository context loaded: {len(repo_context.get('files', []))} files, languages={repo_context.get('languages')}")

    return {
        "repository_context": repo_context
    }
