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

    Returns:
        {"total_traces": 42, "active_traces": 3, "error_rate": 0.05}

    Example response:
        {"total_traces": 42, "active_traces": 3, "error_rate": 0.05}
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

    Returns:
        {"p50_ms": 120, "p99_ms": 3500, "error_rate": 0.02}

    Example response:
        {"p50_ms": 120, "p99_ms": 3500, "error_rate": 0.02}
    """
    return _get_observability().get_metrics()
