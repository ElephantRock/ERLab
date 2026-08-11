"""Per-stage model configuration API.

Allows users to select which LLM model/provider to use for each pipeline stage
via the UI. Configuration is persisted to a JSON file so it survives restarts.
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.api.errors import APIError

logger = logging.getLogger(__name__)

router = APIRouter()

# 16 pipeline stages
STAGES = [
    "literature_search",
    "ingestion",
    "gap_analysis",
    "gap_reflection",
    "idea_generation",
    "idea_reflection",
    "novelty_checking",
    "feasibility_scoring",
    "mechanical_metrics",
    "proposal_synthesis",
    "adversarial_review",
    "evaluation",
    "paper_synthesis",
    "citation_audit",
    "proposal_deepening",
    "export",
]

# Task categories for smart defaults
THINKING_STAGES = {
    "gap_analysis", "gap_reflection", "novelty_checking",
    "feasibility_scoring", "adversarial_review", "evaluation",
    "citation_audit",
}
GENERATION_STAGES = {
    "idea_generation", "idea_reflection", "proposal_synthesis",
    "paper_synthesis", "proposal_deepening",
}
PASSTHROUGH_STAGES = {
    "literature_search", "ingestion", "mechanical_metrics", "export",
}

CONFIG_PATH = Path("./data/model_config.json")


def _load_config() -> dict[str, str]:
    """Load per-stage model config from disk."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load model config: %s", e)
    return {}


