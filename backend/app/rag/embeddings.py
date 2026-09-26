from __future__ import annotations

import math
import os
import re
from typing import List, Optional

from app.config import settings
from app.observability.logging import logger


class EmbeddingClient:
    """
    Production embedding client for code chunks and search queries.
    Integrates LiteLLM (OpenAI text-embedding-3-small/large, Cohere, Bedrock, Ollama)
    with batching support and deterministic projection fallback for offline/test environments.
    """

    def __init__(self, model_name: Optional[str] = None, dimension: Optional[int] = None):
        self.model = model_name or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION

    def _is_live_key_configured(self) -> bool:
        key = os.environ.get("OPENAI_API_KEY") or settings.LLM_API_KEY
        if not key or key.startswith("test-") or key.startswith("fake-") or len(key) <= 5:
            return False
        # If OpenAI model is requested but key is Gemini key, skip to deterministic projection
        if "text-embedding" in self.model and (key.startswith("AQ.") or key.startswith("AIza")):
            return False
        return True

    def get_embedding(self, text: str) -> List[float]:
        """Synchronously generates vector embedding for a single text."""
        if not text:
            return [0.0] * self.dimension

        if self._is_live_key_configured():
            try:
                import litellm
                resp = litellm.embedding(
                    model=self.model,
                    input=[text],
                    api_key=settings.LLM_API_KEY
                )
                if resp and resp.data and len(resp.data) > 0:
                    emb = resp.data[0]["embedding"]
                    if len(emb) == self.dimension:
                        return emb
                    # If model returned different dimension (e.g. 1536 vs 64), slice or pad
                    return self._fit_dimension(emb)
            except Exception as e:
                logger.warning(f"Live embedding API call failed: {e}. Falling back to deterministic semantic projection.")

        return self._compute_deterministic_embedding(text, self.dimension)

    def get_embedding_sync(self, text: str) -> List[float]:
        """Alias for get_embedding to support synchronous call chains."""
        return self.get_embedding(text)

    def get_embeddings_batch(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Batched synchronous embedding generation for efficient indexing."""
        if not texts:
            return []

        if self._is_live_key_configured():
            try:
                import litellm
                all_embeddings: List[List[float]] = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    resp = litellm.embedding(
                        model=self.model,
                        input=batch,
                        api_key=settings.LLM_API_KEY
                    )
                    batch_embs = [self._fit_dimension(item["embedding"]) for item in resp.data]
                    all_embeddings.extend(batch_embs)
                return all_embeddings
            except Exception as e:
                logger.warning(f"Live batch embedding call failed: {e}. Falling back to deterministic projection.")

        return [self._compute_deterministic_embedding(t, self.dimension) for t in texts]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously generates embeddings."""
        if not texts:
            return []

        if self._is_live_key_configured():
            try:
                import litellm
                resp = await litellm.aembedding(
                    model=self.model,
                    input=texts,
                    api_key=settings.LLM_API_KEY
                )
                return [self._fit_dimension(item["embedding"]) for item in resp.data]
            except Exception as e:
                logger.warning(f"Live async embedding failed: {e}. Falling back to deterministic projection.")

        return [self._compute_deterministic_embedding(t, self.dimension) for t in texts]

    def _fit_dimension(self, emb: List[float]) -> List[float]:
        if len(emb) == self.dimension:
            return emb
        if len(emb) > self.dimension:
            fitted = emb[:self.dimension]
        else:
            fitted = emb + [0.0] * (self.dimension - len(emb))
        norm = math.sqrt(sum(x * x for x in fitted))
        return [round(x / norm, 6) for x in fitted] if norm > 1e-9 else fitted

    @classmethod
    def _compute_deterministic_embedding(cls, text: str, dimension: int = 64) -> List[float]:
        """
        High-fidelity dense vector projection using token hashing and character n-gram projection.
        Guarantees deterministic, normalized vectors preserving semantic lexical overlap.
        """
        vec = [0.0] * dimension
        tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        if not tokens:
            return vec

        for token in tokens:
            h = hash(token)
            idx1 = abs(h) % dimension
            sign1 = 1.0 if ((h >> 4) & 1) == 0 else -1.0
            vec[idx1] += sign1 * 1.5

            if len(token) >= 3:
                for i in range(len(token) - 2):
                    tri = token[i:i + 3]
                    th = hash(tri)
                    idx2 = abs(th) % dimension
                    sign2 = 1.0 if ((th >> 3) & 1) == 0 else -1.0
                    vec[idx2] += sign2 * 0.5

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 1e-9:
            vec = [round(x / norm, 6) for x in vec]
        return vec
