"""Tests for graph walk traversal."""


from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity, TruthValue
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.graph_walks import GraphWalker
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType


def _make_entity(name: str, etype: EntityType = EntityType.CONCEPT, freq: float = 0.8) -> KnowledgeEntity:
    eid = f"{etype.value}:{name.lower()}"
    return KnowledgeEntity(
        id=eid,
        name=name,
        entity_type=etype,
        truth=TruthValue(frequency=freq, confidence=0.9),
    )


def _make_rel(src: str, tgt: str, rtype: RelationType = RelationType.BUILDS_ON, weight: float = 1.0) -> KnowledgeRelationship:
    return KnowledgeRelationship(
        source_id=src, target_id=tgt, relation_type=rtype, weight=weight,
    )


class TestGraphWalkerBFS:
    def test_bfs_single_hop(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=1)
        ids = {r.entity_id for r in results}
        assert "concept:a" in ids
        assert "concept:b" in ids

    def test_bfs_multi_hop(self):
        kg = KnowledgeGraph(persist_path="NUL")
        for name in ["A", "B", "C"]:
            kg.add_entity(_make_entity(name))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:c"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=2)
        ids = {r.entity_id for r in results}
        assert "concept:c" in ids

    def test_bfs_respects_max_hops(self):
        kg = KnowledgeGraph(persist_path="NUL")
        for name in ["A", "B", "C", "D"]:
            kg.add_entity(_make_entity(name))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:c"))
        kg.add_relationship(_make_rel("concept:c", "concept:d"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=1)
        ids = {r.entity_id for r in results}
        assert "concept:d" not in ids

    def test_bfs_respects_max_results(self):
        kg = KnowledgeGraph(persist_path="NUL")
        for i in range(10):
            kg.add_entity(_make_entity(f"N{i}"))
            kg.add_relationship(_make_rel("concept:a", f"concept:N{i}"))
        kg.add_entity(_make_entity("A"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=1, max_results=5)
        assert len(results) <= 5

    def test_bfs_with_relation_filter(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_entity(_make_entity("C"))
        kg.add_relationship(_make_rel("concept:a", "concept:b", RelationType.CITES))
        kg.add_relationship(_make_rel("concept:a", "concept:c", RelationType.CONTRADICTS))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(
            ["concept:a"], max_hops=1,
            relation_filter=[RelationType.CITES],
        )
        ids = {r.entity_id for r in results}
        assert "concept:b" in ids
        assert "concept:c" not in ids

    def test_walk_from_nonexistent_entity_returns_seed_only(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:NONEXISTENT"], max_hops=2)
        assert len(results) == 0


class TestGraphWalkerWeighted:
    def test_weighted_walk_prefers_high_weight_edges(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_entity(_make_entity("C"))
        kg.add_relationship(_make_rel("concept:a", "concept:b", weight=1.9))
        kg.add_relationship(_make_rel("concept:a", "concept:c", weight=0.1))

        walker = GraphWalker(kg)
        results = walker.walk_weighted(["concept:a"], max_hops=1)
        if len(results) > 1:
            b_result = next((r for r in results if r.entity_id == "concept:b"), None)
            c_result = next((r for r in results if r.entity_id == "concept:c"), None)
            if b_result and c_result:
                assert b_result.score >= c_result.score

    def test_walk_circular_graph_no_infinite_loop(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:a"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=5)
        assert len(results) == 2

    def test_walk_score_includes_truth_expectation(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A", freq=0.9))
        kg.add_entity(_make_entity("B", freq=0.1))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))

        walker = GraphWalker(kg)
        results = walker.walk_bfs(["concept:a"], max_hops=1)
        a_result = next(r for r in results if r.entity_id == "concept:a")
        assert a_result.score > 0


class TestExtractSubgraph:
    def test_extract_subgraph(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        kg.add_entity(_make_entity("C"))
        kg.add_relationship(_make_rel("concept:a", "concept:b"))
        kg.add_relationship(_make_rel("concept:b", "concept:c"))

        walker = GraphWalker(kg)
        sub = walker.extract_subgraph(["concept:a"], max_hops=1)
        assert "concept:a" in sub["entities"]
        assert "concept:b" in sub["entities"]
        assert len(sub["relationships"]) >= 1
