"""Fail-closed required-provider readiness (Q2).

Case-3 qualification (3B–3D specimens) proved the orchestrator's
startup probes were non-authoritative: ``preflight.ready == False``
logged "proceeding with static defaults", and probe exceptions were
downgraded to warnings — so a run whose LLM endpoint was entirely
unavailable proceeded into research execution and failed opaquely
through empty-content swallowing downstream.

This module makes required-provider readiness a precondition. It
reuses the existing LM Studio preflight (``LMStudioManager``) — no new
health framework — and raises a typed ``ProviderUnavailableError``
before research execution when readiness cannot be established.

Required-provider determination (no network):
  - ``settings.default_provider == "lmstudio"`` (the pre-existing
    trigger), or
  - the committed production capability registry routes the core
    ``idea_generation`` stage to a model whose provider is lmstudio.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.pipeline.research import PreflightResult

logger = logging.getLogger(__name__)


class ProviderUnavailableError(RuntimeError):
    """A provider required by the run cannot establish readiness.

    Raised before research execution so the run never starts on a
    dead endpoint. Carries the provider kind and the preflight
    errors/cause for diagnostics.
    """

    def __init__(self, provider: str, detail: str) -> None:
        self.provider = provider
        self.detail = detail
        super().__init__(
            f"Required provider {provider!r} is not ready:"
            f" {detail}. The run refuses to proceed on static"
            f" defaults (Q2 fail-closed readiness)."
        )


def lmstudio_required_for_run(settings: Settings) -> bool:
    """Determine (offline) whether LM Studio is a required provider.

    True when the default provider is lmstudio, or when the committed
    production capability registry routes the core idea_generation
    stage to an lmstudio-served model.
    """
    if settings.default_provider.lower() == "lmstudio":
        return True
    # Registry availability is a precondition for the determination:
    # missing or unreadable means UNKNOWN, which fails closed (Q2
    # review P1). Only a present registry that routes away from
    # lmstudio may return False.
    from pathlib import Path as _Path

    registry_path = _Path(
        getattr(
            settings, "capability_registry_path", None,
        )
        or "data/model_certification/production_registry.yaml",
    )
    if not registry_path.exists():
        # Q2 review P1: deployments that never shipped a registry
        # (OpenAI/Anthropic-style, no certification data) must not
        # newly abort on its absence — the registry drives the
        # SECONDARY requirement signal only. The primary signal
        # (default_provider == lmstudio) was already checked above
        # and does not depend on the registry.
        logger.info(
            "No production registry at %s — readiness requirement"
            " falls back to the default-provider signal only",
            registry_path,
        )
        return False
    try:
        from backend.pipeline.routing.certified_lookup import (
            CertifiedCapabilityLookup,
        )

        # Load candidates from the SAME registry that was just
        # validated (Q2 review P1): the exact configured file's
        # directory feeds the lookup.
        lookup = CertifiedCapabilityLookup(registry_path.parent)
        candidates = lookup.get_candidates_for_stage(
            getattr(
                settings, "readiness_probe_stage", None,
            )
            or "idea_generation",
        )
    except Exception as e:  # noqa: BLE001 - registry unreadable = unknown
        raise ProviderUnavailableError(
            "capability_registry",
            f"registry lookup failed: {e}",
        ) from e
    return any(
        (getattr(c, "provider", "") or "").lower() == "lmstudio"
        for c in candidates
    )


def enforce_required_provider_readiness(
    settings: Settings,
) -> tuple[Any, PreflightResult]:
    """Run the existing LM Studio preflight and fail closed.

    Returns ``(manager, preflight)`` on readiness. Raises
    ``ProviderUnavailableError`` when the preflight reports not-ready
    or itself fails — never proceeds on static defaults.

    Only called when :func:`lmstudio_required_for_run` is True.
    """
    from backend.pipeline.research import LMStudioManager

    # Construct from the SUPPLIED settings so a run configured with a
    # custom endpoint/model is checked against its own endpoint (Q2
    # review P1): LMStudioManager accepts base_url/model_id/
    # required_context, not a settings object.
    mgr = LMStudioManager(
        base_url=getattr(settings, "lmstudio_base_url", "") or "",
        model_id=getattr(settings, "lmstudio_model", "") or "",
        required_context=int(
            getattr(settings, "lmstudio_required_context", 0) or 0,
        ),
    )
    try:
        preflight = mgr.preflight_check(auto_fix=True)
    except Exception as e:  # noqa: BLE001 - cannot establish readiness
        raise ProviderUnavailableError(
            "lmstudio", f"preflight raised {type(e).__name__}: {e}",
        ) from e
    if not getattr(preflight, "ready", False):
        errors = list(getattr(preflight, "errors", []) or [])
        raise ProviderUnavailableError(
            "lmstudio",
            "; ".join(errors) or "preflight not ready (no errors listed)",
        )
    return mgr, preflight
