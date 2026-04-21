"""Span hierarchy for structured tracing.

Provides Span, SpanKind, and contextvars-based trace propagation.
Each span tracks kind, name, timing, status, and attributes.

Inspired by OpenAI Agents tracing with 12 span types.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SpanKind(str, Enum):
    PIPELINE = "pipeline"
    STAGE = "stage"
    AGENT = "agent"
    TOOL = "tool"
    LLM_CALL = "llm_call"
    RETRIEVAL = "retrieval"


@dataclass
class SpanEvent:
    """An event within a span (e.g., tool call, LLM response)."""
    name: str
    timestamp: float = field(default_factory=time.time)
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """A single trace span with timing and attributes."""
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    trace_id: str = ""
    parent_id: str | None = None
    kind: SpanKind = SpanKind.STAGE
    name: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "ok"  # ok, error, skipped
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    cost_usd: float | None = None
    token_count: int | None = None

    @property
    def duration_ms(self) -> float:
        if self.end_time > self.start_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def add_event(self, name: str, **attributes: Any) -> None:
        self.events.append(SpanEvent(name=name, attributes=attributes))

    def set_status(self, status: str) -> None:
        self.status = status

    def end(self) -> None:
        if not self.end_time:
            self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "kind": self.kind.value,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "attributes": self.attributes,
            "events": [
                {"name": e.name, "timestamp": e.timestamp, "attributes": e.attributes}
                for e in self.events
            ],
        }
        if self.cost_usd is not None:
            d["cost_usd"] = self.cost_usd
        if self.token_count is not None:
            d["token_count"] = self.token_count
        return d


# Context variables for trace/span propagation
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_parent_span_id: ContextVar[str] = ContextVar("parent_span_id", default="")


def get_current_trace_id() -> str:
    return _trace_id.get()


def get_current_span_id() -> str:
    return _parent_span_id.get()


class SpanContext:
    """Context manager that creates a span and sets contextvars."""

    def __init__(
        self,
        kind: SpanKind,
        name: str,
        parent: Span | None = None,
        **attributes: Any,
    ):
        trace_id = _trace_id.get()
        if not trace_id:
            trace_id = uuid.uuid4().hex[:16]

        parent_id = parent.span_id if parent else _parent_span_id.get() or None

        self.span = Span(
            trace_id=trace_id,
            parent_id=parent_id,
            kind=kind,
            name=name,
            attributes=attributes,
        )
        self._trace_token = None
        self._parent_token = None

    def __enter__(self) -> Span:
        self.span.start_time = time.time()
        self._trace_token = _trace_id.set(self.span.trace_id)
        self._parent_token = _parent_span_id.set(self.span.span_id)
        from backend.pipeline.tracing.processor import _notify_span_start
        _notify_span_start(self.span)
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.span.end()
        if exc_type:
            self.span.set_status("error")
            self.span.attributes["error"] = str(exc_val)

        # Restore context
        if self._trace_token:
            _trace_id.reset(self._trace_token)
        if self._parent_token:
            _parent_span_id.reset(self._parent_token)

        # Notify processor
        from backend.pipeline.tracing.processor import _notify_span_end
        _notify_span_end(self.span)


def create_span(
    kind: SpanKind,
    name: str,
    parent: Span | None = None,
    **attributes: Any,
) -> SpanContext:
    """Create a new span context manager."""
    return SpanContext(kind, name, parent=parent, **attributes)
