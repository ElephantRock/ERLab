"""Citation graph traversal for prior art discovery.

Walks the Knowledge Graph's CITES/EXTENDS/BUILDS_ON relations to find
related prior art for generated ideas. Classifies relationships as
exact, partial, or related based on textual similarity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.relationships import RelationType

if TYPE_CHECKING:
    from backend.pipeline.knowledge.graph import KnowledgeGraph
    from backend.pipeline.knowledge.graph_walks import GraphWalker

logger = logging.getLogger(__name__)

_CITATION_RELATIONS = {
    RelationType.CITES,
    RelationType.EXTENDS,
    RelationType.BUILDS_ON,
}


class PriorArtResult(BaseModel):
    """Prior art discovered through citation traversal."""

    idea_id: str = ""
    prior_art_ids: list[str] = Field(default_factory=list)
    citation_depth: int = 0
    similarity_score: float = 0.0
    relationship_type: str = "related"  # "exact" | "partial" | "related"


class CitationGraphTraverser:
    """Traverse the citation graph to find prior art for novelty assessment."""

    def __init__(
        self,
        kg: KnowledgeGraph,
        walker: GraphWalker | None = None,
    ) -> None:
        self._kg = kg
        self._walker = walker

    def find_prior_art(
        self,
        idea_entity_id: str,
        max_hops: int = 3,
    ) -> list[PriorArtResult]:
        """Walk the citation graph from an idea to find related prior art."""
        entity = self._kg.get_entity(idea_entity_id)
        if not entity:
            return []

        results: list[PriorArtResult] = []

        if self._walker:
            walk_results = self._walker.walk_bfs(
                seed_entity_ids=[idea_entity_id],
                max_hops=max_hops,
                max_results=30,
                relation_filter=list(_CITATION_RELATIONS),
            )
            for wr in walk_results:
                if wr.entity_id == idea_entity_id:
                    continue
                rel_type = self._classify_by_depth(wr.hops)
                results.append(PriorArtResult(
                    idea_id=idea_entity_id,
                    prior_art_ids=[wr.entity_id],
                    citation_depth=wr.hops,
                    similarity_score=1.0 - (wr.hops * 0.2),
                    relationship_type=rel_type,
                ))
        else:
            # Fallback: manual BFS through relationships
            results = self._manual_bfs(idea_entity_id, max_hops)

        # Merge results by unique prior art ID
        seen: dict[str, PriorArtResult] = {}
        for r in results:
            for pid in r.prior_art_ids:
                if pid not in seen or r.citation_depth < seen[pid].citation_depth:
                    seen[pid] = r

        return list(seen.values())[:20]

    def classify_relationship(
        self, idea_text: str, prior_art_text: str,
    ) -> str:
        """Classify the relationship between an idea and prior art text."""
        idea_lower = idea_text.lower()
        art_lower = prior_art_text.lower()

        # Simple overlap-based classification
        idea_words = set(idea_lower.split())
        art_words = set(art_lower.split())
        overlap = len(idea_words & art_words)
        total = max(len(idea_words | art_words), 1)
        ratio = overlap / total

        if ratio > 0.6:
            return "exact"
        elif ratio > 0.3:
            return "partial"
        return "related"

    def _manual_bfs(
        self, start_id: str, max_hops: int,
    ) -> list[PriorArtResult]:
        """Fallback BFS when GraphWalker is not available."""
        from collections import deque

        results: list[PriorArtResult] = []
        visited: set[str] = {start_id}
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])

        while queue:
            current_id, hops = queue.popleft()
            if hops >= max_hops:
                continue

            # Find outgoing citation relationships
            for rel in getattr(self._kg, '_relationships', []):
                if rel.source_id == current_id and rel.relation_type in _CITATION_RELATIONS:
                    target_id = rel.target_id
                    if target_id in visited:
                        continue
                    visited.add(target_id)

                    rel_type = self._classify_by_depth(hops + 1)
                    results.append(PriorArtResult(
                        idea_id=start_id,
                        prior_art_ids=[target_id],
                        citation_depth=hops + 1,
                        similarity_score=1.0 - ((hops + 1) * 0.2),
                        relationship_type=rel_type,
                    ))
                    queue.append((target_id, hops + 1))

        return results

    @staticmethod
    def _classify_by_depth(hops: int) -> str:
        if hops <= 1:
            return "exact"
        elif hops == 2:
            return "partial"
        return "related"
