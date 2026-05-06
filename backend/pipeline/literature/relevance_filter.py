"""Relevance filter: removes off-topic papers before gap analysis.

Scores each paper by cosine similarity of its embedding against the
domain query embedding. Papers below threshold are filtered out,
with a guaranteed minimum count (HB-01).
"""
from __future__ import annotations

import logging
import math
from typing import Protocol

from backend.pipeline.literature.models import Paper, SearchResult

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.3
MIN_PAPERS = 5


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""
    async def embed(self, text: str) -> list[float]: ...


class RelevanceFilter:
    """Filter papers by relevance to the research domain.

    Uses embedding cosine similarity to score each paper's title+abstract
    against the original domain query.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        min_papers: int = MIN_PAPERS,
    ) -> None:
        self._provider = embedding_provider
        self._threshold = threshold
        self._min_papers = min_papers

    async def filter(
        self,
        papers: list[SearchResult],
        domain_query: str,
    ) -> list[SearchResult]:
        """Filter papers by relevance to domain_query.

        Args:
            papers: Raw search results to filter.
            domain_query: The original research domain/query.

        Returns:
            Filtered list of SearchResult with updated relevance_score.
        """
        if not papers:
            return []

        if self._provider is None:
            logger.debug("No embedding provider — skipping relevance filter")
            return papers

        try:
            # Get domain embedding
            domain_embedding = await self._provider.embed(domain_query)

            # Score each paper
            scored = []
            for result in papers:
                text = f"{result.paper.title} {result.paper.abstract or ''}"
                try:
                    paper_embedding = await self._provider.embed(text)
                    score = _cosine_similarity(domain_embedding, paper_embedding)
                    # Update relevance score
                    result.relevance_score = score
                    scored.append((result, score))
                except Exception as e:
                    logger.warning("Embedding failed for '%s': %s", result.paper.title[:50], e)
                    scored.append((result, result.relevance_score or 0.0))

            # Sort by score descending
            scored.sort(key=lambda x: x[1], reverse=True)

            # Apply threshold but guarantee minimum (HB-01)
            filtered = [r for r, s in scored if s >= self._threshold]
            if len(filtered) < self._min_papers and len(scored) >= self._min_papers:
                filtered = [r for r, _ in scored[:self._min_papers]]

            logger.info(
                "Relevance filter: %d → %d papers (threshold=%.2f)",
                len(papers), len(filtered), self._threshold,
            )
            return filtered

        except Exception as e:
            logger.warning("Relevance filter failed: %s — returning originals (HB-02)", e)
            return papers


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
