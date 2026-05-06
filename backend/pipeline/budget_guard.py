"""Budget guard: enforces time and cost limits on pipeline runs.

Monitors elapsed time and accumulated cost. When approaching limits,
degrades gracefully by skipping optional stages and reducing scope.
Never crashes the pipeline (HB-01).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BudgetAction(str, Enum):
    CONTINUE = "continue"
    DEGRADE = "degrade"      # Skip optional stages
    STOP = "stop"            # Stop pipeline gracefully


@dataclass
class BudgetConfig:
    """Budget configuration for a pipeline run."""
    max_time_s: float = 0.0      # 0 = unlimited
    max_cost_usd: float = 0.0    # 0 = unlimited
    degrade_threshold: float = 0.8  # Trigger degradation at 80% of limit


@dataclass
class BudgetStatus:
    """Current budget status."""
    elapsed_s: float = 0.0
    cost_usd: float = 0.0
    action: BudgetAction = BudgetAction.CONTINUE
    should_skip_stage: bool = False
    message: str = ""


class BudgetGuard:
    """Enforces time and cost limits on pipeline runs.

    Usage:
        guard = BudgetGuard(config)
        guard.start()
        # Before each stage:
        status = guard.check()
        if status.action == BudgetAction.STOP:
            break
        if status.should_skip_stage and stage_is_optional:
            continue
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()
        self._start_time: float = 0.0
        self._cost_usd: float = 0.0

    def start(self) -> None:
        """Start the budget timer."""
        self._start_time = time.monotonic()

    def update_cost(self, cost_usd: float) -> None:
        """Update accumulated cost."""
        self._cost_usd += cost_usd

    def check(self, current_stage: str = "") -> BudgetStatus:
        """Check budget status. Returns action to take."""
        if self._start_time == 0:
            return BudgetStatus(action=BudgetAction.CONTINUE)

        elapsed = time.monotonic() - self._start_time

        # Check time limit
        if self._config.max_time_s > 0:
            time_pct = elapsed / self._config.max_time_s

            if time_pct >= 1.0:
                return BudgetStatus(
                    elapsed_s=elapsed,
                    cost_usd=self._cost_usd,
                    action=BudgetAction.STOP,
                    message=f"Time limit reached ({elapsed:.0f}s / {self._config.max_time_s:.0f}s)",
                )

            if time_pct >= self._config.degrade_threshold:
                optional_stages = {"novelty_checking", "feasibility_scoring", "mechanical_metrics"}
                should_skip = current_stage in optional_stages
                return BudgetStatus(
                    elapsed_s=elapsed,
                    cost_usd=self._cost_usd,
                    action=BudgetAction.DEGRADE,
                    should_skip_stage=should_skip,
                    message=f"Approaching time limit ({time_pct:.0%}), degrading",
                )

        # Check cost limit
        if self._config.max_cost_usd > 0:
            cost_pct = self._cost_usd / self._config.max_cost_usd

            if cost_pct >= 1.0:
                return BudgetStatus(
                    elapsed_s=elapsed,
                    cost_usd=self._cost_usd,
                    action=BudgetAction.STOP,
                    message=f"Cost limit reached (${self._cost_usd:.4f} / ${self._config.max_cost_usd:.2f})",
                )

            if cost_pct >= self._config.degrade_threshold:
                optional_stages = {"novelty_checking", "feasibility_scoring", "mechanical_metrics"}
                should_skip = current_stage in optional_stages
                return BudgetStatus(
                    elapsed_s=elapsed,
                    cost_usd=self._cost_usd,
                    action=BudgetAction.DEGRADE,
                    should_skip_stage=should_skip,
                    message=f"Approaching cost limit ({cost_pct:.0%}), degrading",
                )

        return BudgetStatus(
            elapsed_s=elapsed,
            cost_usd=self._cost_usd,
            action=BudgetAction.CONTINUE,
        )

    @property
    def config(self) -> BudgetConfig:
        return self._config