def _save_config(config: dict[str, str]) -> None:
    """Persist per-stage model config to disk."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def _get_available_models() -> list[dict[str, Any]]:
    """Discover available models from configured providers."""
    models: list[dict[str, Any]] = []

    try:
        from backend.config import get_settings
        settings = get_settings()

        # Cloud provider (Anthropic/z.ai)
        if settings.anthropic_api_key:
            models.append({
                "id": "cloud",
                "name": f"Cloud ({settings.anthropic_model})",
                "provider": "anthropic",
                "model": settings.anthropic_model,
                "location": "cloud",
                "type": "generation",
            })

        # Local LM Studio
        if settings.lmstudio_enabled:
            models.append({
                "id": "local",
                "name": f"Local ({settings.lmstudio_model})",
                "provider": "lmstudio",
                "model": settings.lmstudio_model,
                "location": "local",
                "type": "thinking",
            })

        # Auto-routed (thinking → local, generation → cloud)
        if settings.anthropic_api_key and settings.lmstudio_enabled:
            models.append({
                "id": "auto",
                "name": "Auto (thinking→local, generation→cloud)",
                "provider": "auto",
                "model": "auto",
                "location": "hybrid",
                "type": "auto",
            })

    except Exception as e:
        logger.warning("Error discovering models: %s", e)

    return models


def _get_default_model(stage: str) -> str:
    """Get the default model ID for a stage based on its category."""
    if stage in THINKING_STAGES:
        return "local"
    if stage in GENERATION_STAGES:
        return "cloud"
    # Passthrough stages use auto
    return "auto"


def get_stage_model(stage: str) -> str | None:
    """Resolve which model ID to use for a given stage.

    Called by the orchestrator when building stages.
    Returns None if no override is configured (use default routing).
    """
    config = _load_config()
    return config.get(stage)


@router.get(
    "/models",
    summary="Get model configuration",
    description="Returns available models and current per-stage model assignments.",
)
async def get_model_config():
    """Get available models and per-stage configuration.

    Returns:
        Available models list, stage definitions, and current assignments.

    Example response:
        {
            "models": [
                {"id": "cloud", "name": "Cloud (glm-5.1)", "provider": "anthropic", ...},
                {"id": "local", "name": "Local (qwen3-4b)", "provider": "lmstudio", ...},
                {"id": "auto", "name": "Auto (thinking→local, generation→cloud)", ...}
            ],
            "stages": [
                {"name": "literature_search", "label": "Literature Search", "category": "passthrough"},
                ...
            ],
            "assignments": {
                "gap_analysis": "local",
                "proposal_synthesis": "cloud"
            }
        }
    """
    models = _get_available_models()
    config = _load_config()

    stages_info = []
    for stage in STAGES:
        # Create human-readable label
        label = stage.replace("_", " ").title()
        if stage in THINKING_STAGES:
            category = "thinking"
        elif stage in GENERATION_STAGES:
            category = "generation"
        else:
            category = "passthrough"

        stages_info.append({
            "name": stage,
            "label": label,
            "category": category,
            "default_model": _get_default_model(stage),
        })

    return {
        "models": models,
        "stages": stages_info,
        "assignments": config,
    }


@router.put(
    "/models",
    summary="Update model configuration",
    description="Set which model to use for each pipeline stage.",
)
async def update_model_config(body: dict[str, str]):
    """Update per-stage model assignments.

    Args:
        body: Map of stage name → model ID. Only stages in STAGES are accepted.

    Example request:
        {
            "gap_analysis": "local",
            "proposal_synthesis": "cloud",
            "novelty_checking": "local"
        }

    Returns:
        Updated assignments.
    """
    valid_model_ids = {m["id"] for m in _get_available_models()}

    if not valid_model_ids:
        raise APIError(400, "CONFIG_ERROR", "No models available. Configure at least one LLM provider.")

    # Validate all keys are known stages and values are known models
    cleaned: dict[str, str] = {}
    for stage, model_id in body.items():
        if stage not in STAGES:
            raise APIError(
                400, "INVALID_STAGE",
                f"Unknown stage: '{stage}'. Valid stages: {', '.join(STAGES)}",
            )
        if model_id not in valid_model_ids:
            raise APIError(
                400, "INVALID_MODEL",
                f"Unknown model '{model_id}' for stage '{stage}'. "
                f"Valid models: {', '.join(sorted(valid_model_ids))}",
            )
        cleaned[stage] = model_id

    _save_config(cleaned)
    logger.info("Updated model config: %s", cleaned)

    return {"assignments": cleaned, "message": f"Updated {len(cleaned)} stage assignments"}


@router.delete(
    "/models",
    summary="Reset model configuration",
    description="Clear all per-stage model overrides, reverting to defaults.",
)
async def reset_model_config():
    """Reset all per-stage model assignments to defaults."""
    _save_config({})
    return {"message": "Model config reset to defaults", "assignments": {}}


# ── Universal Model Manager endpoints ───────────────────────────────


@router.get(
    "/catalog",
    summary="Get discovered model catalog",
    description="Returns all models discovered by the Universal Model Manager at startup.",
)
async def get_model_catalog():
    """Get all discovered models with their capabilities and status."""
    try:
        from backend.providers.model_manager import get_model_manager
        mm = get_model_manager()
        if not mm.is_initialized:
            return {"models": [], "error": "ModelManager not initialized"}

        catalog = mm.get_catalog()
        models = []
        for m in catalog.get_all():
            models.append({
                "model_id": m.model_id,
                "display_name": m.display_name or m.model_id,
                "provider_type": m.provider_type,
                "endpoint_url": m.endpoint_url,
                "parameter_count": m.parameter_count,
                "context_length": m.context_length,
                "context_label": m.context_label,
                "quantization": m.quantization,
                "size_gb": round(m.size_gb, 2),
                "capabilities": {
                    "json_mode": m.supports_json_mode,
                    "tools": m.supports_tools,
                    "vision": m.supports_vision,
                    "thinking": m.supports_thinking,
                },
                "is_loaded": m.is_loaded,
                "health_status": m.health_status,
                "measured": {
                    "total_calls": m.measured.total_calls if m.measured else 0,
                    "reliability": m.measured.reliability if m.measured else 0.0,
                    "json_reliability": m.measured.json_reliability if m.measured else 0.0,
                } if m.measured else None,
            })

        gpu = mm.get_gpu_info()
        return {
            "models": models,
            "total": len(models),
            "gpu": {
                "name": gpu.name if gpu else None,
                "vram_total_gb": round(gpu.vram_total_gb, 1) if gpu else None,
                "vram_available_gb": round(gpu.vram_available_gb, 1) if gpu else None,
            } if gpu else None,
        }
    except Exception as e:
        logger.warning("Error getting model catalog: %s", e)
        return {"models": [], "error": str(e)}


@router.get(
    "/assignments",
    summary="Get stage-to-model assignments",
    description="Returns the current stage → model routing plan from the Universal Model Manager.",
)
async def get_model_assignments():
    """Get current stage → model assignments."""
    try:
        from backend.providers.model_manager import get_model_manager
        mm = get_model_manager()
        if not mm.is_initialized:
            return {"assignments": {}, "error": "ModelManager not initialized"}

        assignments = mm.get_assignments()
        result = {}
        for stage, model in assignments.items():
            result[stage] = {
                "model_id": model.model_id,
                "parameter_count": model.parameter_count,
                "context_label": model.context_label,
                "is_loaded": model.is_loaded,
                "quantization": model.quantization,
            }

        return {
            "assignments": result,
            "total_stages": len(result),
        }
    except Exception as e:
        logger.warning("Error getting model assignments: %s", e)
        return {"assignments": {}, "error": str(e)}


@router.post(
    "/catalog/reload",
    summary="Reload model catalog",
    description="Re-discover models and re-assign stages. Call after adding/removing models.",
)
async def reload_model_catalog():
    """Trigger a model catalog reload."""
    try:
        from backend.providers.model_manager import get_model_manager
        mm = get_model_manager()
        await mm.reload()
        assignments = mm.get_assignments()
        return {
            "message": f"Reloaded: {len(mm.get_catalog())} models, {len(assignments)} stage assignments",
            "total_models": len(mm.get_catalog()),
            "total_assignments": len(assignments),
        }
    except Exception as e:
        logger.error("Error reloading model catalog: %s", e)
        raise APIError(500, "RELOAD_ERROR", f"Failed to reload: {e}")


# ── Real model assignment overrides (model_assignments.json) ────


@router.get(
    "/stages",
    summary="Get pipeline stage metadata",
    description="Returns all pipeline stages with category and default model info.",
)
async def get_stage_metadata():
    """Get all pipeline stages with their categories.

    This is the authoritative source for stage metadata — the UI should
    use this rather than hardcoding stage names.
    """
    stages = []
    for stage in STAGES:
        if stage in THINKING_STAGES:
            category = "thinking"
        elif stage in GENERATION_STAGES:
            category = "generation"
        else:
            category = "passthrough"
        stages.append({
            "name": stage,
            "label": stage.replace("_", " ").title(),
            "category": category,
            "needs_llm": stage not in PASSTHROUGH_STAGES,
        })
    return {"stages": stages, "total": len(stages)}


@router.get(
    "/certification",
    summary="Get model certification status",
    description="Returns per-model certification data from the production registry.",
)
async def get_certification():
    """Get model certification data from the production registry.

    Returns:
        List of certifications with model_id, provider, status, and
        allowed_stages mapping.
    """
    try:
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        lookup = CertifiedCapabilityLookup()
        if not lookup.production_models:
            return {"certifications": [], "total": 0}

        certs = []
        for model_id, entry in lookup.production_models.items():
            if not isinstance(entry, dict):
                continue
            allowed = entry.get("allowed_stages", {})
            if not isinstance(allowed, dict):
                allowed = {}
            certs.append({
                "model_id": model_id,
                "provider": entry.get("provider", "unknown"),
                "status": entry.get("status", "unknown"),
                "allowed_stages": {
                    s: lvl for s, lvl in allowed.items()
                    if isinstance(s, str) and isinstance(lvl, str)
                },
            })

        return {"certifications": certs, "total": len(certs)}
    except Exception as e:
        logger.warning("Error getting certification data: %s", e)
        return {"certifications": [], "total": 0, "error": str(e)}


def _validate_assignments(
    assignments: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Validate stage→model assignments against catalog and certification.

    Returns:
        (cleaned_assignments, warnings)
    """
    from backend.providers.model_manager import get_model_manager

    warnings: list[dict[str, str]] = []
    cleaned: dict[str, str] = {}

    # Build valid stage set
    valid_stages = set(STAGES)

    # Build valid model set from catalog
    valid_model_ids: set[str] = set()
    try:
        mm = get_model_manager()
        if mm.is_initialized:
            for m in mm.get_catalog().get_all():
                valid_model_ids.add(m.model_id)
    except Exception:
        pass

    # Load certification for warnings
    cert_data: dict[str, set[str]] = {}  # model_id → set of certified stages
    try:
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        lookup = CertifiedCapabilityLookup()
        for model_id, entry in lookup.production_models.items():
            allowed = entry.get("allowed_stages", {})
            if isinstance(allowed, dict):
                cert_data[model_id] = {
                    s for s, lvl in allowed.items()
                    if isinstance(lvl, str) and lvl not in ("not_approved", "blocked")
                }
    except Exception:
        pass

    for stage, model_id in assignments.items():
        # Validate stage
        if stage not in valid_stages:
            warnings.append({
                "code": "UNKNOWN_STAGE",
                "stage": stage,
                "model_id": model_id,
                "message": f"Unknown stage '{stage}'. Valid stages: {', '.join(sorted(valid_stages))}",
            })
            continue

        # Validate model exists in catalog (warn if catalog unavailable)
        if valid_model_ids and model_id not in valid_model_ids:
            warnings.append({
                "code": "UNKNOWN_MODEL",
                "stage": stage,
                "model_id": model_id,
                "message": f"Model '{model_id}' not found in catalog. It may need to be loaded first.",
            })
            continue

        # Check certification
        certified_stages = cert_data.get(model_id)
        if certified_stages is not None and stage not in certified_stages:
            warnings.append({
                "code": "NOT_CERTIFIED",
                "stage": stage,
                "model_id": model_id,
                "message": (
                    f"Model '{model_id}' is not certified for stage '{stage}'. "
                    "The pipeline will run, but output quality is not guaranteed."
                ),
            })

        cleaned[stage] = model_id

    return cleaned, warnings


