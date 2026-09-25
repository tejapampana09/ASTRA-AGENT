from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.observability.logging import logger
from app.repository.analyzer import RepositoryAnalyzer
from app.repository.scanner import RepositoryScanner
from app.repository.symbols import SymbolExtractor


class RepositoryIndexer:
    """Indexes files, symbols, and dependencies into an in-memory or persisted index."""

    @classmethod
    def build_index(cls, repo_path: Path) -> Dict[str, Any]:
        logger.info(f"Building repository index for: {repo_path}")
        summary = RepositoryScanner.scan(repo_path)
        symbols = SymbolExtractor.index_workspace_symbols(repo_path)
        deps = RepositoryAnalyzer.analyze_dependencies(repo_path)

        return {
            "summary": summary.to_dict(),
            "symbol_count": len(symbols),
            "symbols": [
                {
                    "name": s.name,
                    "kind": s.kind,
                    "file_path": s.file_path,
                    "line": s.line_number,
                    "docstring": s.docstring,
                    "params": s.parameters,
                }
                for s in symbols
            ],
            "dependencies": deps,
        }
