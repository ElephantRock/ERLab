"""Tests for ObservabilityManager — processor building, graceful OTLP degradation."""

from backend.pipeline.observability.manager import ObservabilityManager, set_active_manager
from backend.pipeline.tracing.processor import (
    CompositeProcessor,
    InMemoryProcessor,
    LoggingProcessor,
    get_tracer,
)
from backend.pipeline.tracing.spans import SpanKind, create_span


class TestObservabilityManager:
    def test_builds_default_processors(self):
        mgr = ObservabilityManager()
        tracer = get_tracer()
        assert isinstance(tracer, CompositeProcessor)
        assert tracer.get(InMemoryProcessor) is not None
        assert tracer.get(LoggingProcessor) is not None

    def test_disabled_memory(self):
        mgr = ObservabilityManager(trace_memory=False)
        tracer = get_tracer()
        assert tracer.get(InMemoryProcessor) is None

    def test_disabled_logging(self):
        mgr = ObservabilityManager(trace_logging=False)
        tracer = get_tracer()
        assert tracer.get(LoggingProcessor) is None

    def test_metrics_enabled(self):
        from backend.pipeline.observability.metrics import MetricsCollector
        mgr = ObservabilityManager(metrics_enabled=True)
        tracer = get_tracer()
        assert tracer.get(MetricsCollector) is not None

    def test_metrics_disabled(self):
        from backend.pipeline.observability.metrics import MetricsCollector
        mgr = ObservabilityManager(metrics_enabled=False)
        tracer = get_tracer()
        assert tracer.get(MetricsCollector) is None

    def test_otlp_graceful_degradation(self):
        # OTLP deps not installed — should not crash
        mgr = ObservabilityManager(otlp_enabled=True)
        tracer = get_tracer()
        # No OTLP exporter added (ImportError caught)
        from backend.pipeline.observability.otlp_exporter import OTLPExporter
        assert tracer.get(OTLPExporter) is None

    def test_get_traces_empty(self):
        mgr = ObservabilityManager(trace_memory=True)
        assert mgr.get_traces("nonexistent") == []

    def test_get_traces_with_spans(self):
        set_active_manager(None)
        mgr = ObservabilityManager(trace_memory=True, trace_logging=False)
        set_active_manager(mgr)
        with create_span(SpanKind.STAGE, "test"):
            pass
        traces = mgr.get_traces(create_span.__module__ or "")
        # The trace_id is generated inside the span, so query via summary
        summary = mgr.get_trace_summary()
        assert summary["span_count"] >= 1

    def test_get_metrics(self):
        mgr = ObservabilityManager(metrics_enabled=True)
        with create_span(SpanKind.TOOL, "t1"):
            pass
        metrics = mgr.get_metrics()
        assert "tool" in metrics
        assert metrics["tool"]["count"] == 1

    def test_active_manager(self):
        mgr = ObservabilityManager()
        set_active_manager(mgr)
        from backend.pipeline.observability.manager import get_active_manager
        assert get_active_manager() is mgr
        set_active_manager(None)
