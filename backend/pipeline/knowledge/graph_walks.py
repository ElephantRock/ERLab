"""Multi-hop graph traversal for retrieval context expansion."""

from __future__ import annotations

import logging
from collections import deque
from typing import TYPE_CHECKING

from pydantic import BaseModel

from backend.pipeline.knowledge.relationships import RelationType

if TYPE_CHECKING:
    from backend.pipeline.knowledge.entities import KnowledgeEntity
    from backend.pipeline.knowledge.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class GraphWalkResult(BaseModel):
    entity_id: str
    distance: int
    path: list[str]
    score: float


class GraphWalker:
    """Multi-hop graph traversal using existing KG adjacency structure."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self._kg = kg

    def walk_bfs(
        self,
        seed_entity_ids: list[str],
        max_hops: int = 2,
        max_results: int = 50,
        relation_filter: list[RelationType] | None = None,
    ) -> list[GraphWalkResult]:
        visited: dict[str, tuple[int, list[str], float]] = {}

        queue: deque[tuple[str, int, list[str], float]] = deque()
        for sid in seed_entity_ids:
            entity = self._kg.get_entity(sid)
            if entity:
                seed_score = entity.truth.expectation if entity.truth else 0.5
                queue.append((sid, 0, [sid], seed_score))
                visited[sid] = (0, [sid], seed_score)

        while queue:
            current_id, hops, path, accumulated_score = queue.popleft()

            if hops >= max_hops:
                continue

            neighbor_entities = self._kg.get_neighbors(current_id)
            if not neighbor_entities:
                continue

            relationships = self._kg._relationships
            for nbr_entity in neighbor_entities:
                nbr_id = nbr_entity.id
                if nbr_id in visited:
                    continue

                edge_weight = 1.0
                if relation_filter is not None:
                    matching = [
                        r for r in relationships
                        if (r.source_id == current_id and r.target_id == nbr_id)
                        or (r.source_id == nbr_id and r.target_id == current_id)
                        if r.relation_type in relation_filter
                    ]
                    if not matching:
                        continue
                    edge_weight = max(r.weight for r in matching)
                else:
                    matching = [
                        r for r in relationships
                        if (r.source_id == current_id and r.target_id == nbr_id)
                        or (r.source_id == nbr_id and r.target_id == current_id)
                    ]
                    if matching:
                        edge_weight = max(r.weight for r in matching)

                nbr_entity = self._kg.get_entity(nbr_id)
                nbr_truth = nbr_entity.truth.expectation if nbr_entity and nbr_entity.truth else 0.5

                decay = 0.7 ** (hops + 1)
                new_score = accumulated_score * edge_weight * nbr_truth * decay

                new_path = path + [nbr_id]
                visited[nbr_id] = (hops + 1, new_path, new_score)

                if hops + 1 < max_hops:
                    queue.append((nbr_id, hops + 1, new_path, new_score))

        results = [
            GraphWalkResult(entity_id=eid, distance=d, path=p, score=s)
            for eid, (d, p, s) in visited.items()
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def walk_weighted(
        self,
        seed_entity_ids: list[str],
        max_hops: int = 2,
        max_results: int = 50,
    ) -> list[GraphWalkResult]:
        visited: dict[str, tuple[int, list[str], float]] = {}
        queue: deque[tuple[str, int, list[str], float]] = deque()

        for sid in seed_entity_ids:
            entity = self._kg.get_entity(sid)
            if entity:
                seed_score = entity.truth.expectation if entity.truth else 0.5
                queue.append((sid, 0, [sid], seed_score))
                visited[sid] = (0, [sid], seed_score)

        while queue:
            current_id, hops, path, accumulated_score = queue.popleft()
            if hops >= max_hops:
                continue

            neighbor_entities = self._kg.get_neighbors(current_id)
            if not neighbor_entities:
                continue

            weighted_neighbors: list[tuple[str, float]] = []
            for nbr_entity in neighbor_entities:
                nbr_id = nbr_entity.id
                if nbr_id in visited:
                    continue
                matching = [
                    r for r in self._kg._relationships
                    if (r.source_id == current_id and r.target_id == nbr_id)
                    or (r.source_id == nbr_id and r.target_id == current_id)
                ]
                weight = max((r.weight for r in matching), default=1.0)
                weighted_neighbors.append((nbr_id, weight))

            total_weight = sum(w for _, w in weighted_neighbors)
            if total_weight == 0:
                continue

            for nbr_id, weight in weighted_neighbors:
                transition_prob = weight / total_weight
                nbr_entity = self._kg.get_entity(nbr_id)
                nbr_truth = nbr_entity.truth.expectation if nbr_entity and nbr_entity.truth else 0.5

                new_score = accumulated_score * transition_prob * nbr_truth
                new_path = path + [nbr_id]
                visited[nbr_id] = (hops + 1, new_path, new_score)

                if hops + 1 < max_hops:
                    queue.append((nbr_id, hops + 1, new_path, new_score))

        results = [
            GraphWalkResult(entity_id=eid, distance=d, path=p, score=s)
            for eid, (d, p, s) in visited.items()
        ]
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    def extract_subgraph(
        self, entity_ids: list[str], max_hops: int = 1
    ) -> dict:
        result_entities: dict[str, KnowledgeEntity] = {}
        result_relationships: list[dict] = []

        for eid in entity_ids:
            entity = self._kg.get_entity(eid)
            if entity:
                result_entities[eid] = entity

        if max_hops >= 1:
            for eid in list(result_entities.keys()):
                neighbor_entities = self._kg.get_neighbors(eid)
                for nbr_entity in neighbor_entities:
                    nbr_id = nbr_entity.id
                    if nbr_id not in result_entities:
                        nbr = self._kg.get_entity(nbr_id)
                        if nbr:
                            result_entities[nbr_id] = nbr

        known_ids = set(result_entities.keys())
        for rel in self._kg._relationships:
            if rel.source_id in known_ids and rel.target_id in known_ids:
                result_relationships.append({
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "type": rel.relation_type.value,
                    "weight": rel.weight,
                })

        return {
            "entities": {eid: e.model_dump() for eid, e in result_entities.items()},
            "relationships": result_relationships,
        }
