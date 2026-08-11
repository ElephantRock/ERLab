"""Tests for graph embeddings index."""

import pytest

from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity, TruthValue
from backend.pipeline.knowledge.graph import KnowledgeGraph
from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex


class FakeEmbeddingProvider:
    def __init__(self, dimension: int = 10):
        self._dim = dimension

    async def embed(self, texts):
        return [[0.1 * (i + 1) for i in range(self._dim)] for _ in texts]

    @property
    def dimension(self):
        return self._dim

    @property
    def provider_name(self):
        return "fake"


def _make_entity(name: str, etype: EntityType = EntityType.CONCEPT, **props) -> KnowledgeEntity:
    eid = f"{etype.value}:{name.lower()}"
    return KnowledgeEntity(
        id=eid, name=name, entity_type=etype,
        truth=TruthValue(frequency=0.8, confidence=0.9),
        properties=props,
    )


@pytest.fixture
def embedding_service():
    return EmbeddingService(FakeEmbeddingProvider(dimension=10))


class TestGraphEmbeddingIndex:
    @pytest.mark.anyio
    async def test_index_entity_stores_embedding(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge1")
        entity = _make_entity("BERT", EntityType.METHOD)
        await idx.index_entity(entity)
        assert idx._collection.count() == 1

    @pytest.mark.anyio
    async def test_index_graph_indexes_all_entities(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge2")
        kg = KnowledgeGraph(persist_path="NUL")
        kg.add_entity(_make_entity("A"))
        kg.add_entity(_make_entity("B"))
        count = await idx.index_graph(kg)
        assert count == 2

    @pytest.mark.anyio
    async def test_query_similar_returns_matching(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge3")
        await idx.index_entity(_make_entity("BERT", EntityType.METHOD))
        results = await idx.query_similar("transformer model", n_results=5)
        assert len(results) >= 1
        assert results[0]["id"] == "method:bert"

    @pytest.mark.anyio
    async def test_query_by_embedding(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge4")
        await idx.index_entity(_make_entity("GPT", EntityType.METHOD))
        embedding = [0.1 * (i + 1) for i in range(10)]
        results = await idx.query_by_embedding(embedding, n_results=5)
        assert len(results) >= 1

    @pytest.mark.anyio
    async def test_empty_collection_returns_empty(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge5")
        results = await idx.query_similar("anything", n_results=5)
        assert results == []

    @pytest.mark.anyio
    async def test_index_empty_graph(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge6")
        kg = KnowledgeGraph(persist_path="NUL")
        count = await idx.index_graph(kg)
        assert count == 0

    @pytest.mark.anyio
    async def test_entity_text_includes_name_type(self, embedding_service):
        entity = _make_entity("BERT", EntityType.METHOD, description="encoder")
        text = GraphEmbeddingIndex._entity_to_text(entity)
        assert "BERT" in text
        assert "method" in text

    @pytest.mark.anyio
    async def test_persistence_across_instances(self, embedding_service, tmp_path):
        idx1 = GraphEmbeddingIndex(str(tmp_path / "emb7"), embedding_service)
        await idx1.index_entity(_make_entity("Test", EntityType.CONCEPT))

        idx2 = GraphEmbeddingIndex(str(tmp_path / "emb7"), embedding_service)
        results = await idx2.query_similar("test", n_results=5)
        assert len(results) >= 1

    @pytest.mark.anyio
    async def test_query_with_type_filter(self, embedding_service, chroma_client):
        idx = GraphEmbeddingIndex(".", embedding_service, client=chroma_client, collection_name="ge8")
        await idx.index_entity(_make_entity("BERT", EntityType.METHOD))
        await idx.index_entity(_make_entity("NLP", EntityType.CONCEPT))
        results = await idx.query_similar("model", n_results=5, entity_type=EntityType.METHOD)
        assert all(r["metadata"]["entity_type"] == "method" for r in results)
