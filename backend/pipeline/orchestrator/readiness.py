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
    try:
        from backend.pipeline.routing.certified_lookup import (
            CertifiedCapabilityLookup,
        )

        candidates = CertifiedCapabilityLookup().get_candidates_for_stage(
            "idea_generation",
        )
        return any(
            (getattr(c, "provider", "") or "").lower() == "lmstudio"
            for c in candidates
        )
    except Exception as e:  # noqa: BLE001 - registry unreadable = unknown
        logger.warning(
            "Capability registry lookup failed during readiness"
            " determination: %s", str(e)[:100],
        )
        return False


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

    mgr = LMStudioManager()
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
