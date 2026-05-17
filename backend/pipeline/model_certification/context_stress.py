"""Safe context estimation.

v0.1: conservative formula-based estimation.
v0.2: real stress testing with measured confidence.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.pipeline.model_certification.hardware_probe import HardwareFitResult


@dataclass
class ContextEstimate:
    """Estimated safe context window."""

    safe_tokens: int
    confidence: str  # "estimated" (v0.1) or "measured" (v0.2)
    method: str      # "conservative_formula" or "stress_test"
    derating_factor: float
    source_context: int  # the context value that was derated


def estimate_safe_context(
    hardware: HardwareFitResult,
    advertised_context_window: int,
) -> ContextEstimate:
    """Estimate safe context window from hardware probe results.

    v0.1 uses a conservative 80% derating factor applied to the
    smaller of reported vs advertised context. This is labeled as
    "estimated" confidence. v0.2 will replace this with actual
    stress testing producing "measured" confidence.
    """
    reported = hardware.context_window_reported

    if reported is not None and reported > 0:
        effective = min(reported, advertised_context_window)
    else:
        effective = advertised_context_window

    derating = 0.80
    safe = int(effective * derating)

    return ContextEstimate(
        safe_tokens=safe,
        confidence="estimated",
        method="conservative_formula",
        derating_factor=derating,
        source_context=effective,
    )
