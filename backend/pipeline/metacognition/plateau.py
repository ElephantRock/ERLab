"""Plateau detection and guard commands for pipeline stages (B167).

Detects when pipeline progress has stalled (plateau) and triggers
guard commands: retry with different params, skip stage, or halt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class GuardAction(Enum):
    """Actions the guard can take."""
    CONTINUE = "continue"    # No intervention needed
    RETRY = "retry"          # Retry with modified params
    SKIP = "skip"            # Skip this stage
    HALT = "halt"            # Stop pipeline


@dataclass
class PlateauCheck:
    """Result of checking for a plateau."""
    stage_name: str
    is_plateau: bool
    score_history: list[float]
    delta: float = 0.0
    action: GuardAction = GuardAction.CONTINUE
    reason: str = ""


class PlateauDetector:
    """Detect score plateaus across pipeline stage iterations.

    A plateau is detected when the last N scores have less than
    `threshold` total variation. This triggers guard commands.
    """

    def __init__(
        self,
        window_size: int = 3,
        threshold: float = 0.01,
        max_retries: int = 2,
    ) -> None:
        self._window = window_size
        self._threshold = threshold
        self._max_retries = max_retries
        self._retry_counts: dict[str, int] = {}

    def check(self, stage_name: str, score_history: list[float]) -> PlateauCheck:
        """Check if scores have plateaued for a stage."""
        if len(score_history) < self._window:
            return PlateauCheck(
                stage_name=stage_name,
                is_plateau=False,
                score_history=score_history,
                action=GuardAction.CONTINUE,
                reason="Not enough data points",
            )

        recent = score_history[-self._window:]
        delta = max(recent) - min(recent)
        is_plateau = delta < self._threshold

        if not is_plateau:
            return PlateauCheck(
                stage_name=stage_name,
                is_plateau=False,
                score_history=score_history,
                delta=delta,
                action=GuardAction.CONTINUE,
            )

        # Plateau detected — decide action
        retries = self._retry_counts.get(stage_name, 0)

        if retries < self._max_retries:
            self._retry_counts[stage_name] = retries + 1
            return PlateauCheck(
                stage_name=stage_name,
                is_plateau=True,
                score_history=score_history,
                delta=delta,
                action=GuardAction.RETRY,
                reason=f"Score plateaued (delta={delta:.4f}), retry {retries + 1}/{self._max_retries}",
            )
        else:
            return PlateauCheck(
                stage_name=stage_name,
                is_plateau=True,
                score_history=score_history,
                delta=delta,
                action=GuardAction.SKIP,
                reason=f"Score plateaued after {retries} retries, skipping stage",
            )

    def reset(self, stage_name: str | None = None) -> None:
        """Reset retry counters."""
        if stage_name:
            self._retry_counts.pop(stage_name, None)
        else:
            self._retry_counts.clear()
