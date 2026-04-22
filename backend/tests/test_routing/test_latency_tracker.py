"""Tests for LatencyTracker — recording, averaging, percentiles."""

from backend.providers.routing.latency_tracker import LatencyTracker


class TestLatencyTracker:
    def test_empty_returns_zero(self):
        lt = LatencyTracker()
        assert lt.avg_latency("unknown") == 0.0
        assert lt.p50("unknown") == 0.0
        assert lt.count("unknown") == 0

    def test_record_and_avg(self):
        lt = LatencyTracker()
        lt.record("openai", 100.0)
        lt.record("openai", 200.0)
        assert lt.avg_latency("openai") == 150.0

    def test_p50(self):
        lt = LatencyTracker()
        for v in [10, 20, 30, 40, 50]:
            lt.record("test", float(v))
        assert lt.p50("test") == 30.0

    def test_count(self):
        lt = LatencyTracker()
        lt.record("openai", 100.0)
        lt.record("openai", 200.0)
        assert lt.count("openai") == 2

    def test_rolling_window(self):
        lt = LatencyTracker(window_size=3)
        for v in [10, 20, 30, 40]:
            lt.record("test", float(v))
        assert lt.count("test") == 3
        assert lt.avg_latency("test") == 30.0  # (20+30+40)/3

    def test_snapshot(self):
        lt = LatencyTracker()
        lt.record("openai", 100.0)
        lt.record("anthropic", 200.0)
        snap = lt.snapshot()
        assert "openai" in snap
        assert "anthropic" in snap
        assert snap["openai"]["avg_ms"] == 100.0
        assert snap["openai"]["count"] == 1

    def test_separate_providers(self):
        lt = LatencyTracker()
        lt.record("openai", 100.0)
        lt.record("anthropic", 500.0)
        assert lt.avg_latency("openai") == 100.0
        assert lt.avg_latency("anthropic") == 500.0
