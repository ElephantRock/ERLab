"""TracingProcessor interface and built-in processors.

Provides the TracingProcessor ABC with on_span_start/on_span_end callbacks,
plus NoOp (zero-cost disabled), Logging, and InMemory processors.

Inspired by OpenAI Agents TracingProcessor with NoOp zero-cost mode.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
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

    #: A trace whose most recent span ended within this window counts as
    #: "active" in summary(). Spans are only recorded on completion, so
    #: activity is the honest proxy for in-flight work.
    ACTIVE_WINDOW_SECONDS = 300.0

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

    def summary(self, recent_limit: int = 50) -> dict[str, Any]:
        """Summarize stored spans across traces.

        Returns the contract documented by /api/v1/traces/summary —
        ``total_traces``, ``active_traces``, ``error_rate``, plus
        ``recent_traces`` carrying REAL trace ids for the viewer — alongside
        the legacy aggregate keys (span_count, trace_count, by_kind,
        by_status, total_duration_ms, avg_duration_ms) preserved for
        existing consumers.
        """
        if not self._spans:
            return {
                "span_count": 0,
                "trace_count": 0,
                "total_traces": 0,
                "active_traces": 0,
                "error_rate": 0.0,
                "recent_traces": [],
                "by_kind": {},
                "by_status": {},
                "total_duration_ms": 0.0,
                "avg_duration_ms": 0.0,
            }

        traces: dict[str, list[Span]] = {}
        by_kind: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total_duration = 0.0

        for s in self._spans:
            traces.setdefault(s.trace_id, []).append(s)
            by_kind[s.kind.value] = by_kind.get(s.kind.value, 0) + 1
            by_status[s.status] = by_status.get(s.status, 0) + 1
            total_duration += s.duration_ms

        now = time.time()
        error_spans = 0
        active_traces = 0
        recent: list[dict[str, Any]] = []
        for tid, spans in traces.items():
            for s in spans:
                if s.status == "error":
                    error_spans += 1
            started_at = min(s.start_time for s in spans)
            last_activity = max(s.end_time for s in spans)
            models: set[str] = set()
            for s in spans:
                attr_models = s.attributes.get("models")
                if isinstance(attr_models, list):
                    models.update(m for m in attr_models if isinstance(m, str))
            recent.append(
                {
                    "trace_id": tid,
                    "span_count": len(spans),
                    "started_at": started_at,
                    "last_activity": last_activity,
                    "duration_ms": max(0.0, (last_activity - started_at) * 1000),
                    "error_count": sum(1 for s in spans if s.status == "error"),
                    "models": sorted(models),
                }
            )
            if now - last_activity <= self.ACTIVE_WINDOW_SECONDS:
                active_traces += 1

        recent.sort(key=lambda r: r["last_activity"], reverse=True)

        return {
            "span_count": len(self._spans),
            "trace_count": len(traces),
            "total_traces": len(traces),
            "active_traces": active_traces,
            "error_rate": error_spans / len(self._spans),
            "recent_traces": recent[:recent_limit],
            "by_kind": by_kind,
            "by_status": by_status,
            "total_duration_ms": total_duration,
            "avg_duration_ms": total_duration / len(self._spans),
        }

    def clear(self) -> None:
        self._spans.clear()


class CompositeProcessor(TracingProcessor):
    """Fan-out processor that delegates to N sub-processors."""

    def __init__(self, processors: list[TracingProcessor] | None = None):
        self._processors: list[TracingProcessor] = list(processors or [])

    def add(self, processor: TracingProcessor) -> None:
        self._processors.append(processor)

    def remove(self, processor_type: type) -> None:
        self._processors = [p for p in self._processors if not isinstance(p, processor_type)]

    def get(self, processor_type: type) -> TracingProcessor | None:
        for p in self._processors:
            if isinstance(p, processor_type):
                return p
        return None

    @property
    def processors(self) -> list[TracingProcessor]:
        return list(self._processors)

    def on_span_start(self, span: Span) -> None:
        for p in self._processors:
            try:
                p.on_span_start(span)
            except Exception:
                logger.exception("Processor %s failed in on_span_start", type(p).__name__)

    def on_span_end(self, span: Span) -> None:
        for p in self._processors:
            try:
                p.on_span_end(span)
            except Exception:
                logger.exception("Processor %s failed in on_span_end", type(p).__name__)


# ---- Module-level singleton ----

_processor: TracingProcessor = CompositeProcessor()


def get_tracer() -> TracingProcessor:
    return _processor


def set_tracer(processor: TracingProcessor) -> None:
    global _processor
    _processor = processor


def get_composite() -> CompositeProcessor:
    """Return the global processor as CompositeProcessor, wrapping if needed."""
    global _processor
    if isinstance(_processor, CompositeProcessor):
        return _processor
    composite = CompositeProcessor([_processor])
    _processor = composite
    return composite


def _notify_span_start(span: Span) -> None:
    """Called by SpanContext.__enter__ to notify the processor."""
    _processor.on_span_start(span)


def _notify_span_end(span: Span) -> None:
    """Called by SpanContext.__exit__ to notify the processor."""
    _processor.on_span_end(span)
