"""Tests for SemanticCache — similarity lookup, TTL, persistence."""

import json
import math
import time

import pytest

from backend.providers.cache.base import CacheEntry
from backend.providers.cache.semantic_cache import SemanticCache
from backend.providers.base import LLMResponse


class FakeEmbeddingService:
    """Returns deterministic embeddings based on text content."""

    def __init__(self, dimension: int = 10):
        self._dimension = dimension
        self._calls: list[str] = []

    async def embed_single(self, text: str) -> list[float]:
        self._calls.append(text)
        # Deterministic: hash each char to a float
        vec = [0.0] * self._dimension
        for i, c in enumerate(text):
            vec[i % self._dimension] += ord(c) * 0.01
        # Normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    @property
    def dimension(self) -> int:
        return self._dimension


@pytest.fixture
def embedding_service():
    return FakeEmbeddingService()


@pytest.fixture
def semantic_cache(embedding_service, tmp_path):
    try:
        cache = SemanticCache(
            embedding_service=embedding_service,
            persist_dir=str(tmp_path / "chroma_cache"),
            similarity_threshold=0.90,
            ttl_seconds=3600,
            max_size=10,
        )
    except ImportError:
        pytest.skip("ChromaDB not fully available")
        return
    return cache


@pytest.mark.anyio
class TestSemanticCache:
    async def test_empty_lookup(self, semantic_cache):
        result = await semantic_cache.lookup_similar("anything")
        assert result is None

    async def test_round_trip(self, semantic_cache):
        resp = LLMResponse(content="cached answer")
        await semantic_cache.update_similar(
            "test query",
            CacheEntry(response=resp, created_at=time.time()),
        )
        result = await semantic_cache.lookup_similar("test query")
        assert result is not None
        assert result.response.content == "cached answer"

    async def test_similar_match(self, semantic_cache):
        resp = LLMResponse(content="answer")
        await semantic_cache.update_similar(
            "machine learning for NLP tasks",
            CacheEntry(response=resp, created_at=time.time()),
        )
        # Same text = exact vector = should match
        result = await semantic_cache.lookup_similar("machine learning for NLP tasks")
        assert result is not None

    async def test_below_threshold(self, embedding_service, tmp_path):
        try:
            cache = SemanticCache(
                embedding_service=embedding_service,
                persist_dir=str(tmp_path / "chroma_strict"),
                similarity_threshold=0.9999,
                ttl_seconds=3600,
            )
        except ImportError:
            pytest.skip("ChromaDB not fully available")
        await cache.update_similar(
            "alpha",
            CacheEntry(response=LLMResponse(content="a"), created_at=time.time()),
        )
        # "beta" produces a different vector, unlikely to reach 0.9999 similarity
        result = await cache.lookup_similar("beta")
        assert result is None

    async def test_ttl_expiry(self, embedding_service, tmp_path):
        try:
            cache = SemanticCache(
                embedding_service=embedding_service,
                persist_dir=str(tmp_path / "chroma_ttl"),
                similarity_threshold=0.90,
                ttl_seconds=0,
            )
        except ImportError:
            pytest.skip("ChromaDB not fully available")
        await cache.update_similar(
            "expiring",
            CacheEntry(
                response=LLMResponse(content="old"),
                created_at=time.time() - 1,
            ),
        )
        result = await cache.lookup_similar("expiring")
        assert result is None

    async def test_clear(self, semantic_cache):
        await semantic_cache.update_similar(
            "x",
            CacheEntry(response=LLMResponse(content="y"), created_at=time.time()),
        )
        semantic_cache.clear()
        assert semantic_cache.stats()["size"] == 0
        assert semantic_cache.stats()["chroma_count"] == 0

    async def test_stats(self, semantic_cache):
        await semantic_cache.update_similar(
            "q1",
            CacheEntry(response=LLMResponse(content="a1"), created_at=time.time()),
        )
        await semantic_cache.lookup_similar("q1")  # hit
        await semantic_cache.lookup_similar("missing")  # miss
        s = semantic_cache.stats()
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["size"] == 1

    async def test_persistence(self, embedding_service, tmp_path):
        """Cache survives process restart (re-created from same dir)."""
        dir_path = str(tmp_path / "chroma_persist")
        try:
            cache1 = SemanticCache(
                embedding_service=embedding_service,
                persist_dir=dir_path,
                similarity_threshold=0.90,
                ttl_seconds=3600,
            )
        except ImportError:
            pytest.skip("ChromaDB not fully available")
        await cache1.update_similar(
            "persist test",
            CacheEntry(response=LLMResponse(content="persisted"), created_at=time.time()),
        )
        # Simulate restart: create new instance pointing to same dir
        try:
            cache2 = SemanticCache(
                embedding_service=embedding_service,
                persist_dir=dir_path,
                similarity_threshold=0.90,
                ttl_seconds=3600,
            )
        except ImportError:
            pytest.skip("ChromaDB not fully available")
        # ChromaDB vectors persist, but timestamps are in-memory only,
        # so we can't do a TTL check — just verify chroma_count
        assert cache2.stats()["chroma_count"] >= 1
