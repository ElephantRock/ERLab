"""Embedding generation service."""

import logging
from typing import Sequence

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

BATCH_SIZE = 100


class EmbeddingService:
    """Generate embeddings using the configured LLM provider."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching for efficiency."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            try:
                embeddings = await self._provider.embed(batch)
                all_embeddings.extend(embeddings)
            except Exception as e:
                logger.error("Embedding batch %d failed: %s", i // BATCH_SIZE, e)
                # Return zero vectors as fallback
                all_embeddings.extend([[0.0] * 1536 for _ in batch])

        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_texts([text])
        return results[0] if results else [0.0] * 1536
