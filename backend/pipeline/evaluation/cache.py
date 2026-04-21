"""Content-hash-based LRU cache for evaluation results."""

from __future__ import annotations

from collections import OrderedDict

from backend.pipeline.evaluation.scorer import EvaluationReport


class EvaluationCache:
    """In-memory LRU cache for evaluation results.

    Keyed by SHA-256 hash of (target_content, rubric_criteria).
    """

    def __init__(self, max_size: int = 500) -> None:
        self._cache: OrderedDict[str, EvaluationReport] = OrderedDict()
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> EvaluationReport | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, report: EvaluationReport) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = report
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def invalidate(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def stats(self) -> dict[str, int]:
        return {
            "hits": self._hits,
            "misses": self._misses,
            "size": len(self._cache),
            "max_size": self._max_size,
        }
