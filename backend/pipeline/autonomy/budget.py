"""Budget and resource management for pipeline execution.

Adopted from mcp-agent's Budget-Policy-Verifier trio. Tracks token
usage, cost, and time per pipeline stage with policy-based decisions.
"""

import logging
import time
from enum import Enum

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BudgetPolicy(str, Enum):
    CONTINUE = "continue"    # Within budget, proceed normally
    REPLAN = "replan"        # Approaching limit, drop low-priority stages
    STOP = "stop"            # Over budget, halt pipeline


class StageCost(BaseModel):
    stage_name: str
    token_count: int = 0
    estimated_cost_usd: float = 0.0
    elapsed_seconds: float = 0.0


class BudgetSnapshot(BaseModel):
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_seconds: float = 0.0
    by_stage: dict[str, StageCost] = {}


class SimpleBudget:
    """Track token/cost/time per pipeline stage."""

    def __init__(
        self,
        max_tokens: int = 500000,
        max_cost_usd: float = 10.0,
        max_seconds: float = 600,
    ):
        self._max_tokens = max_tokens
        self._max_cost_usd = max_cost_usd
        self._max_seconds = max_seconds
        self._stages: dict[str, StageCost] = {}
        self._start_time: float | None = None

    def start(self) -> None:
        """Mark the start of pipeline execution."""
        self._start_time = time.time()

    def record(self, stage: str, tokens: int, cost_usd: float = 0.0, elapsed: float = 0.0) -> None:
        """Record resource usage for a stage."""
        if stage in self._stages:
            existing = self._stages[stage]
            self._stages[stage] = StageCost(
                stage_name=stage,
                token_count=existing.token_count + tokens,
                estimated_cost_usd=existing.estimated_cost_usd + cost_usd,
                elapsed_seconds=existing.elapsed_seconds + elapsed,
            )
        else:
            self._stages[stage] = StageCost(
                stage_name=stage,
                token_count=tokens,
                estimated_cost_usd=cost_usd,
                elapsed_seconds=elapsed,
            )

    def snapshot(self) -> BudgetSnapshot:
        """Get current budget usage."""
        total_elapsed = (time.time() - self._start_time) if self._start_time else 0.0
        return BudgetSnapshot(
            total_tokens=sum(s.token_count for s in self._stages.values()),
            total_cost_usd=sum(s.estimated_cost_usd for s in self._stages.values()),
            total_seconds=total_elapsed,
            by_stage=dict(self._stages),
        )

    def check_policy(self, remaining_stages: list[str] | None = None) -> BudgetPolicy:
        """Decide whether to continue, replan, or stop based on budget."""
        snap = self.snapshot()

        # Hard stops
        if snap.total_tokens >= self._max_tokens:
            logger.warning("Budget STOP: tokens %d >= %d", snap.total_tokens, self._max_tokens)
            return BudgetPolicy.STOP
        if snap.total_cost_usd >= self._max_cost_usd:
            logger.warning("Budget STOP: cost $%.2f >= $%.2f", snap.total_cost_usd, self._max_cost_usd)
            return BudgetPolicy.STOP
        if snap.total_seconds >= self._max_seconds:
            logger.warning("Budget STOP: time %.1fs >= %.1fs", snap.total_seconds, self._max_seconds)
            return BudgetPolicy.STOP

        # Replan thresholds (80% of budget)
        if snap.total_tokens >= self._max_tokens * 0.8:
            return BudgetPolicy.REPLAN
        if snap.total_cost_usd >= self._max_cost_usd * 0.8:
            return BudgetPolicy.REPLAN

        return BudgetPolicy.CONTINUE


class PlanVerifier:
    """Validate plans before execution to estimate cost."""

    # Rough estimates per pipeline stage
    STAGE_ESTIMATES: dict[str, dict] = {
        "literature_search": {"tokens": 5000, "cost_usd": 0.02},
        "ingestion": {"tokens": 10000, "cost_usd": 0.05},
        "gap_analysis": {"tokens": 20000, "cost_usd": 0.10},
        "idea_generation": {"tokens": 50000, "cost_usd": 0.25},
        "novelty_checking": {"tokens": 30000, "cost_usd": 0.15},
        "feasibility_scoring": {"tokens": 20000, "cost_usd": 0.10},
        "proposal_synthesis": {"tokens": 30000, "cost_usd": 0.15},
        "export": {"tokens": 2000, "cost_usd": 0.01},
    }

    def estimate_cost(self, params: dict) -> BudgetSnapshot:
        """Estimate total cost for a pipeline run with given parameters."""
        rounds = params.get("generation_rounds", 2)
        ideas_per = params.get("ideas_per_round", 3)

        total_tokens = 0
        total_cost = 0.0
        by_stage = {}

        for stage, estimates in self.STAGE_ESTIMATES.items():
            tokens = estimates["tokens"]
            cost = estimates["cost_usd"]

            # Scale generation stages by rounds and ideas
            if stage == "idea_generation":
                tokens = int(tokens * rounds * ideas_per / 3)
                cost = cost * rounds * ideas_per / 3
            elif stage in ("novelty_checking", "feasibility_scoring", "proposal_synthesis"):
                tokens = int(tokens * ideas_per / 3)
                cost = cost * ideas_per / 3

            by_stage[stage] = StageCost(
                stage_name=stage,
                token_count=int(tokens),
                estimated_cost_usd=round(cost, 4),
            )
            total_tokens += int(tokens)
            total_cost += cost

        return BudgetSnapshot(
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            total_seconds=0.0,
            by_stage=by_stage,
        )

    def validate(self, params: dict, budget: SimpleBudget) -> tuple[bool, str]:
        """Validate that a plan fits within budget."""
        estimate = self.estimate_cost(params)
        snap = budget.snapshot()

        remaining_tokens = budget._max_tokens - snap.total_tokens
        remaining_cost = budget._max_cost_usd - snap.total_cost_usd

        if estimate.total_tokens > remaining_tokens:
            return False, f"Estimated {estimate.total_tokens} tokens exceeds remaining {remaining_tokens}"
        if estimate.total_cost_usd > remaining_cost:
            return False, f"Estimated ${estimate.total_cost_usd:.2f} exceeds remaining ${remaining_cost:.2f}"

        return True, f"Plan fits: ~{estimate.total_tokens} tokens, ~${estimate.total_cost_usd:.2f}"
