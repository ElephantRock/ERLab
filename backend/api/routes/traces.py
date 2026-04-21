"""Trace observability API routes."""

from fastapi import APIRouter, HTTPException

router = APIRouter()


def _get_observability():
    from backend.pipeline.observability.manager import get_active_manager
    mgr = get_active_manager()
    if not mgr:
        raise HTTPException(status_code=503, detail="Observability not enabled")
    return mgr


@router.get("/summary")
async def trace_summary():
    """Summary of all in-memory traces."""
    return _get_observability().get_trace_summary()


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    """Get all spans for a specific trace."""
    spans = _get_observability().get_traces(trace_id)
    if not spans:
        raise HTTPException(status_code=404, detail=f"No spans found for trace {trace_id}")
    return {"trace_id": trace_id, "spans": spans}


@router.get("/metrics")
async def trace_metrics():
    """Current metrics snapshot (latency percentiles, error rates)."""
    return _get_observability().get_metrics()