@router.get(
    "/overrides",
    summary="Get per-stage model overrides",
    description="Returns real-model per-stage overrides from model_assignments.json.",
)
async def get_model_overrides():
    """Get current real-model per-stage overrides.

    These are explicit user overrides stored separately from the
    auto-assigned routing plan. See runtime precedence in docs.
    """
    from backend.api.model_assignments import load_assignments
    overrides = load_assignments()
    return {
        "overrides": overrides,
        "total": len(overrides),
    }


@router.put(
    "/overrides",
    summary="Update per-stage model overrides",
    description=(
        "Set which real model to use for each pipeline stage. "
        "Accepts real catalog model IDs. Warnings (not blocks) are returned "
        "for uncertified assignments. Use ?dry_run=true to preview warnings."
    ),
)
async def update_model_overrides(
    body: dict[str, str],
    dry_run: bool = False,
):
    """Update per-stage real-model overrides.

    Args:
        body: Map of stage name → real model ID.
        dry_run: If true, validate only — do not persist.

    Returns:
        Updated overrides and any warnings.
    """
    from backend.api.model_assignments import load_assignments, save_assignments

    cleaned, warnings = _validate_assignments(body)

    if dry_run:
        return {
            "overrides": cleaned,
            "warnings": warnings,
            "dry_run": True,
        }

    # Merge with existing (PUT replaces only the stages provided)
    existing = load_assignments()
    existing.update(cleaned)
    save_assignments(existing)

    return {
        "overrides": existing,
        "warnings": warnings,
        "message": f"Saved {len(cleaned)} stage override(s)",
    }


