"""Context Window Registry — maps models to their maximum context sizes.

BATCH-RAG-06: Provides a lookup for model context window sizes so the
TokenBudgetGuard can automatically configure budgets based on the
model being used for each stage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelContextInfo:
    """Context window info for a specific model."""

    model_id: str
    max_tokens: int
    provider: str  # "local" | "cloud" | "hybrid"
    family: str = ""  # e.g., "qwen", "glm", "gpt"
    recommended_budget: int = 0  # 80% of max_tokens for safety

    def __post_init__(self):
        if self.recommended_budget == 0:
            self.recommended_budget = int(self.max_tokens * 0.8)


# Registry of known models and their context windows
MODEL_CONTEXT_REGISTRY: dict[str, ModelContextInfo] = {
    # Local LM Studio models
    "qwen/qwen3-4b-2507": ModelContextInfo(
        model_id="qwen/qwen3-4b-2507",
        max_tokens=4096,
        provider="local",
        family="qwen",
    ),
    "qwen3-4b": ModelContextInfo(
        model_id="qwen3-4b",
        max_tokens=4096,
        provider="local",
        family="qwen",
    ),
    "qwen2.5-7b": ModelContextInfo(
        model_id="qwen2.5-7b",
        max_tokens=32768,
        provider="local",
        family="qwen",
    ),
    "llama-3.1-8b": ModelContextInfo(
        model_id="llama-3.1-8b",
        max_tokens=8192,
        provider="local",
        family="llama",
    ),
    "mistral-7b": ModelContextInfo(
        model_id="mistral-7b",
        max_tokens=8192,
        provider="local",
        family="mistral",
    ),

    # Cloud models
    "glm-5.1": ModelContextInfo(
        model_id="glm-5.1",
        max_tokens=8192,
        provider="cloud",
        family="glm",
    ),
    "gpt-4o": ModelContextInfo(
        model_id="gpt-4o",
        max_tokens=128000,
        provider="cloud",
        family="gpt",
    ),
    "gpt-4o-mini": ModelContextInfo(
        model_id="gpt-4o-mini",
        max_tokens=128000,
        provider="cloud",
        family="gpt",
    ),
    "claude-3.5-sonnet": ModelContextInfo(
        model_id="claude-3.5-sonnet",
        max_tokens=200000,
        provider="cloud",
        family="claude",
    ),

    # Default fallback
    "default": ModelContextInfo(
        model_id="default",
        max_tokens=4096,
        provider="local",
        family="unknown",
    ),
}


def get_model_context(model_id: str) -> ModelContextInfo:
    """Get context window info for a model.

    Tries exact match first, then prefix match, then default.
    """
    # Exact match
    if model_id in MODEL_CONTEXT_REGISTRY:
        return MODEL_CONTEXT_REGISTRY[model_id]

    # Prefix/family match
    model_lower = model_id.lower()
    for key, info in MODEL_CONTEXT_REGISTRY.items():
        if key in model_lower or model_lower.startswith(key.split("/")[0]):
            return info

    # Family match
    for family in ["qwen", "llama", "mistral", "glm", "gpt", "claude"]:
        if family in model_lower:
            for info in MODEL_CONTEXT_REGISTRY.values():
                if info.family == family:
                    return info

    # Default
    logger.debug("Unknown model '%s', using default context", model_id)
    return MODEL_CONTEXT_REGISTRY["default"]


def get_recommended_budget(model_id: str, safety_factor: float = 0.8) -> int:
    """Get recommended token budget for a model.

    Parameters
    ----------
    model_id:
        Model identifier string.
    safety_factor:
        Fraction of max_tokens to use as budget (default 80%).
    """
    info = get_model_context(model_id)
    return int(info.max_tokens * safety_factor)


def list_models() -> list[dict]:
    """List all registered models with their context info."""
    return [
        {
            "model_id": info.model_id,
            "max_tokens": info.max_tokens,
            "provider": info.provider,
            "family": info.family,
            "recommended_budget": info.recommended_budget,
        }
        for info in MODEL_CONTEXT_REGISTRY.values()
        if info.model_id != "default"
    ]
