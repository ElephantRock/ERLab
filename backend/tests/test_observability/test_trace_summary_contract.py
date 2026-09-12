"""Contract tests for the trace observability surfaces.

Guards the shapes consumed by the frontend trace viewer:
  - InMemoryProcessor.summary() — documented /traces/summary contract
    (total_traces, active_traces, error_rate, recent_traces with REAL
    trace ids) plus the legacy aggregate keys.
  - _CostLinkingProcessor — stamps models/providers from cost events
    onto span attributes (per-stage model attribution).
  - MetricsCollector.flat_snapshot() — documented /traces/metrics flat
    aggregate with the per-kind breakdown under by_kind.
"""

import time

from backend.pipeline.observability.manager import _CostLinkingProcessor
from backend.pipeline.observability.metrics import MetricsCollector
from backend.pipeline.tracing.processor import InMemoryProcessor
from backend.pipeline.tracing.spans import Span, SpanKind


def _make_span(
    trace_id: str,
    name: str,
    *,
    status: str = "ok",
    start: float | None = None,
    end: float | None = None,
    attributes: dict | None = None,
) -> Span:
    span = Span(trace_id=trace_id, kind=SpanKind.STAGE, name=name, attributes=attributes or {})
    now = time.time()
    span.start_time = start if start is not None else now - 1.0
    span.end_time = end if end is not None else now
    span.status = status
    return span


class TestSummaryContract:
    def test_empty_store_returns_documented_zero_shape(self):
        summary = InMemoryProcessor().summary()
        assert summary["total_traces"] == 0
        assert summary["active_traces"] == 0
        assert summary["error_rate"] == 0.0
        assert summary["recent_traces"] == []
        # Legacy keys preserved.
        assert summary["span_count"] == 0
        assert summary["trace_count"] == 0

    def test_documented_fields_present_with_spans(self):
        proc = InMemoryProcessor()
        for i in range(3):
            proc.on_span_end(_make_span(f"t{i}", f"stage-{i}"))
        summary = proc.summary()
        assert summary["total_traces"] == 3
        assert summary["trace_count"] == 3
        assert summary["span_count"] == 3
        assert 0.0 <= summary["error_rate"] <= 1.0
        assert len(summary["recent_traces"]) == 3
        for record in summary["recent_traces"]:
            assert isinstance(record["trace_id"], str) and record["trace_id"]
            assert record["span_count"] == 1
            assert record["duration_ms"] >= 0.0
            assert record["error_count"] == 0
            assert record["models"] == []

    def test_error_rate_counts_error_spans(self):
        proc = InMemoryProcessor()
        proc.on_span_end(_make_span("t1", "ok-stage"))
        proc.on_span_end(_make_span("t2", "bad-stage", status="error"))
        summary = proc.summary()
        assert summary["error_rate"] == 0.5
        by_id = {r["trace_id"]: r for r in summary["recent_traces"]}
        bad = [r for r in summary["recent_traces"] if r["error_count"] == 1]
        assert len(bad) == 1
        assert by_id  # recent_traces keyed by real trace ids
        assert all(r["trace_id"] for r in summary["recent_traces"])

    def test_recent_traces_newest_first(self):
        proc = InMemoryProcessor()
        now = time.time()
        proc.on_span_end(_make_span("old", "old-stage", start=now - 100, end=now - 90))
        proc.on_span_end(_make_span("new", "new-stage", start=now - 2, end=now - 1))
        recent = proc.summary()["recent_traces"]
        assert [r["trace_id"] for r in recent] == ["new", "old"]

    def test_active_window_counts_recent_activity_only(self):
        proc = InMemoryProcessor()
        now = time.time()
        proc.on_span_end(_make_span("fresh", "s", start=now - 2, end=now - 1))
        proc.on_span_end(
            _make_span("stale", "s", start=now - 10_000, end=now - 9_000)
        )
        summary = proc.summary()
        assert summary["total_traces"] == 2
        assert summary["active_traces"] == 1

    def test_recent_limit_bounds_list(self):
        proc = InMemoryProcessor()
        for i in range(10):
            proc.on_span_end(_make_span(f"t{i}", "s"))
        assert len(proc.summary(recent_limit=3)["recent_traces"]) == 3
        assert proc.summary()["total_traces"] == 10

    def test_models_collected_from_span_attributes(self):
        proc = InMemoryProcessor()
        proc.on_span_end(
            _make_span("t1", "stage", attributes={"models": ["glm-5.2", "gpt-x"], "providers": ["openai"]})
        )
        record = proc.summary()["recent_traces"][0]
        assert record["models"] == ["glm-5.2", "gpt-x"]


class _FakeTracker:
    def __init__(self, events):
        self._events = events

    def events_in_range(self, start: float, end: float):
        return [e for e in self._events if start <= e.timestamp.timestamp() <= end]


class TestCostLinkingModelAttribution:
    def test_stamps_models_and_providers_on_span(self):
        from backend.providers.base import CostEvent

        tracker = _FakeTracker(
            [
                CostEvent(provider="openai", model="glm-5.2", input_tokens=10, output_tokens=5, cost_usd=0.01),
                CostEvent(provider="lmstudio", model="bge-m3", input_tokens=3, output_tokens=1, cost_usd=0.0),
            ]
        )
        linker = _CostLinkingProcessor(tracker)
        span = _make_span("t1", "stage")
        linker.on_span_end(span)
        assert span.attributes["models"] == ["bge-m3", "glm-5.2"]
        assert span.attributes["providers"] == ["lmstudio", "openai"]
        assert span.cost_usd == 0.01
        assert span.token_count == 19

    def test_no_events_leaves_span_unstamped(self):
        linker = _CostLinkingProcessor(_FakeTracker([]))
        span = _make_span("t1", "stage")
        linker.on_span_end(span)
        assert "models" not in span.attributes
        assert span.cost_usd is None


class TestFlatMetrics:
    def test_zero_shape_when_no_spans(self):
        snap = MetricsCollector().flat_snapshot()
        assert snap["call_count"] == 0
        assert snap["p50_ms"] == 0.0
        assert snap["p99_ms"] == 0.0
        assert snap["error_rate"] == 0.0
        assert snap["by_kind"] == {}

    def test_aggregates_across_kinds(self):
        collector = MetricsCollector()

        def span(kind: SpanKind, name: str, status: str = "ok"):
            s = Span(trace_id="t", kind=kind, name=name)
            s.start_time = time.time() - 0.01
            s.end_time = time.time()
            s.status = status
            return s

        collector.on_span_end(span(SpanKind.STAGE, "a"))
        collector.on_span_end(span(SpanKind.LLM_CALL, "b", status="error"))
        flat = collector.flat_snapshot()
        assert flat["call_count"] == 2
        assert flat["error_rate"] == 0.5
        assert set(flat["by_kind"].keys()) == {"stage", "llm_call"}
        for key in ("p50_ms", "p95_ms", "p99_ms", "avg_ms"):
            assert isinstance(flat[key], float)
