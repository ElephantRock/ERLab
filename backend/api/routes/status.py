"""Status API routes."""

from fastapi import APIRouter

from backend.config import get_settings
from backend.db.database import _get_engine
from sqlalchemy import text

router = APIRouter()


@router.get(
    "/",
    summary="Platform status",
    description="Get platform status including active configuration, enabled features, and default settings.",
)
async def platform_status():
    """Get platform status including configuration and state.

    Returns:
        {"app_name": "...", "version": "...", "config": {...}, "defaults": {...}}

    Example response:
        {"app_name": "Elephant Rock", "version": "0.1.0", "config": {"default_provider": "openai", "memory_enabled": true, "self_improve_enabled": false, "autonomy_enabled": false, "budget_enabled": false, "governance_enabled": false}, "defaults": {"generation_rounds": 3, "ideas_per_round": 5, "novelty_top_k": 20}}
    """
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": "0.1.0",
        "config": {
            "default_provider": settings.default_provider,
            "memory_enabled": settings.memory_enabled,
            "self_improve_enabled": settings.self_improve_enabled,
            "autonomy_enabled": settings.autonomy_enabled,
            "budget_enabled": settings.budget_enabled,
            "governance_enabled": settings.governance_enabled,
        },
        "defaults": {
            "generation_rounds": settings.generation_rounds,
            "ideas_per_round": settings.ideas_per_round,
            "novelty_top_k": settings.novelty_top_k,
        },
    }


@router.get(
    "/detailed",
    summary="Detailed platform status",
    description="Get detailed status including version, default provider, and database connectivity.",
)
async def detailed_status():
    """Get detailed platform status with version, provider, and database health.

    Returns:
        {"version": "...", "provider": "...", "db_status": "ok"|"error"}
    """
    settings = get_settings()

    # Check database connectivity
    db_status = "ok"
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "version": "0.1.0",
        "provider": settings.default_provider,
        "db_status": db_status,
    }


@router.get(
    "/evolution",
    summary="Evolution status",
    description="Get self-improvement evolution engine status including overlay count and recent outcomes.",
)
async def evolution_status():
    """Get evolution engine status.

    Returns:
        {"enabled": bool, "overlays_generated": int, "recent_outcomes": list}

    Example response:
        {"enabled": true, "overlays_generated": 5, "recent_outcomes": [{"stage_name": "idea_generation", "score": 0.8, "run_id": "run_1"}]}
    """
    settings = get_settings()

    if not settings.self_improve_enabled:
        return {
            "enabled": False,
            "overlays_generated": 0,
            "recent_outcomes": [],
        }

    # Access the evolution engine from the pipeline module
    try:
        from backend.pipeline.self_improve.engine import EvolutionEngine
        from backend.pipeline.self_improve.evolution import PipelineEvolver

        evolver = PipelineEvolver()
        engine = EvolutionEngine(evolver=evolver)

        # Count overlays from recent outcomes
        recent_outcomes = []
        overlays = 0
        for outcome in engine._outcomes[-10:]:
            recent_outcomes.append({
                "stage_name": outcome.stage_name,
                "score": outcome.score,
                "run_id": outcome.run_id,
            })
            if outcome.score < 0.7:
                overlays += 1

        return {
            "enabled": True,
            "overlays_generated": overlays,
            "recent_outcomes": recent_outcomes,
        }
    except Exception:
        return {
            "enabled": True,
            "overlays_generated": 0,
            "recent_outcomes": [],
        }
