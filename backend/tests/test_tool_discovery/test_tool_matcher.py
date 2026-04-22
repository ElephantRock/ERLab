"""Tests for hybrid tool matching."""

import pytest

from backend.pipeline.knowledge.bm25_index import BM25Index
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.tools.registry import ToolDefinition, ToolRegistry
from backend.pipeline.tools.tool_index import ToolEmbeddingIndex, ToolSearchResult
from backend.pipeline.tools.tool_matcher import ToolMatcher


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


def _make_tool(name: str, description: str = "", trust_level: str = "trusted") -> ToolDefinition:
    async def handler(**kwargs):
        return "ok"

    return ToolDefinition(
        name=name,
        description=description or f"Tool: {name}",
        parameters={},
        handler=handler,
        trust_level=trust_level,
    )


@pytest.fixture
def embedding_service():
    return EmbeddingService(FakeEmbeddingProvider(dimension=10))


class TestToolMatcher:
    @pytest.mark.anyio
    async def test_semantic_only_search(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm1", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm1_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("search_papers", description="Search academic papers by keyword")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        results = await matcher.find_tools("find papers", source="semantic")
        assert len(results) >= 1
        assert results[0].source == "semantic"

    @pytest.mark.anyio
    async def test_keyword_only_search(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm2", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm2_bm25"))
        registry = ToolRegistry()

        registry.register(name="calculate_metrics", handler=lambda: None, description="Calculate precision recall metrics")
        registry.register(name="search_papers", handler=lambda: None, description="Search academic papers by keyword")
        registry.register(name="generate_summary", handler=lambda: None, description="Generate research summary")

        matcher = ToolMatcher(idx, bm25, registry)
        matcher._index_tools_to_bm25()

        results = await matcher.find_tools("precision metrics", source="keyword")
        assert len(results) >= 1
        assert results[0].source == "keyword"

    @pytest.mark.anyio
    async def test_hybrid_search_returns_fused(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm3", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm3_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("search_papers", description="Search academic papers")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        matcher._index_tools_to_bm25()

        results = await matcher.find_tools("search papers")
        assert len(results) >= 1
        assert results[0].source == "fused"

    @pytest.mark.anyio
    async def test_find_and_rank_returns_tool_definitions(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm4", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm4_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("search_papers", description="Search papers")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        tools = await matcher.find_and_rank("search", n_results=5)
        assert len(tools) >= 1
        assert isinstance(tools[0], ToolDefinition)

    @pytest.mark.anyio
    async def test_find_and_rank_respects_min_score(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm5", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm5_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("tool_a", description="Something unrelated")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        tools = await matcher.find_and_rank("completely different", min_score=0.99)
        assert len(tools) == 0

    @pytest.mark.anyio
    async def test_refresh_index(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm6", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm6_bm25"))
        registry = ToolRegistry()
        registry.register(name="tool_a", handler=lambda: None, description="Tool A")
        registry.register(name="tool_b", handler=lambda: None, description="Tool B")

        matcher = ToolMatcher(idx, bm25, registry)
        count = await matcher.refresh_index()
        assert count == 2

    @pytest.mark.anyio
    async def test_rrf_fusion_deduplicates(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm7", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm7_bm25"))
        registry = ToolRegistry()

        matcher = ToolMatcher(idx, bm25, registry)

        semantic = [ToolSearchResult(tool_name="tool_a", score=0.8, source="semantic")]
        keyword = [ToolSearchResult(tool_name="tool_a", score=0.7, source="keyword")]

        fused = matcher._rrf_fuse(semantic, keyword, n_results=10)
        assert len(fused) == 1
        assert fused[0].tool_name == "tool_a"
        assert fused[0].score > 0.8 / (60 + 1)

    @pytest.mark.anyio
    async def test_trust_level_filter(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm8", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm8_bm25"))
        registry = ToolRegistry()

        trusted = _make_tool("safe_tool", description="A safe tool", trust_level="trusted")
        untrusted = _make_tool("risky_tool", description="A risky tool", trust_level="untrusted")
        registry.register(name=trusted.name, handler=trusted.handler, description=trusted.description, trust_level="trusted")
        registry.register(name=untrusted.name, handler=untrusted.handler, description=untrusted.description, trust_level="untrusted")
        await idx.index_tool(trusted)
        await idx.index_tool(untrusted)

        matcher = ToolMatcher(idx, bm25, registry)
        results = await matcher.find_tools("tool", trust_level="trusted")
        assert all(r.metadata.get("trust_level") == "trusted" for r in results)

    @pytest.mark.anyio
    async def test_empty_query_returns_empty(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm9", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm9_bm25"))
        registry = ToolRegistry()

        matcher = ToolMatcher(idx, bm25, registry)
        results = await matcher.find_tools("anything")
        assert results == []

    @pytest.mark.anyio
    async def test_custom_rrf_k(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm10", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm10_bm25"))
        registry = ToolRegistry()

        matcher = ToolMatcher(idx, bm25, registry, rrf_k=10)
        assert matcher._rrf_k == 10

    @pytest.mark.anyio
    async def test_find_and_rank_skips_disabled(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm11", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm11_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("disabled_tool", description="A disabled tool")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description, is_enabled=False)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        tools = await matcher.find_and_rank("disabled")
        assert len(tools) == 0

    @pytest.mark.anyio
    async def test_find_and_rank_skips_unknown(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="tm12", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "tm12_bm25"))
        registry = ToolRegistry()

        matcher = ToolMatcher(idx, bm25, registry)
        tools = await matcher.find_and_rank("anything")
        assert tools == []
