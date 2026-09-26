from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Set

from app.observability.logging import logger
from app.repository.symbols import SymbolExtractor


class RepositoryAnalyzer:
    """Analyzes imports, internal dependencies, and architectural structure across a repository."""

    @classmethod
    def analyze_dependencies(cls, repo_path: Path) -> Dict[str, Any]:
        internal_modules: Set[str] = set()
        external_imports: Set[str] = set()
        file_imports_map: Dict[str, List[str]] = {}

        ignored_parts = {".git", "__pycache__", "node_modules", ".venv", "venv", "workspaces", "temp_workspaces", "sandbox_data", ".pytest_cache", "dist", "build"}
        for p in repo_path.rglob("*.py"):
            if any(part in ignored_parts for part in p.parts):
                continue
            rel = p.relative_to(repo_path).as_posix()
            mod_name = rel.replace("/", ".").replace(".py", "")
            internal_modules.add(mod_name)

            intel = SymbolExtractor.extract_from_python_file(p, rel)
            file_imports_map[rel] = intel.imports
            for imp in intel.imports:
                root_pkg = imp.split(".")[0]
                external_imports.add(root_pkg)

        return {
            "internal_modules": sorted(list(internal_modules)),
            "external_packages": sorted(list(external_imports)),
            "import_graph": file_imports_map,
        }
