"""Metacognitive self-monitoring and intervention.

Self-monitoring consumer that reads TruthValue, activation levels,
and Borda scores to detect quality degradation, stagnation, or
anomalous patterns. Emits intervention signals when thresholds are
crossed.

Adopted from python_actr (self-monitoring module), Soar (meta-cognitive
interrupts), and det-acp (policy-gated intervention).
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    QUALITY_DROP = "quality_drop"
    STAGNATION = "stagnation"
    ANOMALY = "anomaly"
    BUDGET_EXCEEDED = "budget_exceeded"
    CONVERGENCE_STALL = "convergence_stall"


class InterventionSignal(BaseModel):
    """A metacognitive intervention signal."""

    signal_type: SignalType
    severity: float = 0.0  # 0.0-1.0
    source: str = ""
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class MonitoringThresholds(BaseModel):
    """Configurable thresholds for metacognitive monitoring."""

    quality_drop_threshold: float = 0.3  # Score delta triggering quality drop
    stagnation_rounds: int = 3  # Rounds with no improvement
    anomaly_score_threshold: float = 2.0  # Std deviations from mean
    convergence_stall_rounds: int = 5  # Rounds without convergence
    min_observations: int = 3  # Minimum data before monitoring


class MetacognitiveMonitor:
    """Self-monitoring system that emits intervention signals.

    Consumes metrics from the pipeline (scores, truth values, round
    progress) and emits signals when quality degrades, progress stalls,
    or anomalous patterns are detected.

    Usage:
        monitor = MetacognitiveMonitor()
        monitor.observe(score=0.8, round_num=1)
        monitor.observe(score=0.3, round_num=2)  # Quality drop!
        signals = monitor.check()
        # signals contains a QUALITY_DROP signal
    """

    def __init__(self, thresholds: MonitoringThresholds | None = None):
        self._thresholds = thresholds or MonitoringThresholds()
        self._observations: list[dict[str, Any]] = []
        self._signals: list[InterventionSignal] = []
        self._last_scores: list[float] = []

    def observe(self, **kwargs) -> None:
        self._observations.append({"timestamp": time.time(), **kwargs})
        if "score" in kwargs:
            self._last_scores.append(kwargs["score"])

    def check(self) -> list[InterventionSignal]:
        new_signals = []
        new_signals.extend(self._check_quality_drop())
        new_signals.extend(self._check_stagnation())
        new_signals.extend(self._check_convergence_stall())
        self._signals.extend(new_signals)
        return new_signals

    @property
    def signals(self) -> list[InterventionSignal]:
        return list(self._signals)

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    @property
    def latest_score(self) -> float | None:
        return self._last_scores[-1] if self._last_scores else None

    def _check_quality_drop(self) -> list[InterventionSignal]:
        if len(self._last_scores) < 2:
            return []
        signals = []
        for i in range(1, len(self._last_scores)):
            delta = self._last_scores[i] - self._last_scores[i - 1]
            if delta < -self._thresholds.quality_drop_threshold:
                signals.append(
                    InterventionSignal(
                        signal_type=SignalType.QUALITY_DROP,
                        severity=min(1.0, abs(delta)),
                        message=f"Score dropped by {abs(delta):.2f}: {self._last_scores[i-1]:.2f} -> {self._last_scores[i]:.2f}",
                        data={
                            "delta": delta,
                            "from": self._last_scores[i - 1],
                            "to": self._last_scores[i],
                        },
                    )
                )
        return signals

    def _check_stagnation(self) -> list[InterventionSignal]:
        n = self._thresholds.stagnation_rounds
        if len(self._last_scores) < n + 1:
            return []
        recent = self._last_scores[-(n + 1) :]
        deltas = [abs(recent[i] - recent[i - 1]) for i in range(1, len(recent))]
        if all(d < 0.01 for d in deltas):
            return [
                InterventionSignal(
                    signal_type=SignalType.STAGNATION,
                    severity=0.5,
                    message=f"No meaningful improvement for {n} rounds",
                    data={"recent_scores": recent, "deltas": deltas},
                )
            ]
        return []

    def _check_convergence_stall(self) -> list[InterventionSignal]:
        rounds = [o for o in self._observations if "round_num" in o and "converged" in o]
        if len(rounds) < self._thresholds.convergence_stall_rounds:
            return []
        recent = rounds[-self._thresholds.convergence_stall_rounds :]
        if all(not r.get("converged", False) for r in recent):
            return [
                InterventionSignal(
                    signal_type=SignalType.CONVERGENCE_STALL,
                    severity=0.7,
                    message=f"No convergence in {self._thresholds.convergence_stall_rounds} rounds",
                    data={"rounds_checked": len(recent)},
                )
            ]
        return []
