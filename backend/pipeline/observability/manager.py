"""ObservabilityManager — creates processors, wires cost tracking, provides API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.tracing.processor import (
    CompositeProcessor,
    InMemoryProcessor,
    LoggingProcessor,
    TracingProcessor,
    set_tracer,
)
from backend.pipeline.tracing.spans import Span

if TYPE_CHECKING:
    from backend.providers.provider_factory import CostTracker

logger = logging.getLogger(__name__)

_active: ObservabilityManager | None = None


def set_active_manager(mgr: ObservabilityManager | None) -> None:
    global _active
    _active = mgr


def get_active_manager() -> ObservabilityManager | None:
    return _active


class _CostLinkingProcessor(TracingProcessor):
    """Attaches cost data from CostTracker to completed spans."""

    def __init__(self, cost_tracker: CostTracker) -> None:
        self._tracker = cost_tracker

    def on_span_start(self, span: Span) -> None:
        pass

    def on_span_end(self, span: Span) -> None:
        if not span.start_time or not span.end_time:
            return
        events = self._tracker.events_in_range(span.start_time, span.end_time)
        if events:
            span.cost_usd = sum(e.cost_usd for e in events)
            span.token_count = sum(e.total_tokens for e in events)


class ObservabilityManager:
    """Owns and configures the tracing subsystem.

    Created by PipelineOrchestrator when observability_enabled=True.
    Builds a CompositeProcessor from config and installs it as global tracer.
    """

    def __init__(
        self,
        *,
        trace_logging: bool = True,
        trace_memory: bool = True,
        max_memory_spans: int = 10000,
        otlp_enabled: bool = False,
        otlp_endpoint: str | None = None,
        otlp_protocol: str = "grpc",
        metrics_enabled: bool = True,
        cost_tracker: CostTracker | None = None,
    ) -> None:
        self._composite = CompositeProcessor()
        self._memory_processor: InMemoryProcessor | None = None
        self._otlp_exporter = None
        self._metrics = None

        # Resolve OTLP endpoint from settings if not explicitly provided
        if otlp_endpoint is None:
            try:
                from backend.config import get_settings
                otlp_endpoint = get_settings().observability_otlp_endpoint
            except Exception:
                otlp_endpoint = "http://localhost:4317"

        if trace_logging:
            self._composite.add(LoggingProcessor())

        if trace_memory:
            self._memory_processor = InMemoryProcessor(max_spans=max_memory_spans)
            self._composite.add(self._memory_processor)

        if metrics_enabled:
            from backend.pipeline.observability.metrics import MetricsCollector
            self._metrics = MetricsCollector()
            self._composite.add(self._metrics)

        if cost_tracker:
            self._composite.add(_CostLinkingProcessor(cost_tracker))

        if otlp_enabled:
            self._init_otlp(otlp_endpoint, otlp_protocol)

        set_tracer(self._composite)
        logger.info(
            "Observability initialized (processors: %d, otlp: %s, metrics: %s)",
            len(self._composite.processors),
            otlp_enabled,
            metrics_enabled,
        )

    def _init_otlp(self, endpoint: str, protocol: str) -> None:
        try:
            from backend.pipeline.observability.otlp_exporter import OTLPExporter
            self._otlp_exporter = OTLPExporter(endpoint=endpoint, protocol=protocol)
            self._composite.add(self._otlp_exporter)
        except ImportError:
            logger.warning(
                "OTLP exporter requested but opentelemetry packages not installed. "
                "Install with: pip install opentelemetry-api opentelemetry-sdk "
                "opentelemetry-exporter-otlp-proto-grpc"
            )

    def get_traces(self, trace_id: str) -> list[dict]:
        if not self._memory_processor:
            return []
        spans = self._memory_processor.query(trace_id)
        return [s.to_dict() for s in spans]

    def get_trace_summary(self) -> dict:
        if not self._memory_processor:
            return {"span_count": 0, "trace_count": 0}
        return self._memory_processor.summary()

    def get_metrics(self) -> dict:
        if not self._metrics:
            return {}
        return self._metrics.snapshot()

    def shutdown(self) -> None:
        if self._otlp_exporter and hasattr(self._otlp_exporter, "shutdown"):
            self._otlp_exporter.shutdown()
