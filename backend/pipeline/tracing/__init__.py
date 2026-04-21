"""Structured tracing for pipeline observability."""

from backend.pipeline.tracing.processor import (
    CompositeProcessor,
    InMemoryProcessor,
    LoggingProcessor,
    NoOpProcessor,
    TracingProcessor,
    get_composite,
    get_tracer,
    set_tracer,
)
from backend.pipeline.tracing.spans import Span, SpanContext, SpanEvent, SpanKind, create_span

__all__ = [
    "CompositeProcessor",
    "InMemoryProcessor",
    "LoggingProcessor",
    "NoOpProcessor",
    "TracingProcessor",
    "Span",
    "SpanContext",
    "SpanEvent",
    "SpanKind",
    "create_span",
    "get_composite",
    "get_tracer",
    "set_tracer",
]
