"""Embedding-based deduplication — cosine similarity via EmbeddingProvider.

This module uses the dedicated ``EmbeddingProvider`` protocol from
``backend.pipeline.knowledge.embedding_providers`` — never an
``LLMProvider``. Chat providers cannot produce embeddings.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.pipeline.memory.models import MemoryEntry

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_providers import EmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingSimilarity:
    """Computes cosine similarity between memory entries via embeddings."""

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self._cache: dict[str, list[float]] = {}

    async def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Cosine similarity between two texts."""
        emb_a = await self._get_embedding(text_a)
        emb_b = await self._get_embedding(text_b)
        return _cosine_similarity(emb_a, emb_b)

    async def find_duplicates(
        self,
        entries: list[MemoryEntry],
        threshold: float = 0.9,
    ) -> list[tuple[str, str, float]]:
        """Find pairs of entries with similarity above threshold."""
        if len(entries) < 2:
            return []

        # Batch embed all entries
        await self._batch_embed(entries)

        pairs: list[tuple[str, str, float]] = []
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                emb_a = self._cache.get(entries[i].id, [])
                emb_b = self._cache.get(entries[j].id, [])
                if not emb_a or not emb_b:
                    continue
                sim = _cosine_similarity(emb_a, emb_b)
                if sim >= threshold:
                    pairs.append((entries[i].id, entries[j].id, round(sim, 4)))

        return pairs

    async def _batch_embed(self, entries: list[MemoryEntry]) -> None:
        """Embed all entries, caching results."""
        to_embed = [e for e in entries if e.id not in self._cache]
        if not to_embed:
            return

        texts = [e.content[:500] for e in to_embed]
        try:
            embeddings = await self._provider.embed(texts)
            for entry, emb in zip(to_embed, embeddings):
                self._cache[entry.id] = emb
        except Exception as e:
            logger.warning("Batch embedding failed: %s", e)

    async def _get_embedding(self, text: str) -> list[float]:
        embeds = await self._provider.embed([text[:500]])
        return embeds[0] if embeds else []


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
