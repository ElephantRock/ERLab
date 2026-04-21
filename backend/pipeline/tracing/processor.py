"""TracingProcessor interface and built-in processors.

Provides the TracingProcessor ABC with on_span_start/on_span_end callbacks,
plus NoOp (zero-cost disabled), Logging, and InMemory processors.

Inspired by OpenAI Agents TracingProcessor with NoOp zero-cost mode.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from backend.pipeline.tracing.spans import Span

logger = logging.getLogger(__name__)


class TracingProcessor(ABC):
    """Interface for trace span consumers."""

    @abstractmethod
    def on_span_start(self, span: Span) -> None:
        ...

    @abstractmethod
    def on_span_end(self, span: Span) -> None:
        ...


class NoOpProcessor(TracingProcessor):
    """Zero-cost disabled processor — all methods are no-ops."""

    def on_span_start(self, span: Span) -> None:
        pass

    def on_span_end(self, span: Span) -> None:
        pass


class LoggingProcessor(TracingProcessor):
    """Logs span start/end at INFO level."""

    def on_span_start(self, span: Span) -> None:
        logger.info(
            "SPAN START [%s] %s trace=%s parent=%s",
            span.kind.value, span.name, span.trace_id[:8], span.parent_id[:8] if span.parent_id else "-",
        )

    def on_span_end(self, span: Span) -> None:
        logger.info(
            "SPAN END [%s] %s duration=%.1fms status=%s",
            span.kind.value, span.name, span.duration_ms, span.status,
        )


class InMemoryProcessor(TracingProcessor):
    """Stores all spans in memory. Provides query and summary methods."""

    def __init__(self, max_spans: int = 10000):
        self._spans: list[Span] = []
        self._max_spans = max_spans

    def on_span_start(self, span: Span) -> None:
        pass  # Only track completed spans

    def on_span_end(self, span: Span) -> None:
        if len(self._spans) >= self._max_spans:
            self._spans = self._spans[len(self._spans) // 2:]
        self._spans.append(span)

    def query(self, trace_id: str) -> list[Span]:
        return [s for s in self._spans if s.trace_id == trace_id]

    def query_by_kind(self, kind: str) -> list[Span]:
        return [s for s in self._spans if s.kind.value == kind]

    def summary(self) -> dict[str, Any]:
        if not self._spans:
            return {"span_count": 0, "trace_count": 0}

        trace_ids = {s.trace_id for s in self._spans}
        by_kind: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total_duration = 0.0

        for s in self._spans:
            by_kind[s.kind.value] = by_kind.get(s.kind.value, 0) + 1
            by_status[s.status] = by_status.get(s.status, 0) + 1
            total_duration += s.duration_ms

        return {
            "span_count": len(self._spans),
            "trace_count": len(trace_ids),
            "by_kind": by_kind,
            "by_status": by_status,
            "total_duration_ms": total_duration,
            "avg_duration_ms": total_duration / len(self._spans),
        }

    def clear(self) -> None:
        self._spans.clear()


# ---- Module-level singleton ----

_processor: TracingProcessor = NoOpProcessor()


def get_tracer() -> TracingProcessor:
    return _processor


def set_tracer(processor: TracingProcessor) -> None:
    global _processor
    _processor = processor


def _notify_span_end(span: Span) -> None:
    """Called by SpanContext.__exit__ to notify the processor."""
    _processor.on_span_end(span)
