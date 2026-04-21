"""Embedding generation service.

Wraps an EmbeddingProvider with batching, error handling, and zero-vector
fallback. Accepts either the new EmbeddingProvider or the legacy LLMProvider
for backward compatibility.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.embedding_providers import EmbeddingProvider

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings using a pluggable provider."""

    def __init__(
        self,
        provider: EmbeddingProvider | LLMProvider,
        batch_size: int = 100,
        expected_dimension: int | None = None,
    ):
        self._provider = provider
        self._batch_size = batch_size
        if expected_dimension is not None:
            self.validate_dimension(expected_dimension)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching for efficiency."""
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            try:
                embeddings = await self._provider.embed(batch)
                all_embeddings.extend(embeddings)
            except Exception as e:
                logger.error("Embedding batch %d failed: %s", i // self._batch_size, e)
                dim = self.dimension
                all_embeddings.extend([[0.0] * dim for _ in batch])

        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = await self.embed_texts([text])
        dim = self.dimension
        return results[0] if results else [0.0] * dim

    @property
    def dimension(self) -> int:
        """Return embedding dimension from provider, or default 1536."""
        if hasattr(self._provider, "dimension"):
            return self._provider.dimension
        return 1536

    def validate_dimension(self, expected: int) -> bool:
        """Warn if embedding dimension doesn't match expected. Returns True if match."""
        actual = self.dimension
        if actual != expected:
            logger.warning(
                "Embedding dimension mismatch: provider=%d, expected=%d. "
                "Existing vectors may be incompatible.",
                actual, expected,
            )
            return False
        return True
