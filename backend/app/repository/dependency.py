from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import json

from app.observability.logging import logger


class DependencyResolver:
    """Parses manifest files (requirements.txt, package.json, pyproject.toml) to map dependencies."""

    @classmethod
    def resolve_python_dependencies(cls, repo_path: Path) -> List[str]:
        req_file = repo_path / "requirements.txt"
        if not req_file.exists():
            return []
        try:
            lines = req_file.read_text(encoding="utf-8").splitlines()
            return [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        except Exception as e:
            logger.warning(f"Error reading requirements.txt: {e}")
            return []

    @classmethod
    def resolve_npm_dependencies(cls, repo_path: Path) -> Dict[str, str]:
        pkg_file = repo_path / "package.json"
        if not pkg_file.exists():
            return {}
        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            deps = data.get("dependencies", {})
            deps.update(data.get("devDependencies", {}))
            return deps
        except Exception as e:
            logger.warning(f"Error reading package.json: {e}")
            return {}
