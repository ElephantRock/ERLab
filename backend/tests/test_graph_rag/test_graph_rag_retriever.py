"""Tests for graph-augmented retrieval."""

from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.flaky(reruns=3, reruns_delay=2)

from backend.pipeline.knowledge.entities import KnowledgeEntity, EntityType, TruthValue
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.graph_rag_retriever import GraphRAGRetriever
from backend.pipeline.knowledge.graph_walks import GraphWalker
from backend.pipeline.knowledge.retriever import RetrievalResult, RetrievalSource
from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType


def _make_entity(name: str, etype: EntityType = EntityType.CONCEPT) -> KnowledgeEntity:
    eid = f"{etype.value}:{name.lower()}"
    return KnowledgeEntity(id=eid, name=name, entity_type=etype, truth=TruthValue.initial())


class FakeBaseRetriever:
    def __init__(self, results=None):
        self._results = results or []

    async def retrieve(self, query, n_results=10, overfetch=3, rrf_k=None, min_score=0.0,
                       filter_metadata=None):
        return self._results


class FakeGraphIndex:
    def __init__(self, entity_ids=None):
        self._ids = entity_ids or []

    async def query_similar(self, query, n_results=20, entity_type=None):
        return [{"id": eid, "distance": 0.5, "text": "entity"} for eid in self._ids]


