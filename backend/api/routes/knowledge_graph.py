"""Knowledge graph API routes — interactive graph visualization endpoints."""

from __future__ import annotations

from collections import deque
from typing import Optional

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError
from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType

router = APIRouter()

# ── Graph singleton (lazy-initialised) ────────────────────────────

_graph: KnowledgeGraph | None = None


def _get_graph() -> KnowledgeGraph:
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph


# ── Helpers ────────────────────────────────────────────────────────


def _serialize_entity(entity: KnowledgeEntity) -> dict:
    """Serialize a KnowledgeEntity to a JSON-safe dict."""
    return {
        "id": entity.id,
        "entity_type": entity.entity_type.value,
        "name": entity.name,
        "aliases": entity.aliases,
        "properties": entity.properties,
        "truth": {
            "confidence": entity.truth.confidence,
            "frequency": entity.truth.frequency,
            "source_count": entity.truth.evidence_count,
        },
    }


def _serialize_relationship(rel: KnowledgeRelationship) -> dict:
    """Serialize a KnowledgeRelationship to a JSON-safe dict."""
    return {
        "source_id": rel.source_id,
        "target_id": rel.target_id,
        "relation_type": rel.relation_type.value,
        "weight": rel.weight,
        "evidence": rel.evidence,
        "truth": {
            "confidence": rel.truth.confidence,
            "frequency": rel.truth.frequency,
            "source_count": rel.truth.evidence_count,
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────


@router.get(
    "/world-model",
    summary="World model summary",
    description="Returns a high-level world model summary with top entities, strongest relationships, and type distribution.",
)
async def world_model():
    """GET /api/v1/knowledge-graph/world-model → world model summary."""
    graph = _get_graph()

    entities = list(graph._entities.values())
    relationships = list(graph._relationships)

    # Top entities by truth confidence
    top_entities = sorted(
        entities, key=lambda e: e.truth.confidence, reverse=True
    )[:10]

    # Strongest relationships by weight
    strongest_rels = sorted(
        relationships, key=lambda r: r.weight, reverse=True
    )[:10]

    # Entity type distribution
    type_dist: dict[str, int] = {}
    for e in entities:
        type_dist[e.entity_type.value] = type_dist.get(e.entity_type.value, 0) + 1

    # Relation type distribution
    rel_dist: dict[str, int] = {}
    for r in relationships:
        rel_dist[r.relation_type.value] = rel_dist.get(r.relation_type.value, 0) + 1

    return {
        "total_entities": len(entities),
        "total_relationships": len(relationships),
        "entity_type_distribution": type_dist,
        "relationship_type_distribution": rel_dist,
        "top_entities": [_serialize_entity(e) for e in top_entities],
        "strongest_relationships": [_serialize_relationship(r) for r in strongest_rels],
    }


@router.get(
    "/stats",
    summary="Knowledge graph statistics",
    description="Returns entity count, relationship count, and breakdowns by type.",
)
async def graph_stats():
    """GET /api/v1/knowledge-graph/stats → graph statistics."""
    graph = _get_graph()
    return graph.get_graph_stats()


@router.get(
    "/entities",
    summary="List knowledge graph entities",
    description="Returns up to 100 entities with optional type and search filters (HB-02).",
)
async def list_entities(
    type: Optional[str] = Query(None, description="Filter by entity type"),
    search: Optional[str] = Query(None, description="Search entity names/aliases"),
    limit: int = Query(100, ge=1, le=100, description="Max entities to return (HB-02: capped at 100)"),
):
    """GET /api/v1/knowledge-graph/entities → entity list."""
    graph = _get_graph()

    entities = list(graph._entities.values())

    # Filter by type
    if type:
        try:
            etype = EntityType(type)
        except ValueError:
            return []
        entities = [e for e in entities if e.entity_type == etype]

    # Filter by search term
    if search:
        term = search.lower()
        entities = [
            e
            for e in entities
            if term in e.name.lower()
            or any(term in a.lower() for a in e.aliases)
        ]

    # HB-02: Hard limit at 100
    entities = entities[:limit]

    return [_serialize_entity(e) for e in entities]


@router.get(
    "/entity/{entity_id}",
    summary="Get entity with relationships",
    description="Returns a single entity with all its incoming and outgoing relationships.",
)
async def get_entity(entity_id: str):
    """GET /api/v1/knowledge-graph/entity/{id} → entity + relationships."""
    graph = _get_graph()
    entity = graph.get_entity(entity_id)

    if entity is None:
        raise NotFoundError(
            f"Entity '{entity_id}' not found",
            hint="Check the entity ID or use /entities to browse available entities.",
        )

    relationships = graph.get_referencing_relationships(entity_id)

    return {
        "entity": _serialize_entity(entity),
        "relationships": [_serialize_relationship(r) for r in relationships],
    }


@router.get(
    "/subgraph/{entity_id}",
    summary="Get connected subgraph",
    description="Returns entities and relationships within N hops of the given entity.",
)
async def get_subgraph(
    entity_id: str,
    depth: int = Query(2, ge=1, le=5, description="Traversal depth"),
):
    """GET /api/v1/knowledge-graph/subgraph/{id} → connected subgraph."""
    graph = _get_graph()
    root = graph.get_entity(entity_id)

    if root is None:
        raise NotFoundError(
            f"Entity '{entity_id}' not found",
            hint="Check the entity ID or use /entities to browse available entities.",
        )

    # BFS traversal
    visited_entities: dict[str, KnowledgeEntity] = {root.id: root}
    visited_rels: list[KnowledgeRelationship] = []
    queue: deque[tuple[str, int]] = deque([(entity_id, 0)])

    while queue:
        current_id, current_depth = queue.popleft()
        if current_depth >= depth:
            continue

        neighbors = graph.get_neighbors(current_id)
        rels = graph.get_referencing_relationships(current_id)

        for rel in rels:
            visited_rels.append(rel)

        for neighbor in neighbors:
            if neighbor.id not in visited_entities:
                visited_entities[neighbor.id] = neighbor
                queue.append((neighbor.id, current_depth + 1))

    # Deduplicate relationships
    seen_rel_keys: set[str] = set()
    unique_rels: list[KnowledgeRelationship] = []
    for rel in visited_rels:
        key = f"{rel.source_id}:{rel.target_id}:{rel.relation_type.value}"
        if key not in seen_rel_keys:
            seen_rel_keys.add(key)
            unique_rels.append(rel)

    return {
        "entities": [_serialize_entity(e) for e in visited_entities.values()],
        "relationships": [_serialize_relationship(r) for r in unique_rels],
    }
