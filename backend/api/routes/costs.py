"""Cost tracking API routes."""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from backend.providers.provider_factory import get_registry

router = APIRouter()


def _tracker():
    return get_registry().cost_tracker


@router.get("/summary")
async def cost_summary():
    """Total cost summary across all recorded events."""
    return _tracker().summary()


@router.get("/by-provider")
async def cost_by_provider():
    """Cost breakdown by provider."""
    return _tracker().by_provider()


@router.get("/by-stage")
async def cost_by_stage():
    """Cost breakdown by pipeline stage."""
    return _tracker().by_stage()


@router.get("/by-model")
async def cost_by_model():
    """Cost breakdown by provider/model."""
    return _tracker().by_model()


@router.get("/run/{run_id}")
async def cost_for_run(run_id: str):
    """Load persisted cost events for a specific run."""
    from backend.config import get_settings

    settings = get_settings()
    path = Path(f"{settings.cost_persist_dir}/{run_id}.jsonl")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No cost data for run {run_id}")

    from backend.providers.provider_factory import CostTracker

    tracker = CostTracker.load(str(path))
    return {
        "run_id": run_id,
        "summary": tracker.summary(),
        "by_provider": tracker.by_provider(),
        "by_stage": tracker.by_stage(),
    }
