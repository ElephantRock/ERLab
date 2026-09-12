"""Trace observability API routes."""

from fastapi import APIRouter

from backend.api.errors import NotFoundError, ServiceUnavailableError

router = APIRouter()


def _get_observability():
    from backend.pipeline.observability.manager import get_active_manager
    mgr = get_active_manager()
    if not mgr:
        raise ServiceUnavailableError("Observability not enabled", hint="Enable observability in platform configuration")
    return mgr


@router.get(
    "/summary",
    summary="Trace summary",
    description="Summary of all in-memory traces.",
)
async def trace_summary():
    """Get summary of all in-memory traces.

    Returns the documented contract plus the additive fields the trace
    viewer consumes:

        {
          "total_traces": 42,        # documented
          "active_traces": 3,        # documented; trace with span activity
                                     # within the last 5 minutes
          "error_rate": 0.05,        # documented; error spans / total spans
          "recent_traces": [         # additive; newest first, bounded (50)
            {
              "trace_id": "abc123...",
              "span_count": 12,
              "started_at": 1726100000.0,
              "last_activity": 1726100120.0,
              "duration_ms": 120000.0,
              "error_count": 0,
              "models": ["glm-5.2"]   # providers seen via cost linkage
            }
          ],
          "span_count": 500, "trace_count": 42, "by_kind": {...},
          "by_status": {...}, "total_duration_ms": ..., "avg_duration_ms": ...
        }

    The legacy aggregate keys (span_count, trace_count, by_kind, by_status,
    total_duration_ms, avg_duration_ms) are preserved for existing consumers.
    """
    return _get_observability().get_trace_summary()


@router.get(
    "/trace/{trace_id}",
    summary="Get trace spans",
    description="Get all spans for a specific trace by its ID.",
)
async def get_trace(trace_id: str):
    """Get all spans for a specific trace.

    Args:
        trace_id: The unique trace identifier.

    Returns:
        {"trace_id": "...", "spans": [...]}

    Example response:
        {"trace_id": "abc-123", "spans": [{"name": "generation", "duration_ms": 1500}]}
    """
    spans = _get_observability().get_traces(trace_id)
    if not spans:
        raise NotFoundError(f"No spans found for trace {trace_id}")
    return {"trace_id": trace_id, "spans": spans}


@router.get(
    "/metrics",
    summary="Trace metrics",
    description="Current metrics snapshot including latency percentiles and error rates.",
)
async def trace_metrics():
    """Get current metrics snapshot.

    Returns the documented flat aggregate plus the per-kind breakdown:

        {
          "p50_ms": 120, "p95_ms": 800, "p99_ms": 3500, "avg_ms": 210.5,
          "error_rate": 0.02, "call_count": 128,
          "by_kind": {"stage": {"count": ..., "latency_ms": {...}}, ...}
        }
    """
    return _get_observability().get_metrics()