@router.post(
    "/overrides/validate",
    summary="Validate assignments without saving",
    description="Preview which warnings would apply for a set of assignments.",
)
async def validate_model_overrides(body: dict[str, str]):
    """Dry-run validation of stage→model assignments.

    Same validation as PUT /overrides but never persists.
    """
    cleaned, warnings = _validate_assignments(body)
    return {
        "valid": len(warnings) == 0,
        "overrides": cleaned,
        "warnings": warnings,
    }


@router.delete(
    "/overrides/{stage}",
    summary="Remove a single stage override",
    description="Clear the real-model override for one stage, reverting to auto-routing.",
)
async def remove_stage_override(stage: str):
    """Remove one stage's real-model override."""
    if stage not in STAGES:
        raise APIError(400, "INVALID_STAGE", f"Unknown stage: '{stage}'")

    from backend.api.model_assignments import load_assignments, save_assignments
    current = load_assignments()
    if stage not in current:
        return {"message": f"No override for stage '{stage}'", "overrides": current}
    del current[stage]
    save_assignments(current)
    return {"message": f"Removed override for stage '{stage}'", "overrides": current}


@router.delete(
    "/overrides",
    summary="Clear all stage overrides",
    description="Remove all real-model per-stage overrides, reverting to auto-routing.",
)
async def clear_all_overrides():
    """Clear all real-model per-stage overrides."""
    from backend.api.model_assignments import clear_assignments
    clear_assignments()
    return {"message": "All stage overrides cleared", "overrides": {}}
