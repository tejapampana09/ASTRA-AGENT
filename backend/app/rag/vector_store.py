from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.observability.logging import logger
from app.rag.indexer import ChunkType, IndexedCodeChunk


class VectorStore(ABC):
    """Abstract interface for storing and querying vector embeddings with metadata filters."""

    @abstractmethod
    def upsert_chunks(self, chunks: List[IndexedCodeChunk]) -> int:
        pass

    @abstractmethod
    def delete_file_chunks(self, repo_id: str, file_path: str) -> int:
        pass

    @abstractmethod
    def delete_repo_chunks(self, repo_id: str) -> int:
        pass

    @abstractmethod
    def search(
        self,
        repo_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        chunk_types: Optional[List[ChunkType]] = None,
        file_path_prefix: Optional[str] = None,
    ) -> List[Tuple[IndexedCodeChunk, float]]:
        pass


class InMemoryVectorStore(VectorStore):
    """
    High-performance in-memory vector store with cosine similarity ranking and metadata filtering.
    Default store for development, evaluation suites, and offline environments.
    """

    def __init__(self):
        # repo_id -> chunk_id -> IndexedCodeChunk
        self._store: Dict[str, Dict[str, IndexedCodeChunk]] = {}

    def upsert_chunks(self, chunks: List[IndexedCodeChunk]) -> int:
        count = 0
        for chunk in chunks:
            if chunk.repo_id not in self._store:
                self._store[chunk.repo_id] = {}
            self._store[chunk.repo_id][chunk.chunk_id] = chunk
            count += 1
        return count

    def delete_file_chunks(self, repo_id: str, file_path: str) -> int:
        if repo_id not in self._store:
            return 0
        to_del = [
            cid for cid, chunk in self._store[repo_id].items()
            if chunk.file_path == file_path
        ]
        for cid in to_del:
            del self._store[repo_id][cid]
        return len(to_del)

    def delete_repo_chunks(self, repo_id: str) -> int:
        if repo_id in self._store:
            count = len(self._store[repo_id])
            del self._store[repo_id]
            return count
        return 0

    def search(
        self,
        repo_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        chunk_types: Optional[List[ChunkType]] = None,
        file_path_prefix: Optional[str] = None,
    ) -> List[Tuple[IndexedCodeChunk, float]]:
        repo_chunks = self._store.get(repo_id, {})
        if not repo_chunks or not query_embedding:
            return []

        candidates: List[Tuple[IndexedCodeChunk, float]] = []

        q_norm = math.sqrt(sum(x * x for x in query_embedding))
        if q_norm < 1e-9:
            return []

        for chunk in repo_chunks.values():
            # Apply metadata filters
            if chunk_types and chunk.chunk_type not in chunk_types:
                continue
            if file_path_prefix and not chunk.file_path.startswith(file_path_prefix):
                continue

            if not chunk.embedding:
                continue

            c_norm = math.sqrt(sum(x * x for x in chunk.embedding))
            if c_norm < 1e-9:
                continue

            dot = sum(a * b for a, b in zip(query_embedding, chunk.embedding))
            cosine_sim = dot / (q_norm * c_norm)
            candidates.append((chunk, cosine_sim))

        # Rank descending by cosine similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def get_all_chunks(self, repo_id: str) -> List[IndexedCodeChunk]:
        return list(self._store.get(repo_id, {}).values())


