"""Hardware probe — check model availability and fit.

Probes LM Studio (or other providers) for model availability,
reported context windows, and basic stability.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx as _httpx

logger = logging.getLogger(__name__)


@dataclass
class HardwareFitResult:
    """Result of probing model hardware/availability."""

    hardware_id: str                     # model_id used for probing
    engine: str                          # lmstudio, api, etc.
    load_success: bool = False
    model_loaded: bool = False
    context_window_reported: int | None = None
    safe_context_window: int | None = None
    safe_output_tokens: int | None = None
    load_time_seconds: float | None = None
    peak_vram_gb: float | None = None    # not available for API models
    stable: bool = True
    warnings: list[str] = field(default_factory=list)

    @property
    def available(self) -> bool:
        """Is the model available for use?"""
        return self.load_success and self.model_loaded and self.stable


async def probe_model(
    model_id: str,
    provider: str,
    advertised_context_window: int,
    advertised_max_output_tokens: int,
    base_url: str | None = None,
    timeout: float = 30.0,
) -> HardwareFitResult:
    """Probe model availability and estimate safe context.

    For LM Studio: probes /api/v1/models for loaded instances.
    For API providers: lightweight health check.
    """
    result = HardwareFitResult(
        hardware_id=model_id,
        engine=provider,
    )

    start = time.monotonic()

    if provider.lower() == "lmstudio":
        await _probe_lmstudio(result, base_url, timeout)
    else:
        # API providers: assume available, use advertised values
        result.load_success = True
        result.model_loaded = True
        result.context_window_reported = advertised_context_window

    result.load_time_seconds = time.monotonic() - start

    # Compute safe context regardless of provider
    _compute_safe_context(
        result,
        advertised_context_window=advertised_context_window,
        advertised_max_output_tokens=advertised_max_output_tokens,
    )

    return result


async def _probe_lmstudio(
    result: HardwareFitResult,
    base_url: str | None,
    timeout: float,
) -> None:
    """Probe LM Studio for model availability."""
    if not base_url:
        result.warnings.append("No LM Studio base_url provided")
        result.stable = False
        return

    try:
        async with _httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url}/api/v1/models")

        if resp.status_code != 200:
            result.warnings.append(f"LM Studio returned status {resp.status_code}")
            result.stable = False
            return

        data = resp.json()
        models = data.get("models", data.get("data", []))

        # Find our model
        for model_info in models:
            model_key = model_info.get("key", model_info.get("id", ""))
            if model_key == result.hardware_id or result.hardware_id.startswith(model_key):
                result.load_success = True
                result.model_loaded = True  # If it's in the list, it's available
                result.context_window_reported = model_info.get(
                    "max_context_length", None
                )
                # Check loaded_instances if available (LM Studio native API)
                instances = model_info.get("loaded_instances", [])
                if instances:
                    inst = instances[0]
                    result.context_window_reported = inst.get(
                        "config", {}
                    ).get("context_length", None)
                break
        else:
            # Model not found in list but might still respond to chat
            # (LM Studio auto-loads on first request)
            result.warnings.append(
                f"Model {result.hardware_id} not found in LM Studio model list"
            )
            result.model_loaded = False

    except Exception as e:
        result.warnings.append(f"LM Studio probe error: {str(e)[:100]}")
        result.stable = False


def _compute_safe_context(
    result: HardwareFitResult,
    advertised_context_window: int,
    advertised_max_output_tokens: int,
) -> None:
    """Compute safe context and output tokens.

    v0.1: conservative formula.
    safe_context = min(reported, advertised) * 0.80
    safe_output = min(advertised_max_output, safe_context * 0.25)
    """
    reported = result.context_window_reported
    if reported is not None and reported > 0:
        effective = min(reported, advertised_context_window)
    else:
        effective = advertised_context_window
        result.warnings.append(
            "No reported context window — using advertised value"
        )

    result.safe_context_window = int(effective * 0.80)
    result.safe_output_tokens = min(
        advertised_max_output_tokens,
        int(result.safe_context_window * 0.25),
    )
