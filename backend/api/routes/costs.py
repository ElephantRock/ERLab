"""Cost tracking API routes."""

from pathlib import Path

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError
from backend.providers.provider_factory import get_registry

router = APIRouter()


def _tracker():
    return get_registry().cost_tracker


@router.get(
    "/summary",
    summary="Cost summary",
    description="Total cost summary across all recorded cost events.",
)
async def cost_summary():
    """Get total cost summary across all recorded events.

    Returns:
        {"total_cost_usd": 0.0, "total_tokens": 0, "event_count": 0}

    Example response:
        {"total_cost_usd": 1.23, "total_tokens": 150000, "event_count": 42}
    """
    return _tracker().summary()


@router.get(
    "/by-provider",
    summary="Cost by provider",
    description="Cost breakdown grouped by LLM provider.",
)
async def cost_by_provider():
    """Get cost breakdown by provider.

    Returns:
        {"openai": {"cost_usd": 0.5, "input_tokens": 1000, "output_tokens": 500, "calls": 10}}

    Example response:
        {"openai": {"cost_usd": 0.5, "input_tokens": 1000, "output_tokens": 500, "calls": 10}}
    """
    return _tracker().by_provider()


@router.get(
    "/by-stage",
    summary="Cost by pipeline stage",
    description="Cost breakdown grouped by pipeline execution stage.",
)
async def cost_by_stage():
    """Get cost breakdown by pipeline stage.

    Returns:
        {"generation": {"cost_usd": 0.3, "input_tokens": 500, "output_tokens": 200, "calls": 5}}

    Example response:
        {"generation": {"cost_usd": 0.3, "input_tokens": 500, "output_tokens": 200, "calls": 5}}
    """
    return _tracker().by_stage()


@router.get(
    "/by-model",
    summary="Cost by model",
    description="Cost breakdown grouped by provider/model combination.",
)
async def cost_by_model():
    """Get cost breakdown by provider/model.

    Returns:
        {"openai/gpt-4": {"cost_usd": 0.8, "input_tokens": 1500, "output_tokens": 300, "calls": 8}}

    Example response:
        {"openai/gpt-4": {"cost_usd": 0.8, "input_tokens": 1500, "output_tokens": 300, "calls": 8}}
    """
    return _tracker().by_model()


@router.get(
    "/run/{run_id}",
    summary="Cost for a specific run",
    description="Load persisted cost events for a specific pipeline run.",
)
async def cost_for_run(run_id: str):
    """Load persisted cost events for a specific pipeline run.

    Args:
        run_id: The pipeline run identifier.

    Returns:
        {"run_id": "...", "summary": {...}, "by_provider": {...}, "by_stage": {...}}

    Example response:
        {"run_id": "run_20260422_143908", "summary": {"total_cost_usd": 0.5}, "by_provider": {}, "by_stage": {}}
    """
    from backend.config import get_settings

    settings = get_settings()
    path = Path(f"{settings.cost_persist_dir}/{run_id}.jsonl")
    if not path.exists():
        raise NotFoundError(f"No cost data for run {run_id}")

    from backend.providers.provider_factory import CostTracker

    tracker = CostTracker.load(str(path))
    return {
        "run_id": run_id,
        "summary": tracker.summary(),
        "by_provider": tracker.by_provider(),
        "by_stage": tracker.by_stage(),
    }
