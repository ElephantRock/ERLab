"""In-memory LRU cache with TTL expiry and FIFO eviction."""

from __future__ import annotations

import time
from collections import OrderedDict

from backend.providers.cache.base import CacheEntry


class InMemoryCache:
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def lookup(self, key: str) -> CacheEntry | None:
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() - entry.created_at > self._ttl_seconds:
            self._cache.pop(key, None)
            self._misses += 1
            return None
        self._cache.move_to_end(key)
        self._hits += 1
        return entry

    def update(self, key: str, entry: CacheEntry) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = entry
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict[str, int | float]:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self._max_size,
            "hit_rate": self._hits / max(1, total),
        }
