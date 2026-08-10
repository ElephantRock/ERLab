"""Multi-criteria retrieval quality scoring.

Scores retrieval results on relevance, recency, authority, and diversity.
Produces a composite quality score (0-1) for individual results and for
an entire result set.
"""

from __future__ import annotations

import logging

from backend.pipeline.knowledge.retriever import RetrievalResult

logger = logging.getLogger(__name__)


class RetrievalQualityScorer:
    """Scores retrieval results on multiple criteria.

    Criteria: relevance (from RRF score), recency (year),
    authority (citation_count), diversity (embedding distance).
    Returns a composite quality score 0-1.
    """

    def __init__(
        self,
        relevance_weight: float = 0.5,
        recency_weight: float = 0.2,
        authority_weight: float = 0.2,
        diversity_weight: float = 0.1,
    ) -> None:
        total = relevance_weight + recency_weight + authority_weight + diversity_weight
        self._rel_w = relevance_weight / total
        self._rec_w = recency_weight / total
        self._auth_w = authority_weight / total
        self._div_w = diversity_weight / total

    def score(
        self, results: list[RetrievalResult], query: str = ""
    ) -> list[RetrievalResult]:
        """Add quality scores to retrieval results via metadata.

        Each result gets a `_quality_score` in its metadata dict.
        Results are NOT re-sorted — caller decides whether to re-sort.
        """
        if not results:
            return results

        max_rrf = max(r.score for r in results) or 1.0
        scored_results = []

        for i, result in enumerate(results):
            relevance = min(1.0, result.score / max_rrf) if max_rrf > 0 else 0.0
            recency = self._recency_score(result.metadata)
            authority = self._authority_score(result.metadata)
            diversity = self._diversity_score(results, i)

            quality = (
                relevance * self._rel_w
                + recency * self._rec_w
                + authority * self._auth_w
                + diversity * self._div_w
            )

            metadata = {**result.metadata, "_quality_score": round(quality, 4)}
            scored_results.append(
                RetrievalResult(
                    id=result.id,
                    text=result.text,
                    score=result.score,
                    metadata=metadata,
                    source=result.source,
                )
            )

        return scored_results

    def aggregate_quality(self, results: list[RetrievalResult]) -> float:
        """Compute aggregate quality for a result set (0-1).

        Returns the mean quality score across all results that have
        been scored (have _quality_score in metadata).
        """
        scores = [
            r.metadata.get("_quality_score", 0.0)
            for r in results
            if "_quality_score" in r.metadata
        ]
        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    @staticmethod
    def _recency_score(metadata: dict) -> float:
        """Score based on publication year (0-1). Recent = higher."""
        year = metadata.get("year")
        if year is None:
            return 0.5
        try:
            year = int(year)
        except (TypeError, ValueError):
            return 0.5
        # Scale: 2020+ = 1.0, 2015 = 0.7, 2010 = 0.4, older = lower
        if year >= 2024:
            return 1.0
        if year >= 2020:
            return 0.7 + 0.3 * (year - 2020) / 4
        if year >= 2015:
            return 0.4 + 0.3 * (year - 2015) / 5
        return max(0.1, 0.4 * (year - 2000) / 15) if year >= 2000 else 0.1

    @staticmethod
    def _authority_score(metadata: dict) -> float:
        """Score based on citation count (0-1). More cited = higher."""
        citations = metadata.get("citation_count", 0)
        try:
            citations = int(citations)
        except (TypeError, ValueError):
            return 0.3
        # Logarithmic scale: 0=0.1, 10=0.3, 100=0.6, 1000+=1.0
        if citations <= 0:
            return 0.1
        import math
        return min(1.0, 0.1 + 0.3 * math.log10(max(1, citations)))

    @staticmethod
    def _diversity_score(results: list[RetrievalResult], idx: int) -> float:
        """Score based on position diversity ( discourage clustered results)."""
        # Simple heuristic: spread results across the list get higher diversity
        n = len(results)
        if n <= 1:
            return 1.0
        # Results in different positions are considered diverse
        # This is a proxy — true diversity would use embeddings
        return round(1.0 - abs(idx / n - 0.5) * 0.4, 3)
