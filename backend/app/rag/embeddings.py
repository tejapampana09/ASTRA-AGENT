from __future__ import annotations

from typing import List
import litellm

from app.config import settings
from app.observability.logging import logger


class EmbeddingClient:
    """Generates dense vector embeddings for code chunks."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model = model_name

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            resp = await litellm.aembedding(
                model=self.model,
                input=texts,
                api_key=settings.LLM_API_KEY
            )
            return [item["embedding"] for item in resp.data]
        except Exception as e:
            logger.debug(f"Embedding generation fallback (dummy/offline): {e}")
            # Offline dummy 64-dim vector for testing
            return [[0.0] * 64 for _ in texts]
