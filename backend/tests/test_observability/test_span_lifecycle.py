"""Tests for span lifecycle — on_span_start fires on enter, on_span_end on exit."""

import time

from backend.pipeline.tracing.processor import CompositeProcessor, InMemoryProcessor, set_tracer
from backend.pipeline.tracing.spans import SpanKind, create_span


class TestSpanLifecycle:
    def test_on_span_start_fires(self):
        starts = []
        class Spy(InMemoryProcessor):
            def on_span_start(self, span):
                starts.append(span.name)

        c = CompositeProcessor([Spy()])
        set_tracer(c)
        with create_span(SpanKind.STAGE, "test_stage") as span:
            assert len(starts) == 1
            assert starts[0] == "test_stage"

    def test_on_span_end_fires(self):
        ends = []
        class Spy(InMemoryProcessor):
            def on_span_end(self, span):
                ends.append(span.name)

        c = CompositeProcessor([Spy()])
        set_tracer(c)
        with create_span(SpanKind.STAGE, "end_test") as span:
            assert len(ends) == 0
        assert len(ends) == 1
        assert ends[0] == "end_test"

    def test_all_span_kinds(self):
        mem = InMemoryProcessor()
        set_tracer(CompositeProcessor([mem]))

        for kind in SpanKind:
            with create_span(kind, f"test_{kind.value}"):
                pass

        assert mem.summary()["span_count"] == len(SpanKind)

    def test_span_duration(self):
        set_tracer(CompositeProcessor())
        import time
        with create_span(SpanKind.TOOL, "slow") as span:
            time.sleep(0.01)
        assert span.duration_ms > 5

    def test_span_error_status(self):
        mem = InMemoryProcessor()
        set_tracer(CompositeProcessor([mem]))
        try:
            with create_span(SpanKind.STAGE, "fail") as span:
                raise ValueError("oops")
        except ValueError:
            pass
        spans = mem.query_by_kind("stage")
        assert len(spans) == 1
        assert spans[0].status == "error"

    def test_span_to_dict(self):
        set_tracer(CompositeProcessor())
        with create_span(SpanKind.LLM_CALL, "test", model="gpt-4") as span:
            span.cost_usd = 0.05
            span.token_count = 100
            time.sleep(0.01)
        d = span.to_dict()
        assert d["kind"] == "llm_call"
        assert d["name"] == "test"
        assert d["cost_usd"] == 0.05
        assert d["token_count"] == 100
        assert d["duration_ms"] > 0

    def test_parent_child_propagation(self):
        mem = InMemoryProcessor()
        set_tracer(CompositeProcessor([mem]))
        with create_span(SpanKind.PIPELINE, "root") as parent:
            with create_span(SpanKind.STAGE, "child") as child:
                pass
        assert child.parent_id == parent.span_id
        assert child.trace_id == parent.trace_id
