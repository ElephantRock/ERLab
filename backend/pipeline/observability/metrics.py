"""MetricsCollector — latency percentiles, call counts, error rates per SpanKind."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from backend.pipeline.tracing.processor import TracingProcessor
from backend.pipeline.tracing.spans import Span


class MetricsCollector(TracingProcessor):
    """Accumulates latency and error metrics from completed spans.

    Computes p50/p95/p99 latency percentiles, call counts, and error rates
    per SpanKind. Plugs into CompositeProcessor.
    """

    def __init__(self) -> None:
        self._latencies: dict[str, list[float]] = defaultdict(list)
        self._counts: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)

    def on_span_start(self, span: Span) -> None:
        pass

    def on_span_end(self, span: Span) -> None:
        kind = span.kind.value
        self._counts[kind] += 1
        self._latencies[kind].append(span.duration_ms)
        if span.status == "error":
            self._errors[kind] += 1

    @staticmethod
    def _percentile(sorted_values: list[float], p: float) -> float:
        if not sorted_values:
            return 0.0
        idx = (p / 100.0) * (len(sorted_values) - 1)
        lower = int(math.floor(idx))
        upper = min(lower + 1, len(sorted_values) - 1)
        frac = idx - lower
        return sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for kind in self._counts:
            latencies = sorted(self._latencies.get(kind, []))
            result[kind] = {
                "count": self._counts[kind],
                "errors": self._errors.get(kind, 0),
                "error_rate": self._errors.get(kind, 0) / max(1, self._counts[kind]),
                "latency_ms": {
                    "p50": self._percentile(latencies, 50),
                    "p95": self._percentile(latencies, 95),
                    "p99": self._percentile(latencies, 99),
                    "avg": sum(latencies) / max(1, len(latencies)),
                },
            }
        return result
