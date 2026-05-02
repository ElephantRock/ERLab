"""Embedding-based novelty scoring for research ideas.

Uses GraphEmbeddingIndex to compute distance-based novelty scores
between generated ideas and existing KG entities. Provides min/avg
distance metrics and identifies the closest prior work.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.pipeline.knowledge.embedding_providers import EmbeddingService
    from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex

logger = logging.getLogger(__name__)


class EmbeddingNoveltyResult(BaseModel):
    """Result of embedding-based novelty scoring."""

    idea_id: str = ""
    min_embedding_distance: float = 1.0
    avg_embedding_distance: float = 1.0
    closest_paper_id: str = ""
    distance_distribution: dict[str, float] = Field(default_factory=dict)


class EmbeddingNoveltyScorer:
    """Score idea novelty using embedding distances in the KG."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        graph_index: GraphEmbeddingIndex,
    ) -> None:
        self._embedding = embedding_service
        self._graph_index = graph_index

    async def score_novelty(
        self,
        idea: Any,
        cited_paper_ids: list[str] | None = None,
        top_k: int = 20,
    ) -> EmbeddingNoveltyResult:
        """Score novelty by computing embedding distance to KG entities."""
        idea_text = f"{getattr(idea, 'title', '')} {getattr(idea, 'proposed_method', '')}"
        idea_id = getattr(idea, 'id', getattr(idea, 'title', 'unknown'))[:60]

        try:
            results = await self._graph_index.query_similar(
                query=idea_text,
                n_results=top_k,
            )
        except Exception as e:
            logger.warning("Embedding novelty query failed: %s", e)
            return EmbeddingNoveltyResult(idea_id=idea_id)

        if not results:
            return EmbeddingNoveltyResult(
                idea_id=idea_id,
                min_embedding_distance=1.0,
                avg_embedding_distance=1.0,
            )

        # Filter out cited papers if provided
        if cited_paper_ids:
            results = [
                r for r in results
                if r.get("id", "") not in cited_paper_ids
            ]

        if not results:
            return EmbeddingNoveltyResult(
                idea_id=idea_id,
                min_embedding_distance=1.0,
                avg_embedding_distance=1.0,
            )

        distances = [r.get("distance", 1.0) for r in results]
        min_dist = min(distances)
        avg_dist = sum(distances) / len(distances)

        # Distance distribution: quartile breakdown
        sorted_dists = sorted(distances)
        n = len(sorted_dists)
        distribution = {
            "p25": sorted_dists[n // 4] if n >= 4 else sorted_dists[0],
            "p50": sorted_dists[n // 2],
            "p75": sorted_dists[3 * n // 4] if n >= 4 else sorted_dists[-1],
            "max": sorted_dists[-1],
        }

        # Find closest paper
        closest = min(results, key=lambda r: r.get("distance", 1.0))

        return EmbeddingNoveltyResult(
            idea_id=idea_id,
            min_embedding_distance=min_dist,
            avg_embedding_distance=avg_dist,
            closest_paper_id=closest.get("id", ""),
            distance_distribution=distribution,
        )
