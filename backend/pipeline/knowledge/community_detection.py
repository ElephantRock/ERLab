"""Label propagation community detection over the KG adjacency structure."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from backend.pipeline.knowledge.entities import KnowledgeEntity
    from backend.pipeline.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class Community(BaseModel):
    id: str
    entity_ids: list[str]
    label: str = ""
    modularity_score: float = 0.0


class CommunityDetector:
    """Label propagation community detection over the KG adjacency structure."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self._kg = kg

    def detect_communities(self, resolution: float = 1.0) -> list[Community]:
        entities = list(self._kg._entities.values())
        if not entities:
            return []

        labels: dict[str, int] = {e.id: i for i, e in enumerate(entities)}
        entity_ids = [e.id for e in entities]

        for _ in range(20):
            changed = False
            for eid in entity_ids:
                neighbors = self._kg.get_neighbors(eid)
                if not neighbors:
                    continue

                neighbor_labels: dict[int, float] = {}
                for nbr_entity in neighbors:
                    nbr_id = nbr_entity.id
                    if nbr_id not in labels:
                        continue
                    lbl = labels[nbr_id]
                    matching = [
                        r for r in self._kg._relationships
                        if (r.source_id == eid and r.target_id == nbr_id)
                        or (r.source_id == nbr_id and r.target_id == eid)
                    ]
                    weight = max((r.weight for r in matching), default=1.0)
                    neighbor_labels[lbl] = neighbor_labels.get(lbl, 0.0) + weight

                if not neighbor_labels:
                    continue

                best_label = max(neighbor_labels, key=lambda l: neighbor_labels[l])
                if best_label != labels[eid]:
                    labels[eid] = best_label
                    changed = True

            if not changed:
                break

        groups: dict[int, list[str]] = {}
        for eid, lbl in labels.items():
            groups.setdefault(lbl, []).append(eid)

        total_edges = len(self._kg._relationships)
        communities: list[Community] = []
        for i, (lbl, members) in enumerate(groups.items()):
            member_set = set(members)
            internal = sum(
                1 for r in self._kg._relationships
                if r.source_id in member_set and r.target_id in member_set
            )
            modularity = internal / max(total_edges, 1) if total_edges > 0 else 0.0

            communities.append(Community(
                id=f"community_{i}",
                entity_ids=members,
                label=f"Community {i} ({len(members)} entities)",
                modularity_score=round(modularity, 4),
            ))

        return communities

    def get_entity_community(
        self, entity_id: str, communities: list[Community]
    ) -> Community | None:
        for community in communities:
            if entity_id in community.entity_ids:
                return community
        return None

    def get_community_entities(
        self, community_id: str, communities: list[Community]
    ) -> list[KnowledgeEntity]:
        for community in communities:
            if community.id == community_id:
                return [
                    self._kg.get_entity(eid)
                    for eid in community.entity_ids
                    if self._kg.get_entity(eid) is not None
                ]
        return []
