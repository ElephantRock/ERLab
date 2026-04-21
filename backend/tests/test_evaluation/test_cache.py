"""Tests for the evaluation LRU cache."""

from backend.pipeline.evaluation.cache import EvaluationCache
from backend.pipeline.evaluation.scorer import EvaluationReport, ScoreDimension, ScoreResult


def _make_report(score: float) -> EvaluationReport:
    return EvaluationReport(
        target_id="test",
        scores=[ScoreResult(dimension=ScoreDimension.NOVELTY, score=score)],
        overall_score=score,
    )


class TestEvaluationCache:
    def test_put_and_get(self):
        cache = EvaluationCache(max_size=10)
        report = _make_report(0.8)
        cache.put("key1", report)
        assert cache.get("key1") is not None
        assert cache.get("key1").overall_score == 0.8

    def test_miss_returns_none(self):
        cache = EvaluationCache()
        assert cache.get("nonexistent") is None

    def test_lru_eviction(self):
        cache = EvaluationCache(max_size=3)
        for i in range(5):
            cache.put(f"key{i}", _make_report(float(i)))
        # First 2 should be evicted
        assert cache.get("key0") is None
        assert cache.get("key1") is None
        assert cache.get("key4") is not None

    def test_stats(self):
        cache = EvaluationCache()
        cache.put("k1", _make_report(0.5))
        cache.get("k1")   # hit
        cache.get("k1")   # hit
        cache.get("miss")  # miss
        stats = cache.stats
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_invalidate(self):
        cache = EvaluationCache()
        cache.put("k1", _make_report(0.5))
        cache.invalidate("k1")
        assert cache.get("k1") is None

    def test_clear(self):
        cache = EvaluationCache()
        cache.put("k1", _make_report(0.5))
        cache.clear()
        assert cache.stats["size"] == 0
        assert cache.stats["hits"] == 0
