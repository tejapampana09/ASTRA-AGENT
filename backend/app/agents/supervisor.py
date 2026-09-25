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
    """
    Inspects workspace directory, AST symbols, dependencies, and architectural manifests
    to produce deep repository intelligence without hallucination.
    """
    from app.repository.analyzer import RepositoryAnalyzer
    from app.repository.scanner import RepositoryScanner
    from app.repository.symbols import SymbolExtractor

    task_id = state.get("task_id", "")
    workspace_path_str = state.get("workspace_path")
    repo_context: Dict[str, Any] = {
        "files": [],
        "languages": [],
        "test_framework": "unknown",
        "has_git": False,
        "symbols": [],
        "dependencies": {},
        "summary": {},
    }

    if workspace_path_str:
        ws_path = Path(workspace_path_str)
        if ws_path.exists():
            # 1. Deep architectural scan
            scanner_summary = RepositoryScanner.scan(ws_path)
            repo_context["summary"] = scanner_summary.to_dict()
            repo_context["languages"] = scanner_summary.languages
            repo_context["test_framework"] = scanner_summary.test_framework or "unknown"
            repo_context["test_command"] = scanner_summary.test_command
            repo_context["build_command"] = scanner_summary.build_command
            repo_context["has_git"] = (ws_path / ".git").exists()

            # 2. Extract code symbols (AST classes, functions, signatures)
            extracted_symbols = SymbolExtractor.index_workspace_symbols(ws_path)
            repo_context["symbols"] = [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "file": s.file_path,
                    "line": s.line_number,
                    "params": s.parameters,
                    "doc": (s.docstring[:100] if s.docstring else None)
                }
                for s in extracted_symbols[:50]
            ]

            # 3. Analyze internal import graph and external dependencies
            deps = RepositoryAnalyzer.analyze_dependencies(ws_path)
            repo_context["dependencies"] = deps

            # 4. List relative files
            all_files = []
            for p in ws_path.rglob("*"):
                if p.is_file() and not any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                    rel = p.relative_to(ws_path).as_posix()
                    all_files.append(rel)
            repo_context["files"] = all_files[:100]

    logger.info(
        f"[{task_id}] Deep repository context loaded: {len(repo_context.get('files', []))} files, "
        f"{len(repo_context.get('symbols', []))} symbols, framework={repo_context.get('summary', {}).get('backend')}"
    )

    return {
        "repository_context": repo_context
    }
