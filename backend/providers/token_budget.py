"""Token Budget Resolver — dynamically adjust max_tokens for thinking models.

Reads model profiles (from 3-tier profiling) and automatically inflates
max_tokens when the active model is a thinking model that burns tokens
on reasoning before producing content.

This prevents the "empty output" failure mode where a thinking model
(e.g., gemma-4-12b) consumes its entire token budget in reasoning and
produces zero content tokens.

Integration: Used by StageAwareProvider to wrap every LLM call.
Zero changes needed to the 88 individual call sites across the pipeline.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default profile directory
_PROFILE_DIR = Path("data/model_certification/profiles")

# Cache of loaded profiles (model_id -> profile dict)
_profile_cache: dict[str, dict] = {}


def _load_profile(model_id: str, profile_dir: Path | None = None) -> dict | None:
    """Load the latest profile for a model.

    Looks for files matching {slug}_latest.json or {slug}_*.json
    (picks the most recent).
    """
    if model_id in _profile_cache:
        return _profile_cache[model_id]

    search_dir = profile_dir or _PROFILE_DIR
    if not search_dir.exists():
        return None

    slug = model_id.replace("/", "_")

    # Try _latest.json first
    latest = search_dir / f"{slug}_latest.json"
    if latest.exists():
        try:
            data = json.loads(latest.read_text(encoding="utf-8"))
            _profile_cache[model_id] = data
            return data
        except Exception:
            pass

    # Fall back to most recent timestamped file
    candidates = sorted(search_dir.glob(f"{slug}_*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _profile_cache[model_id] = data
            return data
        except Exception:
            continue

    return None


class TokenBudgetResolver:
    """Resolve the correct max_tokens for a given model + stage.

    If the model has a token profile showing it's a thinking model,
    the resolver inflates max_tokens to account for the reasoning budget.
    """

    # Default content budget per stage category (tokens of actual output needed)
    STAGE_CONTENT_BUDGETS: dict[str, int] = {
        "gap_analysis": 1500,
        "gap_reflection": 1000,
        "idea_generation": 2000,
        "idea_reflection": 1000,
        "novelty_checking": 1500,
        "feasibility_scoring": 1000,
        "proposal_synthesis": 3000,
        "adversarial_review": 1500,
        "evaluation": 1000,
        "paper_synthesis": 4000,
        "citation_audit": 1000,
        "default": 1500,
    }

    def __init__(self, profile_dir: str | Path | None = None) -> None:
        self._profile_dir = Path(profile_dir) if profile_dir else _PROFILE_DIR

    def resolve_max_tokens(
        self,
        model_id: str,
        requested_max_tokens: int,
        stage: str | None = None,
    ) -> int:
        """Return the max_tokens to actually use.

        For non-thinking models: returns requested_max_tokens unchanged.
        For thinking models: returns max(requested_max_tokens, computed_safe_minimum).

        The computed_safe_minimum is:
            peak_reasoning + buffer + stage_content_budget

        Args:
            model_id: The model being called.
            requested_max_tokens: What the caller asked for.
            stage: Pipeline stage name (for content budget lookup).

        Returns:
            The adjusted max_tokens value.
        """
        profile = _load_profile(model_id, self._profile_dir)
        if not profile:
            return requested_max_tokens

        # Check if this is a thinking model
        capabilities = profile.get("capabilities", {})
        if not capabilities.get("is_thinking_model", False):
            return requested_max_tokens

        token_profile = profile.get("token_profile", {})
        pipeline_routing = profile.get("pipeline_routing", {})

        peak_reasoning = token_profile.get("peak_reasoning_observed", 0)
        buffer = token_profile.get("recommended_buffer", 200)

        # Use min_pipeline_max_tokens from profile if available
        min_safe = pipeline_routing.get("min_pipeline_max_tokens", 0)

        # Compute stage-specific safe minimum
        content_budget = self.STAGE_CONTENT_BUDGETS.get(
            stage or "default",
            self.STAGE_CONTENT_BUDGETS["default"],
        )
        computed_safe = peak_reasoning + buffer + content_budget

        # Use the higher of: min_safe from profile, computed stage-specific, or requested
        safe_minimum = max(min_safe, computed_safe)

        if safe_minimum > requested_max_tokens:
            logger.debug(
                "TokenBudgetResolver: inflating max_tokens %d -> %d for '%s' "
                "(thinking model, stage=%s, peak_reasoning=%d, content_budget=%d)",
                requested_max_tokens, safe_minimum, model_id,
                stage or "unknown", peak_reasoning, content_budget,
            )
            return safe_minimum

        return requested_max_tokens

    def get_model_info(self, model_id: str) -> dict[str, Any] | None:
        """Get cached profile info for a model."""
        return _load_profile(model_id, self._profile_dir)


# Singleton instance (lazy-initialized)
_resolver: TokenBudgetResolver | None = None


def get_token_budget_resolver() -> TokenBudgetResolver:
    """Get the singleton TokenBudgetResolver."""
    global _resolver
    if _resolver is None:
        _resolver = TokenBudgetResolver()
    return _resolver
