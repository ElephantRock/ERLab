"""Tests for community detection via label propagation."""

import pytest

from backend.pipeline.knowledge.entities import KnowledgeEntity, EntityType, TruthValue
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.community_detection import CommunityDetector
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType


def _make_entity(name: str, etype: EntityType = EntityType.CONCEPT) -> KnowledgeEntity:
    eid = f"{etype.value}:{name.lower()}"
    return KnowledgeEntity(id=eid, name=name, entity_type=etype, truth=TruthValue.initial())


def _make_rel(src: str, tgt: str, weight: float = 1.0) -> KnowledgeRelationship:
    return KnowledgeRelationship(
        source_id=src, target_id=tgt,
        relation_type=RelationType.BUILDS_ON, weight=weight,
    )


class TestCommunityDetector:
    def test_single_entity_returns_single_community(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(_make_entity("A"))
        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        assert len(communities) == 1
        assert len(communities[0].entity_ids) == 1

    def test_disconnected_entities_separate_communities(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        assert len(communities) == 2

    def test_detect_communities_on_clustered_graph(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        for name in ["A", "B", "C", "D", "E", "F"]:
            kg.add_entity(_make_entity(name))

        # Cluster 1: A-B-C
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:c"))
        kg.add_relationship(_make_rel("concept:a", "concept:c"))

        # Cluster 2: D-E-F
        kg.add_relationship(_make_rel("concept:d", "concept:e"))
        kg.add_relationship(_make_rel("concept:e", "concept:f"))
        kg.add_relationship(_make_rel("concept:d", "concept:f"))

        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        assert len(communities) == 2
        sizes = sorted(len(c.entity_ids) for c in communities)
        assert sizes == [3, 3]

    def test_get_entity_community(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))

        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        result = detector.get_entity_community("concept:a", communities)
        assert result is not None
        assert "concept:a" in result.entity_ids

    def test_get_community_entities(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))

        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        entities = detector.get_community_entities(communities[0].id, communities)
        assert len(entities) >= 1

    def test_modularity_score_nonnegative(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        for name in ["A", "B", "C"]:
            kg.add_entity(_make_entity(name))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:c"))

        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        for c in communities:
            assert c.modularity_score >= 0.0

    def test_empty_graph_returns_empty(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        detector = CommunityDetector(kg)
        communities = detector.detect_communities()
        assert communities == []

    def test_community_labels_stable(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        for name in ["A", "B"]:
            kg.add_entity(_make_entity(name))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))

        detector = CommunityDetector(kg)
        c1 = detector.detect_communities()
        c2 = detector.detect_communities()
        assert len(c1) == len(c2)
