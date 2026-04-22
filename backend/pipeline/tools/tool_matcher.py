"""Hybrid tool matching — semantic + BM25 keyword search fused via RRF."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.pipeline.tools.tool_index import ToolSearchResult

if TYPE_CHECKING:
    from backend.pipeline.knowledge.bm25_index import BM25Index
    from backend.pipeline.tools.registry import ToolDefinition, ToolRegistry
    from backend.pipeline.tools.tool_index import ToolEmbeddingIndex

logger = logging.getLogger(__name__)


class ToolMatcher:
    """Hybrid tool search combining semantic embeddings and BM25 keyword matching."""

    def __init__(
        self,
        tool_embedding_index: ToolEmbeddingIndex,
        bm25_index: BM25Index,
        registry: ToolRegistry,
        rrf_k: int = 60,
    ) -> None:
        self._index = tool_embedding_index
        self._bm25 = bm25_index
        self._registry = registry
        self._rrf_k = rrf_k

    async def find_tools(
        self,
        capability_description: str,
        n_results: int = 10,
        trust_level: str | None = None,
        source: str | None = None,
    ) -> list[ToolSearchResult]:
        if source == "semantic":
            return await self._index.query(capability_description, n_results, trust_level)

        if source == "keyword":
            return self._keyword_search(capability_description, n_results, trust_level)

        return await self._hybrid_search(capability_description, n_results, trust_level)

    async def find_and_rank(
        self,
        capability_description: str,
        n_results: int = 10,
        min_score: float = 0.0,
    ) -> list[ToolDefinition]:
        results = await self._hybrid_search(capability_description, n_results)
        tools: list[ToolDefinition] = []
        for r in results:
            if r.score < min_score:
                continue
            tool = self._registry.get(r.tool_name)
            if tool and tool.enabled:
                tools.append(tool)
        return tools

    async def refresh_index(self) -> int:
        count = await self._index.index_registry(self._registry)
        self._index_tools_to_bm25()
        return count

    def _index_tools_to_bm25(self) -> None:
        from backend.pipeline.tools.tool_index import ToolEmbeddingIndex

        tools = self._registry.list_tools(enabled_only=True)
        if not tools:
            return

        ids = [t.name for t in tools]
        texts = [ToolEmbeddingIndex._tool_to_text(t) for t in tools]
        metas = [{"trust_level": t.trust_level, "source": t.source} for t in tools]
        self._bm25.add_documents(ids, texts, metas)

    async def _hybrid_search(
        self,
        capability_description: str,
        n_results: int,
        trust_level: str | None = None,
    ) -> list[ToolSearchResult]:
        semantic = await self._index.query(capability_description, n_results * 2, trust_level)
        keyword = self._keyword_search(capability_description, n_results * 2, trust_level)
        return self._rrf_fuse(semantic, keyword, n_results)

    def _keyword_search(
        self,
        query: str,
        n_results: int,
        trust_level: str | None = None,
    ) -> list[ToolSearchResult]:
        filter_meta = {"trust_level": trust_level} if trust_level else None
        raw = self._bm25.query(query, n_results=n_results, filter_metadata=filter_meta)
        return [
            ToolSearchResult(tool_name=r["id"], score=r["score"], source="keyword", metadata=r.get("metadata", {}))
            for r in raw
        ]

    def _rrf_fuse(
        self,
        semantic: list[ToolSearchResult],
        keyword: list[ToolSearchResult],
        n_results: int,
    ) -> list[ToolSearchResult]:
        scores: dict[str, float] = {}
        metas: dict[str, dict[str, Any]] = {}

        for rank, r in enumerate(semantic):
            scores[r.tool_name] = scores.get(r.tool_name, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            metas.setdefault(r.tool_name, r.metadata)

        for rank, r in enumerate(keyword):
            scores[r.tool_name] = scores.get(r.tool_name, 0.0) + 1.0 / (self._rrf_k + rank + 1)
            metas.setdefault(r.tool_name, r.metadata)

        fused = [
            ToolSearchResult(
                tool_name=name,
                score=score,
                source="fused",
                metadata=metas.get(name, {}),
            )
            for name, score in scores.items()
        ]
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused[:n_results]
