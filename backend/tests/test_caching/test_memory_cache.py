"""Tests for InMemoryCache — LRU, FIFO eviction, TTL expiry."""

import time

from backend.providers.cache.base import CacheEntry
from backend.providers.cache.memory_cache import InMemoryCache
from backend.providers.base import LLMResponse


def _entry(content: str = "test") -> CacheEntry:
    return CacheEntry(response=LLMResponse(content=content), created_at=time.time())


class TestInMemoryCache:
    def test_empty_lookup(self, memory_cache):
        assert memory_cache.lookup("missing") is None

    def test_round_trip(self, memory_cache):
        entry = _entry("hello")
        memory_cache.update("k1", entry)
        result = memory_cache.lookup("k1")
        assert result is not None
        assert result.response.content == "hello"

    def test_fifo_eviction(self):
        cache = InMemoryCache(max_size=3, ttl_seconds=3600)
        for i in range(4):
            cache.update(f"k{i}", _entry(f"v{i}"))
        assert cache.lookup("k0") is None  # evicted
        assert cache.lookup("k3") is not None

    def test_ttl_expiry(self):
        cache = InMemoryCache(max_size=10, ttl_seconds=0)
        cache.update("k1", CacheEntry(
            response=LLMResponse(content="expired"),
            created_at=time.time() - 1,
        ))
        assert cache.lookup("k1") is None

    def test_lru_reorder_saves_entry(self):
        cache = InMemoryCache(max_size=3, ttl_seconds=3600)
        for i in range(3):
            cache.update(f"k{i}", _entry(f"v{i}"))
        # Access k0 to move it to end
        cache.lookup("k0")
        # Insert one more — should evict k1 (oldest untouched), not k0
        cache.update("k4", _entry("v4"))
        assert cache.lookup("k0") is not None
        assert cache.lookup("k1") is None

    def test_clear(self, memory_cache):
        memory_cache.update("k1", _entry())
        memory_cache.clear()
        assert memory_cache.lookup("k1") is None
        assert memory_cache.stats()["hits"] == 0

    def test_stats(self, memory_cache):
        memory_cache.update("k1", _entry())
        memory_cache.lookup("k1")  # hit
        memory_cache.lookup("missing")  # miss
        s = memory_cache.stats()
        assert s["hits"] == 1
        assert s["misses"] == 1
        assert s["size"] == 1
        assert abs(s["hit_rate"] - 0.5) < 0.01
