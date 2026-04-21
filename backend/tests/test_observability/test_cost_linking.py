"""Tests for cost-per-span linking via _CostLinkingProcessor."""

import time
from datetime import datetime, timezone

from backend.pipeline.observability.manager import _CostLinkingProcessor
from backend.pipeline.tracing.spans import Span, SpanKind


def _make_cost_event(ts, cost_usd=0.01, tokens=100):
    from backend.providers.base import CostEvent
    return CostEvent(
        provider="openai",
        model="gpt-4o",
        input_tokens=tokens // 2,
        output_tokens=tokens // 2,
        cost_usd=cost_usd,
        stage="test",
        run_id="r1",
        timestamp=ts,
    )


class FakeCostTracker:
    def __init__(self, events):
        self._events = events

    def events_in_range(self, start, end):
        return [
            e for e in self._events
            if start <= e.timestamp.timestamp() <= end
        ]


class TestCostLinking:
    def test_attaches_cost_to_span(self):
        now = time.time()
        tracker = FakeCostTracker([_make_cost_event(datetime.fromtimestamp(now + 0.01, tz=timezone.utc))])
        linker = _CostLinkingProcessor(tracker)

        span = Span(kind=SpanKind.LLM_CALL, name="test")
        span.start_time = now
        span.end_time = now + 0.1
        linker.on_span_end(span)

        assert span.cost_usd == 0.01
        assert span.token_count == 100

    def test_no_cost_outside_range(self):
        now = time.time()
        tracker = FakeCostTracker([_make_cost_event(datetime.fromtimestamp(now - 10, tz=timezone.utc))])
        linker = _CostLinkingProcessor(tracker)

        span = Span(kind=SpanKind.STAGE, name="test")
        span.start_time = now
        span.end_time = now + 1.0
        linker.on_span_end(span)

        assert span.cost_usd is None
        assert span.token_count is None

    def test_multiple_events_summed(self):
        now = time.time()
        events = [
            _make_cost_event(datetime.fromtimestamp(now + 0.01, tz=timezone.utc), cost_usd=0.02, tokens=50),
            _make_cost_event(datetime.fromtimestamp(now + 0.02, tz=timezone.utc), cost_usd=0.03, tokens=75),
        ]
        tracker = FakeCostTracker(events)
        linker = _CostLinkingProcessor(tracker)

        span = Span(kind=SpanKind.LLM_CALL, name="multi")
        span.start_time = now
        span.end_time = now + 0.1
        linker.on_span_end(span)

        assert span.cost_usd == 0.05
        assert span.token_count == 124  # 50//2*2 + 75//2*2 = 50 + 74
