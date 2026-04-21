"""Tests for CompositeProcessor — fan-out, exception isolation, add/remove."""

from backend.pipeline.tracing.processor import (
    CompositeProcessor,
    InMemoryProcessor,
    LoggingProcessor,
    NoOpProcessor,
)
from backend.pipeline.tracing.spans import Span, SpanKind


def _make_span(name="test", kind=SpanKind.STAGE):
    return Span(kind=kind, name=name)


class TestCompositeProcessor:
    def test_fan_out_on_span_start(self):
        received = []
        class Spy:
            def on_span_start(self, span):
                received.append(("start", span.name))
            def on_span_end(self, span):
                received.append(("end", span.name))

        c = CompositeProcessor([Spy(), Spy()])
        span = _make_span("hello")
        c.on_span_start(span)
        assert len(received) == 2
        assert all(r == ("start", "hello") for r in received)

    def test_fan_out_on_span_end(self):
        received = []
        class Spy:
            def on_span_start(self, span): pass
            def on_span_end(self, span):
                received.append(span.name)

        c = CompositeProcessor([Spy(), Spy(), Spy()])
        c.on_span_end(_make_span("x"))
        assert len(received) == 3

    def test_exception_isolation(self):
        class Failing:
            def on_span_start(self, span): raise RuntimeError("boom")
            def on_span_end(self, span): raise RuntimeError("boom")

        ok_received = []
        class Ok:
            def on_span_start(self, span): ok_received.append("start")
            def on_span_end(self, span): ok_received.append("end")

        c = CompositeProcessor([Failing(), Ok()])
        c.on_span_start(_make_span())
        c.on_span_end(_make_span())
        assert ok_received == ["start", "end"]

    def test_add_remove(self):
        c = CompositeProcessor()
        mem = InMemoryProcessor()
        c.add(mem)
        assert c.get(InMemoryProcessor) is mem
        c.remove(InMemoryProcessor)
        assert c.get(InMemoryProcessor) is None

    def test_processors_property(self):
        c = CompositeProcessor([NoOpProcessor()])
        assert len(c.processors) == 1
        # Returns a copy
        c.processors.append(NoOpProcessor())
        assert len(c.processors) == 1

    def test_empty_composite_noop(self):
        c = CompositeProcessor()
        c.on_span_start(_make_span())
        c.on_span_end(_make_span())
        # No exceptions — that's the test
