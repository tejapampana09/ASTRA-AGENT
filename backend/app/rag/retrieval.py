from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.observability.logging import logger
from app.rag.embeddings import EmbeddingClient
from app.rag.indexer import ChunkType, IndexedCodeChunk
from app.rag.vector_store import VectorStore, get_vector_store


@dataclass
class CodeFlowChain:
    """Represents an architectural execution path from API route -> Service -> Database model."""
    entrypoint_route: Optional[IndexedCodeChunk] = None
    service_function: Optional[IndexedCodeChunk] = None
    database_model: Optional[IndexedCodeChunk] = None
    related_tests: List[IndexedCodeChunk] = field(default_factory=list)
    flow_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entrypoint_route": self.entrypoint_route.to_dict() if self.entrypoint_route else None,
            "service_function": self.service_function.to_dict() if self.service_function else None,
            "database_model": self.database_model.to_dict() if self.database_model else None,
            "related_tests": [t.to_dict() for t in self.related_tests],
            "flow_summary": self.flow_summary,
        }


@dataclass
class RetrievalResult:
    chunks: List[IndexedCodeChunk]
    flow_chain: Optional[CodeFlowChain] = None
    query: str = ""
    scores: List[float] = field(default_factory=list)


class SemanticRetriever:
    """
    Intelligent code retriever combining dense vector search, symbol resolution,
    and architectural call-chain traversal (API -> Service -> Database Model).
    """

    def __init__(self, vector_store: Optional[VectorStore] = None, embedding_client: Optional[EmbeddingClient] = None):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_client = embedding_client or EmbeddingClient()

    def retrieve(
        self,
        repo_id: str,
        query: str,
        top_k: int = 6,
        include_flow_chain: bool = True
    ) -> RetrievalResult:
        """
        Executes hybrid semantic search with architectural chain reconstruction.
        """
        query_embedding = self.embedding_client.get_embedding_sync(query)
        vector_matches = self.vector_store.search(
            repo_id=repo_id,
            query_embedding=query_embedding,
            top_k=top_k * 2
        )

        all_chunks: List[IndexedCodeChunk] = [c for c, _ in vector_matches]
        scores: List[float] = [s for _, s in vector_matches]

        flow_chain = None
        if include_flow_chain:
            flow_chain = self.trace_code_flow_chain(repo_id, query)
            if flow_chain:
                # Prioritize chain chunks in retrieval
                chain_chunks = []
                if flow_chain.entrypoint_route:
                    chain_chunks.append(flow_chain.entrypoint_route)
                if flow_chain.service_function:
                    chain_chunks.append(flow_chain.service_function)
                if flow_chain.database_model:
                    chain_chunks.append(flow_chain.database_model)
                chain_chunks.extend(flow_chain.related_tests)

                # Prepend chain chunks without duplicates
                seen_ids = set()
                combined: List[IndexedCodeChunk] = []
                combined_scores: List[float] = []

                for cc in chain_chunks:
                    if cc.chunk_id not in seen_ids:
                        seen_ids.add(cc.chunk_id)
                        combined.append(cc)
                        combined_scores.append(1.0)  # maximum architectural relevance

                for c, s in zip(all_chunks, scores):
                    if c.chunk_id not in seen_ids:
                        seen_ids.add(c.chunk_id)
                        combined.append(c)
                        combined_scores.append(s)

                all_chunks = combined
                scores = combined_scores

        return RetrievalResult(
            chunks=all_chunks[:top_k],
            flow_chain=flow_chain,
            query=query,
            scores=scores[:top_k]
        )

    def trace_code_flow_chain(self, repo_id: str, query: str) -> Optional[CodeFlowChain]:
        """
        Synthesizes the architectural code chain:
        e.g., API Route (/login) -> Service (authenticate_user) -> DB Model (User).
        """
        query_terms = set(re.findall(r"\w+", query.lower()))

        # Get all chunks for repo
        if hasattr(self.vector_store, "get_all_chunks"):
            repo_chunks = self.vector_store.get_all_chunks(repo_id)  # type: ignore
        else:
            repo_chunks = [c for c, _ in self.vector_store.search(repo_id, self.embedding_client.get_embedding_sync(query), top_k=50)]

        if not repo_chunks:
            return None

        routes = [c for c in repo_chunks if c.chunk_type == ChunkType.API_ROUTE]
        functions = [c for c in repo_chunks if c.chunk_type == ChunkType.FUNCTION]
        models = [c for c in repo_chunks if c.chunk_type == ChunkType.DB_MODEL]
        tests = [c for c in repo_chunks if c.chunk_type == ChunkType.TEST]

        # 1. Identify target API Route
        best_route = None
        best_route_score = -1
        for r in routes:
            score = sum(1 for t in query_terms if t in r.symbol.lower() or t in r.content.lower())
            if score > best_route_score:
                best_route_score = score
                best_route = r

        # 2. Trace Service Function called by Route
        best_service = None
        if best_route:
            called_in_route = set(best_route.metadata.get("calls", []))
            for fn in functions:
                fn_name = fn.symbol.split(".")[-1]
                if fn_name in called_in_route or any(term in fn_name.lower() for term in query_terms if len(term) > 3):
                    best_service = fn
                    break

        # If no service identified via route call, find matching service function directly
        if not best_service:
            for fn in functions:
                if any(t in fn.symbol.lower() for t in ["auth", "login", "service", "handler"]):
                    best_service = fn
                    break

        # 3. Trace Database Model referenced by Service or Route
        best_model = None
        referenced_symbols = set()
        if best_service:
            referenced_symbols.update(best_service.metadata.get("calls", []))
        if best_route:
            referenced_symbols.update(best_route.metadata.get("calls", []))

        for m in models:
            m_name = m.symbol.lower()
            if m.symbol in referenced_symbols or any(t in m_name for t in ["user", "account", "auth", "token"]):
                best_model = m
                break

        # 4. Find matching tests
        relevant_tests = []
        for t in tests:
            if any(term in t.symbol.lower() for term in ["auth", "login", "user", "token"]) or (best_route and best_route.metadata.get("http_path", "") in t.content):
                relevant_tests.append(t)

        flow_steps = []
        if best_route:
            flow_steps.append(f"API Route: {best_route.symbol} ({best_route.file_path}:{best_route.start_line})")
        if best_service:
            flow_steps.append(f"Service: {best_service.symbol}() ({best_service.file_path}:{best_service.start_line})")
        if best_model:
            flow_steps.append(f"DB Model: {best_model.symbol} ({best_model.file_path}:{best_model.start_line})")

        flow_summary = " -> ".join(flow_steps) if flow_steps else "Direct invocation flow"

        return CodeFlowChain(
            entrypoint_route=best_route,
            service_function=best_service,
            database_model=best_model,
            related_tests=relevant_tests[:2],
            flow_summary=flow_summary
        )


# Backward-compatible hybrid retriever alias
class HybridCodeRetriever:
    @classmethod
    def retrieve(cls, workspace_path: Path, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        retriever = SemanticRetriever()
        results = retriever.retrieve(repo_id="workspace", query=query, top_k=top_k)
        return [
            {
                "type": c.chunk_type.value,
                "file_path": c.file_path,
                "name": c.symbol,
                "line": c.start_line,
                "line_range": f"{c.start_line}-{c.end_line}",
                "snippet": c.content[:300],
                "score": s
            }
            for c, s in zip(results.chunks, results.scores)
        ]
