"""Tests for BATCH-25/TASK-01: Knowledge Graph API endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_entity(
    eid: str = "concept:test",
    name: str = "Test Concept",
    entity_type: EntityType = EntityType.CONCEPT,
) -> KnowledgeEntity:
    return KnowledgeEntity(
        id=eid,
        entity_type=entity_type,
        name=name,
        aliases=["Alias"],
        properties={},
        truth=TruthValue(frequency=0.9, confidence=0.8, evidence_count=3),
    )


def _make_relationship(source: str, target: str) -> KnowledgeRelationship:
    return KnowledgeRelationship(
        source_id=source,
        target_id=target,
        relation_type=RelationType.CITES,
        weight=1.0,
        evidence=[],
        truth=TruthValue(frequency=0.7, confidence=0.6, evidence_count=1),
    )


def _build_graph(entities=None, relationships=None):
    """Build a KnowledgeGraph with optional entities and relationships."""
    graph = KnowledgeGraph.__new__(KnowledgeGraph)
    graph._path = type("P", (), {"exists": lambda self: False})()
    graph._entities = {}
    graph._relationships = []
    graph._resolution = type("R", (), {"canonical_id": lambda self, x: x})()
    graph._hash_index = {}
    graph._incoming_set = {}
    graph._versioning_enabled = False
    graph._change_buffer = None
    graph._version_log = None
    graph._adjacency = None
    graph._stream_registry = None

    for e in entities or []:
        graph._entities[e.id] = e
        graph._hash_index[e.content_hash] = e.id
    for r in relationships or []:
        graph._relationships.append(r)

    return graph


class TestGraphStats:
    """TEST-25-01-01: GET /stats returns entity/relationship counts."""

    def test_stats_returns_counts(self, client):
        e1 = _make_entity("paper:1", "Paper One", EntityType.PAPER)
        e2 = _make_entity("author:1", "Author A", EntityType.AUTHOR)
        r1 = _make_relationship("paper:1", "author:1")
        graph = _build_graph(entities=[e1, e2], relationships=[r1])

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["entity_count"] == 2
        assert data["relationship_count"] == 1
        assert "entity_types" in data
        assert data["entity_types"]["paper"] == 1
        assert data["entity_types"]["author"] == 1


class TestListEntities:
    """TEST-25-01-02: GET /entities returns entity list (limit 100)."""

    def test_entities_returns_list(self, client):
        e1 = _make_entity("concept:1", "Alpha")
        e2 = _make_entity("concept:2", "Beta")
        graph = _build_graph(entities=[e1, e2])

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/entities")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] in ("Alpha", "Beta")
        assert "entity_type" in data[0]
        assert "truth" in data[0]


class TestFilterByType:
    """TEST-25-01-03: GET /entities?type=X filters by type."""

    def test_entities_filter_by_type(self, client):
        e1 = _make_entity("paper:1", "Paper One", EntityType.PAPER)
        e2 = _make_entity("concept:1", "Concept One", EntityType.CONCEPT)
        graph = _build_graph(entities=[e1, e2])

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/entities?type=paper")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["entity_type"] == "paper"
        assert data[0]["name"] == "Paper One"


class TestGetEntity:
    """TEST-25-01-04: GET /entity/{id} returns entity with relationships."""

    def test_entity_detail_with_relationships(self, client):
        e1 = _make_entity("paper:1", "Paper One", EntityType.PAPER)
        e2 = _make_entity("author:1", "Author A", EntityType.AUTHOR)
        r1 = _make_relationship("paper:1", "author:1")
        graph = _build_graph(entities=[e1, e2], relationships=[r1])

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/entity/paper:1")

        assert response.status_code == 200
        data = response.json()
        assert data["entity"]["id"] == "paper:1"
        assert data["entity"]["name"] == "Paper One"
        assert len(data["relationships"]) == 1
        assert data["relationships"][0]["relation_type"] == "cites"


class TestGetSubgraph:
    """TEST-25-01-05: GET /subgraph/{id} returns connected subgraph."""

    def test_subgraph_returns_connected_entities(self, client):
        e1 = _make_entity("paper:1", "Paper One", EntityType.PAPER)
        e2 = _make_entity("author:1", "Author A", EntityType.AUTHOR)
        e3 = _make_entity("concept:1", "Concept X", EntityType.CONCEPT)
        r1 = _make_relationship("paper:1", "author:1")
        r2 = _make_relationship("paper:1", "concept:1")
        graph = _build_graph(entities=[e1, e2, e3], relationships=[r1, r2])

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/subgraph/paper:1?depth=1")

        assert response.status_code == 200
        data = response.json()
        entity_ids = [e["id"] for e in data["entities"]]
        assert "paper:1" in entity_ids
        assert "author:1" in entity_ids
        assert "concept:1" in entity_ids
        assert len(data["relationships"]) == 2


class TestEntityNotFound:
    """TEST-25-01-06: Entity not found returns 404."""

    def test_entity_not_found_returns_404(self, client):
        graph = _build_graph()

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/entity/nonexistent:123")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND"

    def test_subgraph_not_found_returns_404(self, client):
        graph = _build_graph()

        with patch(
            "backend.api.routes.knowledge_graph._get_graph", return_value=graph
        ):
            response = client.get("/api/v1/knowledge-graph/subgraph/nonexistent:123")

        assert response.status_code == 404
