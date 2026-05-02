"""Adaptive retrieval with quality-aware re-querying.

Wraps TwoStageRetriever with automatic query reformulation when
result quality is below a configurable threshold. Uses the existing
QueryTransformer for reformulation and RRF for result merging.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.knowledge.retrieval_quality import RetrievalQualityScorer
from backend.pipeline.knowledge.retriever import RetrievalResult, TwoStageRetriever

logger = logging.getLogger(__name__)


class AdaptiveRetriever:
    """Wraps TwoStageRetriever with quality-aware re-querying.

    1. Retrieve with initial query
    2. Score result quality
    3. If quality < threshold, reformulate query using QueryTransformer
    4. Retry with reformulated query
    5. Merge results via RRF-style score averaging
    """

    def __init__(
        self,
        retriever: TwoStageRetriever,
        quality_scorer: RetrievalQualityScorer,
        query_transformer: Any = None,
        min_quality: float = 0.4,
        max_retries: int = 2,
    ) -> None:
        self._retriever = retriever
        self._quality_scorer = quality_scorer
        self._query_transformer = query_transformer
        self._min_quality = min_quality
        self._max_retries = max(0, max_retries)

    async def retrieve(
        self,
        query: str,
        n_results: int = 10,
    ) -> list[RetrievalResult]:
        """Retrieve with adaptive re-querying based on quality assessment.

        Args:
            query: Initial search query.
            n_results: Number of results to return.

        Returns:
            Quality-scored retrieval results, possibly from merged queries.
        """
        # Initial retrieval
        results = await self._retriever.retrieve(query, n_results=n_results * 2)

        # Score quality
        scored = self._quality_scorer.score(results, query)
        quality = self._quality_scorer.aggregate_quality(scored)

        if quality >= self._min_quality or self._max_retries == 0:
            return scored[:n_results]

        logger.info(
            "Retrieval quality %.3f below threshold %.3f, attempting re-query",
            quality,
            self._min_quality,
        )

        # Re-query with reformulated queries
        all_results = list(scored)
        for attempt in range(self._max_retries):
            reformulated = await self._reformulate(query, attempt)
            if not reformulated or reformulated == query:
                break

            retry_results = await self._retriever.retrieve(
                reformulated, n_results=n_results
            )
            retry_scored = self._quality_scorer.score(retry_results, reformulated)

            # Merge: combine via score averaging for shared docs
            all_results = self._merge_results(all_results, retry_scored)

            new_quality = self._quality_scorer.aggregate_quality(all_results)
            if new_quality >= self._min_quality:
                logger.info(
                    "Re-query %d improved quality to %.3f", attempt + 1, new_quality
                )
                break

        # Final sort by quality score
        all_results.sort(
            key=lambda r: r.metadata.get("_quality_score", 0.0), reverse=True
        )
        return all_results[:n_results]

    async def _reformulate(self, original_query: str, attempt: int) -> str:
        """Generate a reformulated query using QueryTransformer."""
        if not self._query_transformer:
            # Simple reformulation: add domain-specific terms
            suffixes = [
                "survey recent advances",
                "systematic review methods",
                "benchmark evaluation techniques",
            ]
            suffix = suffixes[attempt % len(suffixes)]
            return f"{original_query} {suffix}"

        try:
            variants = await self._query_transformer.transform(original_query)
            # Pick a different variant than the original
            for v in variants:
                if v.lower() != original_query.lower():
                    return v
            return variants[0] if variants else original_query
        except Exception as e:
            logger.warning("Query reformulation failed: %s", e)
            return original_query

    @staticmethod
    def _merge_results(
        existing: list[RetrievalResult],
        new_results: list[RetrievalResult],
    ) -> list[RetrievalResult]:
        """Merge two result sets, averaging scores for shared documents."""
        by_id: dict[str, RetrievalResult] = {}

        for r in existing:
            by_id[r.id] = r

        for r in new_results:
            if r.id in by_id:
                existing_r = by_id[r.id]
                avg_quality = (
                    existing_r.metadata.get("_quality_score", 0.0)
                    + r.metadata.get("_quality_score", 0.0)
                ) / 2
                merged_meta = {**existing_r.metadata, "_quality_score": round(avg_quality, 4)}
                by_id[r.id] = RetrievalResult(
                    id=r.id,
                    text=r.text,
                    score=(existing_r.score + r.score) / 2,
                    metadata=merged_meta,
                    source=r.source,
                )
            else:
                by_id[r.id] = r

        return list(by_id.values())
