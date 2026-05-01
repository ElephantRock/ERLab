"""Status API routes."""

from fastapi import APIRouter

from backend.config import get_settings

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
