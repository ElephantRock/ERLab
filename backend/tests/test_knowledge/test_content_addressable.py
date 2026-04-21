"""Tests for content-addressable knowledge identity (Gap 23)."""

import tempfile

from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue


class TestContentHash:
    def test_deterministic(self):
        e = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        assert e.content_hash == e.content_hash
        assert len(e.content_hash) == 16

    def test_differs_on_name_change(self):
        e1 = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        e2 = KnowledgeEntity(
            id="c:beta",
            entity_type=EntityType.CONCEPT,
            name="Beta",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        assert e1.content_hash != e2.content_hash

    def test_differs_on_truth_change(self):
        e1 = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        e2 = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.3, confidence=0.2),
        )
        assert e1.content_hash != e2.content_hash

    def test_same_content_same_hash(self):
        e1 = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        e2 = KnowledgeEntity(
            id="c:alpha",
            entity_type=EntityType.CONCEPT,
            name="Alpha",
            truth=TruthValue(frequency=0.8, confidence=0.7),
        )
        assert e1.content_hash == e2.content_hash


class TestContentAddressableGraph:
    def test_dedup_on_identical_add(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            kg.add_entity(
                KnowledgeEntity(
                    id="c:alpha",
                    entity_type=EntityType.CONCEPT,
                    name="Alpha",
                    truth=TruthValue(frequency=0.8, confidence=0.7),
                )
            )
            kg.add_entity(
                KnowledgeEntity(
                    id="c:alpha",
                    entity_type=EntityType.CONCEPT,
                    name="Alpha",
                    truth=TruthValue(frequency=0.8, confidence=0.7),
                )
            )
            assert len(kg._entities) == 1
            assert kg._entities["c:alpha"].truth.evidence_count == 1

    def test_different_entities_coexist(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            kg.add_entity(
                KnowledgeEntity(
                    id="c:alpha",
                    entity_type=EntityType.CONCEPT,
                    name="Alpha",
                    truth=TruthValue.from_observation(),
                )
            )
            kg.add_entity(
                KnowledgeEntity(
                    id="c:beta",
                    entity_type=EntityType.CONCEPT,
                    name="Beta",
                    truth=TruthValue.from_observation(),
                )
            )
            assert len(kg._entities) == 2

    def test_get_by_content_hash_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            entity = KnowledgeEntity(
                id="c:alpha",
                entity_type=EntityType.CONCEPT,
                name="Alpha",
                truth=TruthValue(frequency=0.8, confidence=0.7),
            )
            kg.add_entity(entity)
            result = kg.get_by_content_hash(entity.content_hash)
            assert result is not None
            assert result.id == "c:alpha"

    def test_get_by_content_hash_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            assert kg.get_by_content_hash("nonexistent_hash") is None

    def test_get_referencing_relationships(self):
        with tempfile.TemporaryDirectory() as tmp:
            kg = KnowledgeGraph(persist_path=f"{tmp}/kg.json")
            kg.add_entity(
                KnowledgeEntity(
                    id="c:a",
                    entity_type=EntityType.CONCEPT,
                    name="A",
                    truth=TruthValue.from_observation(),
                )
            )
            kg.add_entity(
                KnowledgeEntity(
                    id="c:b",
                    entity_type=EntityType.CONCEPT,
                    name="B",
                    truth=TruthValue.from_observation(),
                )
            )
            kg.add_entity(
                KnowledgeEntity(
                    id="c:c",
                    entity_type=EntityType.CONCEPT,
                    name="C",
                    truth=TruthValue.from_observation(),
                )
            )
            kg.add_relationship(
                KnowledgeRelationship(
                    source_id="c:a",
                    target_id="c:b",
                    relation_type=RelationType.BUILDS_ON,
                    truth=TruthValue.from_observation(),
                )
            )
            kg.add_relationship(
                KnowledgeRelationship(
                    source_id="c:c",
                    target_id="c:a",
                    relation_type=RelationType.EXTENDS,
                    truth=TruthValue.from_observation(),
                )
            )

            refs = kg.get_referencing_relationships("c:a")
            assert len(refs) == 2

    def test_hash_index_rebuilt_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/kg.json"
            entity = KnowledgeEntity(
                id="c:alpha",
                entity_type=EntityType.CONCEPT,
                name="Alpha",
                truth=TruthValue(frequency=0.8, confidence=0.7),
            )
            kg1 = KnowledgeGraph(persist_path=path)
            kg1.add_entity(entity)
            kg1.save()

            kg2 = KnowledgeGraph(persist_path=path)
            result = kg2.get_by_content_hash(entity.content_hash)
            assert result is not None
            assert result.name == "Alpha"
