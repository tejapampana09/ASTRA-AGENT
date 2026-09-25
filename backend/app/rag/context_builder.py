from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.memory.store import TaskEpisodicMemory, task_memory_store
from app.rag.indexer import ChunkType, IndexedCodeChunk, RepositorySemanticIndexer
from app.rag.retrieval import CodeFlowChain, SemanticRetriever
from app.rag.vector_store import get_vector_store
from app.repository.scanner import RepositoryScanner


class ContextBuilder:
    """
    Assembles synthesized repository intelligence, architectural call-chains,
    vector retrieval chunks, and multi-turn task memory into a cohesive context.
    """

    def __init__(self):
        self.retriever = SemanticRetriever()
        self.vector_store = get_vector_store()

    def build_context(
        self,
        repo_path: Path,
        repo_id: str,
        task_goal: str,
        candidate_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Builds complete multi-layer context for dynamic planning and autonomous coding.
        """
        # 1. High-level architecture scan
        scan_summary = RepositoryScanner.scan(repo_path).to_dict()

        # 2. Semantic retrieval and architectural call-chain resolution
        retrieval = self.retriever.retrieve(
            repo_id=repo_id,
            query=task_goal,
            top_k=5,
            include_flow_chain=True
        )

        # 3. Retrieve relevant past task memory
        relevant_memories = task_memory_store.retrieve_relevant_task_memories(
            repo_id=repo_id,
            current_goal=task_goal,
            candidate_files=candidate_files or [c.file_path for c in retrieval.chunks]
        )
        memory_prompt_section = task_memory_store.format_memory_for_agent_prompt(relevant_memories)

        # 4. Format architectural call chain
        chain_info = None
        if retrieval.flow_chain:
            chain_info = {
                "summary": retrieval.flow_chain.flow_summary,
                "route": retrieval.flow_chain.entrypoint_route.symbol if retrieval.flow_chain.entrypoint_route else None,
                "service": retrieval.flow_chain.service_function.symbol if retrieval.flow_chain.service_function else None,
                "model": retrieval.flow_chain.database_model.symbol if retrieval.flow_chain.database_model else None,
            }

        # 5. Build prompt-ready markdown representation
        context_prompt = self._format_prompt_context(
            scan=scan_summary,
            flow_chain=retrieval.flow_chain,
            chunks=retrieval.chunks,
            memory_section=memory_prompt_section,
            goal=task_goal
        )

        return {
            "architecture": scan_summary,
            "flow_chain": chain_info,
            "relevant_chunks": [c.to_dict() for c in retrieval.chunks],
            "past_memories": [m.to_dict() for m in relevant_memories],
            "context_prompt": context_prompt,
        }

    def _format_prompt_context(
        self,
        scan: Dict[str, Any],
        flow_chain: Optional[CodeFlowChain],
        chunks: List[IndexedCodeChunk],
        memory_section: str,
        goal: str
    ) -> str:
        lines = [
            "## Repository Architecture & Code Context",
            f"- **Backend Framework**: {scan.get('backend', 'Unknown')}",
            f"- **Test Framework**: {scan.get('test_framework', 'pytest')}",
            f"- **Key Languages**: {', '.join(scan.get('languages', []))}",
        ]

        if flow_chain and flow_chain.flow_summary:
            lines.append(f"\n### Identified Code Flow Chain\n`{flow_chain.flow_summary}`")
            if flow_chain.entrypoint_route:
                lines.append(f"- **API Route Handler**: `{flow_chain.entrypoint_route.symbol}` in `{flow_chain.entrypoint_route.file_path}:{flow_chain.entrypoint_route.start_line}`")
            if flow_chain.service_function:
                lines.append(f"- **Service Function**: `{flow_chain.service_function.symbol}()` in `{flow_chain.service_function.file_path}:{flow_chain.service_function.start_line}`")
            if flow_chain.database_model:
                lines.append(f"- **Database Model**: `{flow_chain.database_model.symbol}` in `{flow_chain.database_model.file_path}:{flow_chain.database_model.start_line}`")

        if chunks:
            lines.append("\n### Relevant Code Snippets")
            for c in chunks[:4]:
                lines.append(f"#### `{c.file_path}` ({c.symbol} - lines {c.start_line}-{c.end_line})")
                lines.append(f"```{c.language}\n{c.content[:400]}\n```")

        if memory_section and "No previous task history" not in memory_section:
            lines.append(f"\n{memory_section}")

        return "\n".join(lines)


# Global singleton context builder
context_builder = ContextBuilder()
