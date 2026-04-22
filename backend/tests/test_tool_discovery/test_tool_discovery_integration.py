"""Integration tests for tool discovery — end-to-end find and score."""

import pytest

from backend.pipeline.knowledge.bm25_index import BM25Index
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.tools.registry import ToolDefinition, ToolRegistry
from backend.pipeline.tools.tool_index import ToolEmbeddingIndex
from backend.pipeline.tools.tool_matcher import ToolMatcher
from backend.pipeline.tools.tool_scoring import ToolScorer


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


@pytest.fixture
def embedding_service():
    return EmbeddingService(FakeEmbeddingProvider(dimension=10))


def _make_tool(name: str, description: str, trust_level: str = "trusted") -> ToolDefinition:
    async def handler(**kwargs):
        return "ok"

    return ToolDefinition(
        name=name,
        description=description,
        parameters={},
        handler=handler,
        trust_level=trust_level,
    )


class TestToolDiscoveryIntegration:
    @pytest.mark.anyio
    async def test_end_to_end_find_and_score(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int1", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "int1_bm25"))
        registry = ToolRegistry()

        tools = [
            _make_tool("search_papers", "Search academic papers by keyword"),
            _make_tool("calculate_metrics", "Calculate precision recall F1 metrics"),
            _make_tool("generate_summary", "Generate a summary of research findings"),
        ]
        for t in tools:
            registry.register(name=t.name, handler=t.handler, description=t.description, trust_level=t.trust_level)
            await idx.index_tool(t)

        matcher = ToolMatcher(idx, bm25, registry)
        matcher._index_tools_to_bm25()

        results = await matcher.find_tools("find papers about transformers")
        assert len(results) >= 1

        scorer = ToolScorer()
        tool_map = {t.name: t for t in tools}
        scores = scorer.score(results, tool_map)
        assert len(scores) >= 1
        assert scores[0].composite > 0

    @pytest.mark.anyio
    async def test_mcp_auto_indexing(self, embedding_service, chroma_client):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int2", client=chroma_client)

        tool = _make_tool("mcp__server__search", "MCP search tool", trust_level="untrusted")
        await idx.index_tool(tool)

        results = await idx.query("search", n_results=5)
        assert len(results) >= 1
        assert results[0].tool_name == "mcp__server__search"

    @pytest.mark.anyio
    async def test_refresh_reindexes_all(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int3", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "int3_bm25"))
        registry = ToolRegistry()

        registry.register(name="tool_a", handler=lambda: None, description="First tool")
        matcher = ToolMatcher(idx, bm25, registry)
        count = await matcher.refresh_index()
        assert count == 1

        registry.register(name="tool_b", handler=lambda: None, description="Second tool")
        count = await matcher.refresh_index()
        assert count == 2

    @pytest.mark.anyio
    async def test_discover_with_trust_filter_then_score(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int4", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "int4_bm25"))
        registry = ToolRegistry()

        trusted = _make_tool("safe_search", "Safe search tool", trust_level="trusted")
        untrusted = _make_tool("risky_search", "Risky search tool", trust_level="untrusted")
        registry.register(name=trusted.name, handler=trusted.handler, description=trusted.description, trust_level="trusted")
        registry.register(name=untrusted.name, handler=untrusted.handler, description=untrusted.description, trust_level="untrusted")
        await idx.index_tool(trusted)
        await idx.index_tool(untrusted)

        matcher = ToolMatcher(idx, bm25, registry)

        all_results = await matcher.find_tools("search tool")
        assert len(all_results) >= 2

        scorer = ToolScorer(trust_penalty=0.3)
        tool_map = {trusted.name: trusted, untrusted.name: untrusted}
        scores = scorer.score(all_results, tool_map)
        trusted_score = next(s for s in scores if s.tool_name == "safe_search")
        untrusted_score = next(s for s in scores if s.tool_name == "risky_search")
        assert trusted_score.trust_penalty == 0.0
        assert untrusted_score.trust_penalty == 0.3

    @pytest.mark.anyio
    async def test_full_pipeline_empty_registry(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int5", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "int5_bm25"))
        registry = ToolRegistry()

        matcher = ToolMatcher(idx, bm25, registry)
        results = await matcher.find_tools("anything")
        assert results == []

        scorer = ToolScorer()
        scores = scorer.score(results, {})
        assert scores == []

    @pytest.mark.anyio
    async def test_find_and_rank_full_workflow(self, embedding_service, chroma_client, tmp_path):
        idx = ToolEmbeddingIndex(".", embedding_service, collection_name="int6", client=chroma_client)
        bm25 = BM25Index(str(tmp_path / "int6_bm25"))
        registry = ToolRegistry()

        tool = _make_tool("paper_search", "Search for academic papers on a topic")
        registry.register(name=tool.name, handler=tool.handler, description=tool.description)
        await idx.index_tool(tool)

        matcher = ToolMatcher(idx, bm25, registry)
        matcher._index_tools_to_bm25()

        tools = await matcher.find_and_rank("find papers about NLP", n_results=5)
        assert len(tools) >= 1
        assert tools[0].name == "paper_search"