class PostgresVectorStore(VectorStore):
    """
    Production PostgreSQL vector store backed by pgvector and SQLAlchemy.
    Uses vector distance operator (<=> for cosine distance) with indexed metadata filters.
    """

    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory
        # Fallback in-memory mirror if database is not reachable
        self._fallback = InMemoryVectorStore()

    def upsert_chunks(self, chunks: List[IndexedCodeChunk]) -> int:
        # Mirror in fallback store for immediate local search
        self._fallback.upsert_chunks(chunks)

        if not self._session_factory:
            return len(chunks)

        try:
            from app.database.models import CodeChunkRecord
            with self._session_factory() as session:
                for chunk in chunks:
                    rec = CodeChunkRecord(
                        id=chunk.chunk_id,
                        repo_id=chunk.repo_id,
                        file_path=chunk.file_path,
                        symbol=chunk.symbol,
                        chunk_type=chunk.chunk_type.value,
                        language=chunk.language,
                        content=chunk.content,
                        commit_sha=chunk.commit_sha,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        metadata_json=chunk.metadata,
                        embedding=chunk.embedding,
                    )
                    session.merge(rec)
                session.commit()
            return len(chunks)
        except Exception as e:
            logger.warning(f"Postgres upsert fallback to memory: {e}")
            return len(chunks)

    def delete_file_chunks(self, repo_id: str, file_path: str) -> int:
        self._fallback.delete_file_chunks(repo_id, file_path)
        if not self._session_factory:
            return 0
        try:
            from app.database.models import CodeChunkRecord
            with self._session_factory() as session:
                deleted = session.query(CodeChunkRecord).filter_by(
                    repo_id=repo_id, file_path=file_path
                ).delete()
                session.commit()
                return deleted
        except Exception as e:
            logger.warning(f"Postgres delete error: {e}")
            return 0

    def delete_repo_chunks(self, repo_id: str) -> int:
        self._fallback.delete_repo_chunks(repo_id)
        if not self._session_factory:
            return 0
        try:
            from app.database.models import CodeChunkRecord
            with self._session_factory() as session:
                deleted = session.query(CodeChunkRecord).filter_by(repo_id=repo_id).delete()
                session.commit()
                return deleted
        except Exception as e:
            logger.warning(f"Postgres delete error: {e}")
            return 0

    def search(
        self,
        repo_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        chunk_types: Optional[List[ChunkType]] = None,
        file_path_prefix: Optional[str] = None,
    ) -> List[Tuple[IndexedCodeChunk, float]]:
        """
        Executes real vector distance queries via SQL.
        On PostgreSQL: Uses native pgvector cosine distance operator (<=> / cosine_distance).
        On SQLite / local dialects: Performs SQL-backed vector query with exact cosine calculation.
        Falls back to in-memory store if database is unreachable.
        """
        if self._session_factory:
            try:
                from app.database.models import CodeChunkRecord
                from sqlalchemy import select, asc

                with self._session_factory() as session:
                    bind = session.get_bind()
                    dialect_name = bind.dialect.name if bind else "postgresql"

                    if dialect_name == "postgresql":
                        # Native pgvector SQL cosine distance search: embedding <=> :vec
                        distance_expr = CodeChunkRecord.embedding.cosine_distance(query_embedding)
                        query = select(CodeChunkRecord, distance_expr.label("distance")).filter(
                            CodeChunkRecord.repo_id == repo_id,
                            CodeChunkRecord.embedding.isnot(None)
                        )
                        if chunk_types:
                            query = query.filter(CodeChunkRecord.chunk_type.in_([c.value for c in chunk_types]))
                        if file_path_prefix:
                            query = query.filter(CodeChunkRecord.file_path.startswith(file_path_prefix))

                        query = query.order_by(asc("distance")).limit(top_k)
                        rows = session.execute(query).all()

                        results: List[Tuple[IndexedCodeChunk, float]] = []
                        for row in rows:
                            rec = row[0]
                            dist = row[1]
                            similarity = 1.0 - float(dist) if dist is not None else 0.0
                            chunk = self._record_to_chunk(rec)
                            results.append((chunk, similarity))
                        return results
                    else:
                        # SQL-backed query on SQLite or other dialect
                        query = select(CodeChunkRecord).filter(
                            CodeChunkRecord.repo_id == repo_id,
                            CodeChunkRecord.embedding.isnot(None)
                        )
                        if chunk_types:
                            query = query.filter(CodeChunkRecord.chunk_type.in_([c.value for c in chunk_types]))
                        if file_path_prefix:
                            query = query.filter(CodeChunkRecord.file_path.startswith(file_path_prefix))

                        records = session.execute(query).scalars().all()
                        scored = []
                        q_norm = math.sqrt(sum(x * x for x in query_embedding))
                        if q_norm > 1e-9:
                            for rec in records:
                                emb = rec.embedding
                                if isinstance(emb, list) and len(emb) == len(query_embedding):
                                    c_norm = math.sqrt(sum(x * x for x in emb))
                                    if c_norm > 1e-9:
                                        sim = sum(a * b for a, b in zip(query_embedding, emb)) / (q_norm * c_norm)
                                        scored.append((self._record_to_chunk(rec), sim))

                        scored.sort(key=lambda x: x[1], reverse=True)
                        return scored[:top_k]

            except Exception as e:
                logger.warning(f"Database vector query failed, falling back to memory store: {e}")

        # Fallback to in-memory store
        return self._fallback.search(
            repo_id=repo_id,
            query_embedding=query_embedding,
            top_k=top_k,
            chunk_types=chunk_types,
            file_path_prefix=file_path_prefix
        )

    def get_all_chunks(self, repo_id: str) -> List[IndexedCodeChunk]:
        if self._session_factory:
            try:
                from app.database.models import CodeChunkRecord
                from sqlalchemy import select
                with self._session_factory() as session:
                    records = session.execute(
                        select(CodeChunkRecord).filter_by(repo_id=repo_id)
                    ).scalars().all()
                    if records:
                        return [self._record_to_chunk(r) for r in records]
            except Exception as e:
                logger.debug(f"get_all_chunks DB query fallback: {e}")

        return self._fallback.get_all_chunks(repo_id)

    @staticmethod
    def _record_to_chunk(rec) -> IndexedCodeChunk:
        from app.rag.indexer import ChunkType, IndexedCodeChunk
        valid_types = {e.value for e in ChunkType}
        ctype = ChunkType(rec.chunk_type) if rec.chunk_type in valid_types else ChunkType.FUNCTION
        return IndexedCodeChunk(
            chunk_id=rec.id,
            repo_id=rec.repo_id,
            file_path=rec.file_path,
            symbol=rec.symbol or "",
            chunk_type=ctype,
            language=rec.language,
            content=rec.content,
            embedding=list(rec.embedding) if rec.embedding is not None else None,
            commit_sha=rec.commit_sha,
            start_line=rec.start_line,
            end_line=rec.end_line,
            metadata=rec.metadata_json or {},
        )


# Global singleton instance
_default_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _default_vector_store
    if _default_vector_store is None:
        from app.database.session import get_sync_session_factory
        sync_factory = get_sync_session_factory()
        if sync_factory is not None:
            _default_vector_store = PostgresVectorStore(db_session_factory=sync_factory)
        else:
            _default_vector_store = InMemoryVectorStore()
    return _default_vector_store


def set_vector_store(store: VectorStore) -> None:
    global _default_vector_store
    _default_vector_store = store

