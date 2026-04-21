"""Optional OTLP exporter — converts custom spans to OpenTelemetry format.

Requires: pip install opentelemetry-api opentelemetry-sdk
          opentelemetry-exporter-otlp-proto-grpc (or -http)
Feature-flagged: only imported when EROCK_OBSERVABILITY_OTLP_ENABLED=true.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.pipeline.tracing.processor import TracingProcessor
from backend.pipeline.tracing.spans import Span

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.resources import Resource
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


class OTLPExporter(TracingProcessor):
    """Converts Elephant Rock spans to OTLP and exports via gRPC or HTTP."""

    def __init__(self, endpoint: str = "http://localhost:4317", protocol: str = "grpc") -> None:
        if not _OTEL_AVAILABLE:
            raise ImportError("opentelemetry packages not installed")

        resource = Resource.create({"service.name": "elephant-rock"})
        provider = TracerProvider(resource=resource)

        if protocol == "http":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint)
        else:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint)

        provider.add_span_processor(BatchSpanProcessor(exporter))
        self._tracer = provider.get_tracer("elephant-rock")

    def on_span_start(self, span: Span) -> None:
        pass

    def on_span_end(self, span: Span) -> None:
        try:
            otel_span = self._tracer.start_span(
                name=f"{span.kind.value}:{span.name}",
                attributes={
                    "erock.span_id": span.span_id,
                    "erock.trace_id": span.trace_id,
                    "erock.kind": span.kind.value,
                    **{f"erock.attr.{k}": str(v) for k, v in span.attributes.items()},
                },
                start_time=int(span.start_time * 1e9) if span.start_time else None,
            )
            otel_span.end(end_time=int(span.end_time * 1e9) if span.end_time else None)
        except Exception:
            logger.exception("OTLP export failed for span %s", span.span_id)

    def shutdown(self) -> None:
        if hasattr(self._tracer, "shutdown"):
            self._tracer.shutdown()
