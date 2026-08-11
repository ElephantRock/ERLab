"""Tests for TwoStageRetriever wiring: rrf_k, retrieval_mode, reranker integration.

Uses sys.modules mock for chromadb to avoid heavy import chain.
"""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# Stub out chromadb before any backend imports
_chromadb = ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock
_chromadb.HttpClient = MagicMock
sys.modules["chromadb"] = _chromadb

from backend.pipeline.knowledge.retriever import RetrievalSource, TwoStageRetriever


class MockVectorStore:
    async def query(self, query_text, n_results=10, filter_metadata=None):
        return [
            {"id": f"vec_{i}", "text": f"semantic result {i}", "distance": 0.1 * i, "metadata": {}}
            for i in range(n_results)
        ]


class MockBM25:
    def query(self, query_text, n_results=10, filter_metadata=None):
        return [
            {"id": f"bm25_{i}", "text": f"keyword result {i}", "score": 10.0 - i, "metadata": {}}
            for i in range(n_results)
        ]


class MockEmbedding:
    pass


def _make_retriever(**kwargs):
    defaults = dict(
        vector_store=MockVectorStore(),
        bm25_index=MockBM25(),
        embedding_service=MockEmbedding(),
    )
    defaults.update(kwargs)
    return TwoStageRetriever(**defaults)


class TestRRF_KConfig:
    def test_default_rrf_k(self):
        r = _make_retriever()
        assert r._default_rrf_k == 60

    def test_custom_rrf_k(self):
        r = _make_retriever(rrf_k=30)
        assert r._default_rrf_k == 30

    def test_rrf_k_fallback_to_default(self):
        r = _make_retriever(rrf_k=42)
        results = asyncio.run(r.retrieve("test", n_results=3))
        assert len(results) > 0

    def test_rrf_k_override_in_retrieve(self):
        r = _make_retriever(rrf_k=42)
        results = asyncio.run(r.retrieve("test", n_results=3, rrf_k=10))
        assert len(results) > 0


class TestRetrievalMode:
    def test_default_mode_is_hybrid(self):
        r = _make_retriever()
        assert r._retrieval_mode == "hybrid"

    def test_custom_mode(self):
        r = _make_retriever(retrieval_mode="semantic")
        assert r._retrieval_mode == "semantic"

    def test_semantic_mode_skips_bm25(self):
        r = _make_retriever(retrieval_mode="semantic")
        results = asyncio.run(r.retrieve("test", n_results=5))
        ids = [res.id for res in results]
        assert all(id.startswith("vec_") for id in ids)
        assert not any(id.startswith("bm25_") for id in ids)

    def test_hybrid_mode_includes_both(self):
        r = _make_retriever(retrieval_mode="hybrid")
        results = asyncio.run(r.retrieve("test", n_results=10))
        ids = [res.id for res in results]
        has_bm25 = any(id.startswith("bm25_") for id in ids)
        has_semantic = any(id.startswith("vec_") for id in ids)
        assert has_bm25 and has_semantic


class TestRerankerWiring:
    def test_no_reranker_by_default(self):
        r = _make_retriever()
        assert r._reranker is None

    def test_reranker_configured(self):
        mock_provider = MagicMock()
        from backend.pipeline.knowledge.reranker import LLMReranker

        reranker = LLMReranker(mock_provider)
        r = _make_retriever(reranker=reranker)
        assert r._reranker is not None

    def test_reranker_invoked_during_retrieve(self):
        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(return_value="0.8")
        from backend.pipeline.knowledge.reranker import LLMReranker

        reranker = LLMReranker(mock_provider)
        r = _make_retriever(reranker=reranker, retrieval_mode="semantic")

        results = asyncio.run(r.retrieve("test query", n_results=3))
        assert mock_provider.complete.called
        assert all(r.source == RetrievalSource.RERANKED for r in results)
