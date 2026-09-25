from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.observability.logging import logger
from app.rag.indexing import CodeChunk, CodeChunker
from app.repository.symbols import SymbolExtractor


class HybridCodeRetriever:
    """
    Hybrid retriever combining keyword, symbol match, and path relevance
    so the agent receives only targeted relevant context rather than the entire codebase.
    """

    @classmethod
    def retrieve(cls, workspace_path: Path, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_terms = set(re.findall(r"\w+", query.lower()))
        matched_chunks: List[Dict[str, Any]] = []

        # 1. Symbol matching
        symbols = SymbolExtractor.index_workspace_symbols(workspace_path)
        symbol_map = {s.name.lower(): s for s in symbols}

        for term in query_terms:
            if term in symbol_map:
                s = symbol_map[term]
                matched_chunks.append({
                    "type": "symbol",
                    "file_path": s.file_path,
                    "line": s.line_number,
                    "name": s.name,
                    "score": 10.0,
                    "snippet": f"def {s.name}({', '.join(s.parameters)}): # {s.docstring or ''}"
                })

        # 2. Keyword & path chunk retrieval
        for p in workspace_path.rglob("*.py"):
            if any(part in {".git", "__pycache__", "node_modules", ".venv"} for part in p.parts):
                continue
            rel = p.relative_to(workspace_path).as_posix()
            chunks = CodeChunker.chunk_file(p, rel)
            for c in chunks:
                # Calculate term overlap score
                content_lower = c.content.lower()
                matches = sum(1 for term in query_terms if term in content_lower)
                if matches > 0:
                    matched_chunks.append({
                        "type": "text",
                        "file_path": c.file_path,
                        "line_range": f"{c.start_line}-{c.end_line}",
                        "score": float(matches),
                        "snippet": c.content[:300]
                    })

        # Sort by score descending and take top_k
        matched_chunks.sort(key=lambda x: x["score"], reverse=True)
        return matched_chunks[:top_k]