class TestGraphRAGRetriever:
    @pytest.mark.anyio
    async def test_retrieve_delegates_to_base_retriever(self):
        base_results = [
            RetrievalResult(id="doc1", text="text1", score=0.8, source=RetrievalSource.SEMANTIC),
        ]
        base = FakeBaseRetriever(results=base_results)
        retriever = GraphRAGRetriever(base_retriever=base, kg=KnowledgeGraph(persist_path="NUL"))
        results = await retriever.retrieve("test query")
        assert len(results) == 1
        assert results[0].id == "doc1"

    @pytest.mark.anyio
    async def test_retrieve_without_graph_index_returns_base(self):
        base_results = [RetrievalResult(id="d1", text="t1", score=0.5)]
        base = FakeBaseRetriever(results=base_results)
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=KnowledgeGraph(),
            graph_embedding_index=None,
        )
        results = await retriever.retrieve("query", use_graph=True)
        assert results == base_results

    @pytest.mark.anyio
    async def test_retrieve_with_graph_augmentation(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("BERT", EntityType.METHOD))
        kg.add_entity(_make_entity("Paper1", EntityType.PAPER))
        kg.add_relationship(KnowledgeRelationship(
            source_id="paper:paper1", target_id="method:bert",
            relation_type=RelationType.USES_METHOD, weight=1.0,
        ))

        base_results = [RetrievalResult(id="doc1", text="t1", score=0.5)]
        base = FakeBaseRetriever(results=base_results)
        graph_index = FakeGraphIndex(entity_ids=["method:bert"])
        walker = GraphWalker(kg)

        retriever = GraphRAGRetriever(
            base_retriever=base, kg=kg,
            graph_embedding_index=graph_index, graph_walker=walker,
        )
        results = await retriever.retrieve("transformer model", use_graph=True)
        graph_ids = [r.id for r in results if r.id.startswith("graph_")]
        assert len(graph_ids) > 0

    @pytest.mark.anyio
    async def test_three_way_rrf(self):
        base = FakeBaseRetriever()
        retriever = GraphRAGRetriever(base_retriever=base, kg=KnowledgeGraph())

        base_results = [RetrievalResult(id="doc1", text="t1", score=0.5)]
        graph_results = [{"id": "graph_doc1", "text": "gt1", "score": 0.3}]

        fused = retriever._three_way_rrf(base_results, graph_results, k=60, graph_weight=0.3)
        assert len(fused) >= 2
        assert all(isinstance(r, RetrievalResult) for r in fused)

    @pytest.mark.anyio
    async def test_three_way_rrf_with_empty_graph(self):
        base = FakeBaseRetriever()
        retriever = GraphRAGRetriever(base_retriever=base, kg=KnowledgeGraph())

        base_results = [RetrievalResult(id="doc1", text="t1", score=0.5)]
        fused = retriever._three_way_rrf(base_results, [], k=60)
        assert len(fused) == 1

    @pytest.mark.anyio
    async def test_graph_weight_configurable(self):
        base = FakeBaseRetriever()
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=KnowledgeGraph(), graph_weight=0.5,
        )
        assert retriever._graph_weight == 0.5

    @pytest.mark.anyio
    async def test_min_score_filter_applied(self):
        base_results = [
            RetrievalResult(id="doc1", text="t1", score=0.01),
            RetrievalResult(id="doc2", text="t2", score=0.5),
        ]
        base = FakeBaseRetriever(results=base_results)
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=KnowledgeGraph(),
            graph_embedding_index=None,
        )
        results = await retriever.retrieve("query", min_score=0.1)
        assert all(r.score >= 0.1 for r in results)

    @pytest.mark.anyio
    async def test_graph_rag_disabled_falls_back(self):
        base_results = [RetrievalResult(id="d1", text="t1", score=0.5)]
        base = FakeBaseRetriever(results=base_results)
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=KnowledgeGraph(),
            graph_embedding_index=FakeGraphIndex(),
        )
        results = await retriever.retrieve("query", use_graph=False)
        assert results == base_results

    @pytest.mark.anyio
    async def test_retrieve_respects_n_results(self):
        base_results = [RetrievalResult(id=f"d{i}", text=f"t{i}", score=0.5) for i in range(20)]
        base = FakeBaseRetriever(results=base_results)
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=KnowledgeGraph(), graph_embedding_index=None,
        )
        results = await retriever.retrieve("query", n_results=5)
        assert len(results) <= 5

    @pytest.mark.anyio
    async def test_query_to_entities_returns_ids(self):
        kg = KnowledgeGraph()
        graph_index = FakeGraphIndex(entity_ids=["concept:nlp", "method:bert"])
        base = FakeBaseRetriever()
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=kg, graph_embedding_index=graph_index,
        )
        ids = await retriever._query_to_entities("NLP methods")
        assert len(ids) == 2

    @pytest.mark.anyio
    async def test_query_to_entities_empty_index(self):
        kg = KnowledgeGraph()
        graph_index = FakeGraphIndex(entity_ids=[])
        base = FakeBaseRetriever()
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=kg, graph_embedding_index=graph_index,
        )
        ids = await retriever._query_to_entities("anything")
        assert ids == []

    @pytest.mark.anyio
    async def test_entities_to_documents_maps_papers(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("BERT", EntityType.METHOD))
        kg.add_entity(_make_entity("Paper1", EntityType.PAPER))
        kg.add_relationship(KnowledgeRelationship(
            source_id="paper:paper1", target_id="method:bert",
            relation_type=RelationType.USES_METHOD, weight=1.0,
        ))

        base = FakeBaseRetriever()
        walker = GraphWalker(kg)
        graph_index = FakeGraphIndex(entity_ids=["method:bert"])
        retriever = GraphRAGRetriever(
            base_retriever=base, kg=kg,
            graph_embedding_index=graph_index, graph_walker=walker,
        )
        graph_results = await retriever._graph_retrieve("BERT")
        graph_doc_ids = [r["id"] for r in graph_results]
        assert any("paper1" in gid for gid in graph_doc_ids)

    @pytest.mark.anyio
    async def test_end_to_end_with_small_graph(self):
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("Transformer", EntityType.METHOD))
        kg.add_entity(_make_entity("Attention", EntityType.CONCEPT))
        kg.add_entity(_make_entity("Vaswani2017", EntityType.PAPER))
        kg.add_relationship(KnowledgeRelationship(
            source_id="paper:vaswani2017", target_id="method:transformer",
            relation_type=RelationType.PROPOSES_METHOD, weight=1.5,
        ))
        kg.add_relationship(KnowledgeRelationship(
            source_id="method:transformer", target_id="concept:attention",
            relation_type=RelationType.USES_METHOD, weight=1.0,
        ))

        base_results = [RetrievalResult(id="d1", text="base doc", score=0.6)]
        base = FakeBaseRetriever(results=base_results)
        graph_index = FakeGraphIndex(entity_ids=["method:transformer"])
        walker = GraphWalker(kg)

        retriever = GraphRAGRetriever(
            base_retriever=base, kg=kg,
            graph_embedding_index=graph_index, graph_walker=walker,
            walk_max_hops=2,
        )
        results = await retriever.retrieve("attention mechanism")
        assert len(results) >= 1
