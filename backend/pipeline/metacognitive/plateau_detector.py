"""PlateauDetector — identifies when quality scores stop improving."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.pipeline.metacognitive.ledger import ProgressLedger


@dataclass
class PlateauResult:
    is_plateau: bool = False
    reason: str = ""
    values: list[float] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class PlateauDetector:
    def __init__(
        self,
        window_size: int = 3,
        threshold: float = 0.02,
        max_evals: int = 5,
    ) -> None:
        self._window_size = window_size
        self._threshold = threshold
        self._max_evals = max_evals

    def detect(self, ledger: ProgressLedger, metric: str) -> PlateauResult:
        values = ledger.trajectory(metric)

        if len(values) < self._window_size:
            return PlateauResult(
                is_plateau=False,
                reason=f"Insufficient data: {len(values)} entries, need {self._window_size}",
                values=values,
            )

        window = values[-self._window_size:]

        # Check 1: low variance (std_dev below threshold)
        std_dev = _std_dev(window)
        if std_dev < self._threshold:
            return PlateauResult(
                is_plateau=True,
                reason=f"Low variance plateau (std_dev={std_dev:.4f} < {self._threshold})",
                values=window,
                suggestions=["retry_with_different_strategy", "increase_rounds", "relax_quality_gate"],
            )

        # Check 2: stagnation — many evaluations without improvement
        if len(values) >= self._max_evals:
            recent = values[-self._max_evals:]
            best = max(recent)
            if recent[-1] <= best and all(v <= best for v in recent[1:]):
                return PlateauResult(
                    is_plateau=True,
                    reason=f"Stagnation: no improvement over last {self._max_evals} evaluations",
                    values=recent,
                    suggestions=["change_strategy", "abort"],
                )

        return PlateauResult(
            is_plateau=False,
            reason="Scores improving or fluctuating normally",
            values=window,
        )


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
