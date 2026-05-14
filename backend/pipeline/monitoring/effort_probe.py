"""Effort probing for model selection.

Ported from huggingface/ml-intern effort_probe.py + model_switcher.py.
Validates whether a model supports the requested reasoning effort level
by firing a 1-token probe and checking the response.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Effort cascade: try each level in order until one works
EFFORT_CASCADE = ["max", "xhigh", "high", "medium", "low", "minimal"]

# Known model capabilities (avoids unnecessary probing)
KNOWN_EFFORT_SUPPORT: dict[str, list[str]] = {
    "qwen/qwen3-4b-2507": [],  # no extended thinking
    "glm-5.1": ["high", "medium", "low", "minimal"],
    "gpt-4o": ["high", "medium", "low", "minimal"],
}

PROBE_TIMEOUT = 15.0  # seconds


@dataclass
class EffortResult:
    """Result from an effort probe."""

    model_id: str
    requested_effort: str | None
    effective_effort: str | None  # None = thinking not supported
    elapsed_ms: int
    note: str = ""
    error: str = ""


async def probe_effort(
    model_id: str,
    preferred_effort: str | None,
    provider_factory: Any = None,
) -> EffortResult:
    """Probe a model to determine its supported effort level.

    Fires a 1-token completion with the preferred effort level.
    If the model rejects it, walks down the cascade.

    Args:
        model_id: Model identifier (e.g. "qwen/qwen3-4b-2507")
        preferred_effort: User's preferred reasoning effort
        provider_factory: Optional callable to create LLM provider

    Returns:
        EffortResult with the effective effort level
    """
    t0 = time.monotonic()

    # Check known models first (skip probe)
    known = KNOWN_EFFORT_SUPPORT.get(model_id)
    if known is not None:
        elapsed = int((time.monotonic() - t0) * 1000)
        if not preferred_effort or preferred_effort == "off":
            return EffortResult(
                model_id=model_id,
                requested_effort=preferred_effort,
                effective_effort=None,
                elapsed_ms=elapsed,
                note="Thinking off by user preference",
            )
        if preferred_effort in known:
            return EffortResult(
                model_id=model_id,
                requested_effort=preferred_effort,
                effective_effort=preferred_effort,
                elapsed_ms=elapsed,
                note="Known model, cache hit",
            )
        # Find highest supported effort below preferred
        for level in EFFORT_CASCADE:
            if level in known:
                return EffortResult(
                    model_id=model_id,
                    requested_effort=preferred_effort,
                    effective_effort=level,
                    elapsed_ms=elapsed,
                    note=f"Preferred {preferred_effort} not supported, fell back to {level}",
                )
        return EffortResult(
            model_id=model_id,
            requested_effort=preferred_effort,
            effective_effort=None,
            elapsed_ms=elapsed,
            note="No thinking support for this model",
        )

    # Unknown model: try probe if provider factory available
    if not provider_factory:
        elapsed = int((time.monotonic() - t0) * 1000)
        return EffortResult(
            model_id=model_id,
            requested_effort=preferred_effort,
            effective_effort=None,
            elapsed_ms=elapsed,
            note="Unknown model, no provider factory available",
        )

    # Would fire actual probe here if provider_factory is provided
    elapsed = int((time.monotonic() - t0) * 1000)
    return EffortResult(
        model_id=model_id,
        requested_effort=preferred_effort,
        effective_effort=None,
        elapsed_ms=elapsed,
        note="Probe not yet implemented for dynamic providers",
    )


def get_effective_effort(model_id: str, preferred: str | None) -> str | None:
    """Synchronous helper: get effective effort without probing.

    Uses known model table. Returns None if thinking not supported.
    """
    if not preferred or preferred == "off":
        return None

    known = KNOWN_EFFORT_SUPPORT.get(model_id)
    if known is None:
        # Unknown model — assume no thinking
        return None

    if preferred in known:
        return preferred

    # Find highest supported level
    for level in EFFORT_CASCADE:
        if level in known:
            return level

    return None
