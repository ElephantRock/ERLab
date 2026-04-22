"""Tests for tool embedding index."""

import pytest

from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.tools.registry import ToolDefinition, ToolRegistry
from backend.pipeline.tools.tool_index import ToolEmbeddingIndex


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


def _make_tool(name: str, description: str = "", params: dict | None = None,
               trust_level: str = "trusted") -> ToolDefinition:
    async def handler(**kwargs):
        return "ok"

    return ToolDefinition(
        name=name,
        description=description or f"Tool: {name}",
        parameters=params or {},
        handler=handler,
        trust_level=trust_level,
    )


@pytest.fixture
def embedding_service():
    return EmbeddingService(FakeEmbeddingProvider(dimension=10))


class TestToolEmbeddingIndex:
    @pytest.mark.anyio
    async def test_index_tool_stores_embedding(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti1", client=chroma_client)
        tool = _make_tool("search_papers", description="Search for academic papers")
        await idx.index_tool(tool)
        assert idx._collection.count() == 1

    @pytest.mark.anyio
    async def test_index_registry_indexes_all_tools(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti2", client=chroma_client)
        registry = ToolRegistry()
        registry.register(name="tool_a", handler=lambda: None, description="Tool A")
        registry.register(name="tool_b", handler=lambda: None, description="Tool B")
        count = await idx.index_registry(registry)
        assert count == 2

    @pytest.mark.anyio
    async def test_query_returns_matching(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti3", client=chroma_client)
        await idx.index_tool(_make_tool("search_papers", description="Search academic papers"))
        results = await idx.query("find papers", n_results=5)
        assert len(results) >= 1
        assert results[0].tool_name == "search_papers"

    @pytest.mark.anyio
    async def test_query_empty_returns_empty(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti4", client=chroma_client)
        results = await idx.query("anything", n_results=5)
        assert results == []

    @pytest.mark.anyio
    async def test_tool_text_includes_name_and_params(self):
        tool = _make_tool("search", description="Search things", params={"query": {"type": "string"}})
        text = ToolEmbeddingIndex._tool_to_text(tool)
        assert "search" in text
        assert "query" in text

    @pytest.mark.anyio
    async def test_query_with_trust_filter(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti6", client=chroma_client)
        await idx.index_tool(_make_tool("trusted_tool", trust_level="trusted"))
        await idx.index_tool(_make_tool("untrusted_tool", trust_level="untrusted"))
        results = await idx.query("tool", n_results=5, trust_level="trusted")
        assert all(r.metadata.get("trust_level") == "trusted" for r in results)

    @pytest.mark.anyio
    async def test_upsert_overwrites_existing(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti7", client=chroma_client)
        await idx.index_tool(_make_tool("my_tool", description="v1"))
        await idx.index_tool(_make_tool("my_tool", description="v2 updated"))
        assert idx._collection.count() == 1

    @pytest.mark.anyio
    async def test_index_registry_skips_disabled(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti8", client=chroma_client)
        registry = ToolRegistry()
        registry.register(name="enabled_tool", handler=lambda: None, description="Enabled", is_enabled=True)
        registry.register(name="disabled_tool", handler=lambda: None, description="Disabled", is_enabled=False)
        count = await idx.index_registry(registry)
        assert count == 1

    @pytest.mark.anyio
    async def test_search_result_has_source_semantic(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti9", client=chroma_client)
        await idx.index_tool(_make_tool("search"))
        results = await idx.query("search", n_results=5)
        assert all(r.source == "semantic" for r in results)

    @pytest.mark.anyio
    async def test_score_is_one_minus_distance(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti10", client=chroma_client)
        await idx.index_tool(_make_tool("tool1", description="search"))
        results = await idx.query("search", n_results=5)
        assert all(0.0 <= r.score <= 1.0 for r in results)

    @pytest.mark.anyio
    async def test_index_empty_registry(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="ti11", client=chroma_client)
        count = await idx.index_registry(ToolRegistry())
        assert count == 0
