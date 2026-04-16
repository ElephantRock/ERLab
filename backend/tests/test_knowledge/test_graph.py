"""Tests for knowledge graph."""

from backend.pipeline.knowledge.entities import EntityResolution, EntityType, KnowledgeEntity
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
from backend.pipeline.knowledge.truth import TruthValue


class TestEntityResolution:
    def test_find_unregistered(self):
        uf = EntityResolution()
        assert uf.find("paper:attention_is_all_you_need") == "paper:attention_is_all_you_need"

    def test_union_merges(self):
        uf = EntityResolution()
        uf.union("author:vaswani", "author:vaswani_a")
        assert uf.are_same("author:vaswani", "author:vaswani_a")

    def test_canonical_id(self):
        uf = EntityResolution()
        uf.union("method:transformer", "method:transformer_arch")
        canonical = uf.canonical_id("method:transformer_arch")
        assert canonical in ("method:transformer", "method:transformer_arch")

    def test_transitive_union(self):
        uf = EntityResolution()
        uf.union("a", "b")
        uf.union("b", "c")
        assert uf.are_same("a", "c")


class TestKnowledgeGraph:
    def test_add_entity(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        eid = kg.add_entity(KnowledgeEntity(
            id="paper:attention",
            entity_type=EntityType.PAPER,
            name="Attention Is All You Need",
            truth=TruthValue.from_observation(0.9),
        ))
        assert eid == "paper:attention"
        assert kg.get_entity("paper:attention") is not None

    def test_add_relationship(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(
            id="paper:a", entity_type=EntityType.PAPER, name="Paper A",
        ))
        kg.add_entity(KnowledgeEntity(
            id="paper:b", entity_type=EntityType.PAPER, name="Paper B",
        ))
        kg.add_relationship(KnowledgeRelationship(
            source_id="paper:a",
            target_id="paper:b",
            relation_type=RelationType.CITES,
            evidence=["paper:a"],
        ))
        assert len(kg._relationships) == 1

    def test_reinforce_edge(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(id="p:a", entity_type=EntityType.PAPER, name="A"))
        kg.add_entity(KnowledgeEntity(id="p:b", entity_type=EntityType.PAPER, name="B"))
        kg.add_relationship(KnowledgeRelationship(
            source_id="p:a", target_id="p:b", relation_type=RelationType.CITES, weight=1.0,
        ))
        kg.reinforce("p:a", "p:b", RelationType.CITES, delta=0.2)
        assert kg._relationships[0].weight == 1.2

    def test_weaken_edge(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(id="p:a", entity_type=EntityType.PAPER, name="A"))
        kg.add_entity(KnowledgeEntity(id="p:b", entity_type=EntityType.PAPER, name="B"))
        kg.add_relationship(KnowledgeRelationship(
            source_id="p:a", target_id="p:b", relation_type=RelationType.CITES, weight=1.0,
        ))
        kg.weaken("p:a", "p:b", RelationType.CITES, delta=0.3)
        assert kg._relationships[0].weight == 0.7

    def test_get_neighbors(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(id="p:a", entity_type=EntityType.PAPER, name="A"))
        kg.add_entity(KnowledgeEntity(id="p:b", entity_type=EntityType.PAPER, name="B"))
        kg.add_entity(KnowledgeEntity(id="p:c", entity_type=EntityType.PAPER, name="C"))
        kg.add_relationship(KnowledgeRelationship(
            source_id="p:a", target_id="p:b", relation_type=RelationType.CITES,
        ))
        kg.add_relationship(KnowledgeRelationship(
            source_id="p:c", target_id="p:a", relation_type=RelationType.EXTENDS,
        ))
        neighbors = kg.get_neighbors("p:a")
        names = {n.name for n in neighbors}
        assert "B" in names
        assert "C" in names

    def test_merge_entities(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(id="auth:vaswani", entity_type=EntityType.AUTHOR, name="Vaswani"))
        kg.add_entity(KnowledgeEntity(id="auth:vaswani_a", entity_type=EntityType.AUTHOR, name="Vaswani A."))
        kg.merge_entities("auth:vaswani", "auth:vaswani_a")
        # Both should resolve to same canonical
        assert kg._resolution.are_same("auth:vaswani", "auth:vaswani_a")

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "kg.json")
        kg1 = KnowledgeGraph(persist_path=path)
        kg1.add_entity(KnowledgeEntity(
            id="p:test", entity_type=EntityType.PAPER, name="Test Paper",
        ))
        kg1.save()

        kg2 = KnowledgeGraph(persist_path=path)
        assert kg2.get_entity("p:test") is not None
        assert kg2.get_entity("p:test").name == "Test Paper"

    def test_graph_stats(self, tmp_path):
        kg = KnowledgeGraph(persist_path=str(tmp_path / "kg.json"))
        kg.add_entity(KnowledgeEntity(id="p:1", entity_type=EntityType.PAPER, name="P1"))
        kg.add_entity(KnowledgeEntity(id="p:2", entity_type=EntityType.PAPER, name="P2"))
        kg.add_entity(KnowledgeEntity(id="m:1", entity_type=EntityType.METHOD, name="M1"))
        kg.add_relationship(KnowledgeRelationship(
            source_id="p:1", target_id="p:2", relation_type=RelationType.CITES,
        ))
        stats = kg.get_graph_stats()
        assert stats["entity_count"] == 3
        assert stats["relationship_count"] == 1
        assert stats["entity_types"]["paper"] == 2
        assert stats["entity_types"]["method"] == 1
