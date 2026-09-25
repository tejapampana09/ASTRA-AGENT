from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.observability.logging import logger
from app.rag.embeddings import EmbeddingClient
from app.rag.indexer import SemanticCodeChunker, IndexedCodeChunk
from app.rag.vector_store import VectorStore, get_vector_store


class IncrementalIndexer:
    """
    Intelligent incremental repository indexer.
    Only re-parses, re-chunks, and re-embeds files that have changed via Git diff.
    Never re-embeds unchanged portions of the repository.
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_client: Optional[EmbeddingClient] = None
    ):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_client = embedding_client or EmbeddingClient()

    def get_changed_files_from_git(self, repo_path: Path) -> Dict[str, List[str]]:
        """Detects modified, added, and deleted files using git status and diff."""
        added_or_modified: List[str] = []
        deleted: List[str] = []

        try:
            # 1. Check working tree changes and untracked files
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if not line.strip():
                        continue
                    status_code = line[:2].strip()
                    file_path = line[3:].strip()
                    # Normalize Windows path slashes
                    norm_path = file_path.replace("\\", "/")

                    if status_code in ["D", "RD"]:
                        deleted.append(norm_path)
                    else:
                        added_or_modified.append(norm_path)
        except Exception as e:
            logger.debug(f"Git status error in incremental indexing: {e}")

        return {
            "modified": sorted(list(set(added_or_modified))),
            "deleted": sorted(list(set(deleted))),
        }

    def index_changes(
        self,
        repo_path: Path,
        repo_id: str,
        explicit_changed_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes incremental indexing:
        Git Diff -> Changed files -> Re-parse -> Re-chunk -> Re-embed -> Update Vector Store.
        """
        if explicit_changed_files is not None:
            # Explicit file list provided (e.g. from workspace or agent run)
            modified_files = [f.replace("\\", "/") for f in explicit_changed_files]
            deleted_files = []
        else:
            diff_files = self.get_changed_files_from_git(repo_path)
            modified_files = diff_files["modified"]
            deleted_files = diff_files["deleted"]

        chunks_created = 0
        chunks_deleted = 0

        # 1. Handle deleted files
        for rel_del in deleted_files:
            c_del = self.vector_store.delete_file_chunks(repo_id, rel_del)
            chunks_deleted += c_del

        # 2. Handle modified / added files
        all_new_chunks: List[IndexedCodeChunk] = []

        for rel_path in modified_files:
            full_path = repo_path / rel_path
            if not full_path.exists() or not full_path.is_file():
                continue

            # Delete old chunks for this modified file
            c_del = self.vector_store.delete_file_chunks(repo_id, rel_path)
            chunks_deleted += c_del

            # Parse and chunk this single modified file
            file_chunks: List[IndexedCodeChunk] = []
            if full_path.name.endswith(".py"):
                file_chunks = SemanticCodeChunker.chunk_python_file(repo_id, full_path, repo_path)
            elif full_path.name in SemanticCodeChunker.CONFIG_NAMES or full_path.suffix in [".toml", ".yaml", ".yml", ".json"]:
                file_chunks = SemanticCodeChunker.chunk_config_file(repo_id, full_path, repo_path)
            elif full_path.suffix in [".md", ".rst"]:
                file_chunks = SemanticCodeChunker.chunk_documentation(repo_id, full_path, repo_path)

            all_new_chunks.extend(file_chunks)

        # 3. Re-embed ONLY the new chunks
        if all_new_chunks:
            texts = [c.content for c in all_new_chunks]
            # Embeddings generated synchronously or via batching
            for chunk in all_new_chunks:
                chunk.embedding = self.embedding_client.get_embedding_sync(chunk.content)

            # 4. Upsert updated chunks to vector store
            chunks_created = self.vector_store.upsert_chunks(all_new_chunks)

        logger.info(
            f"[{repo_id}] Incremental index complete: "
            f"{len(modified_files)} modified files, {chunks_created} new chunks embedded, {chunks_deleted} obsolete chunks removed."
        )

        return {
            "repo_id": repo_id,
            "modified_files": modified_files,
            "deleted_files": deleted_files,
            "chunks_embedded": chunks_created,
            "chunks_deleted": chunks_deleted,
        }
