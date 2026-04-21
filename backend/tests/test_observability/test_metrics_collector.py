"""Tests for MetricsCollector — p50/p95/p99, error rates."""

from backend.pipeline.observability.metrics import MetricsCollector
from backend.pipeline.tracing.spans import Span, SpanKind


def _make_span(kind=SpanKind.STAGE, name="test", duration_ms=100.0, status="ok"):
    span = Span(kind=kind, name=name)
    span.start_time = 0.0
    span.end_time = duration_ms / 1000.0
    span.status = status
    return span


class TestMetricsCollector:
    def test_empty_snapshot(self):
        m = MetricsCollector()
        assert m.snapshot() == {}

    def test_single_span(self):
        m = MetricsCollector()
        m.on_span_end(_make_span(duration_ms=200.0))
        snap = m.snapshot()
        assert "stage" in snap
        assert snap["stage"]["count"] == 1
        assert snap["stage"]["errors"] == 0
        assert snap["stage"]["latency_ms"]["avg"] == 200.0

    def test_percentiles(self):
        m = MetricsCollector()
        for d in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            m.on_span_end(_make_span(duration_ms=float(d)))
        snap = m.snapshot()
        lat = snap["stage"]["latency_ms"]
        assert lat["p50"] == 55.0  # linear interpolation: 50*0.5 + 60*0.5
        assert lat["p95"] == 95.5
        assert lat["p99"] == 99.1

    def test_error_rate(self):
        m = MetricsCollector()
        m.on_span_end(_make_span(status="ok"))
        m.on_span_end(_make_span(status="error"))
        m.on_span_end(_make_span(status="ok"))
        snap = m.snapshot()
        assert snap["stage"]["count"] == 3
        assert snap["stage"]["errors"] == 1
        assert abs(snap["stage"]["error_rate"] - 1/3) < 0.01

    def test_multiple_kinds(self):
        m = MetricsCollector()
        m.on_span_end(_make_span(kind=SpanKind.TOOL, duration_ms=50.0))
        m.on_span_end(_make_span(kind=SpanKind.LLM_CALL, duration_ms=200.0))
        snap = m.snapshot()
        assert "tool" in snap
        assert "llm_call" in snap
        assert snap["tool"]["count"] == 1
        assert snap["llm_call"]["count"] == 1

    def test_on_span_start_noop(self):
        m = MetricsCollector()
        m.on_span_start(_make_span())
        assert m.snapshot() == {}
