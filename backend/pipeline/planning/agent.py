"""Pre-execution planning agent.

Creates a stage-by-stage execution plan with time/token estimates
and blocker identification before pipeline execution begins.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default time estimates per stage (seconds)
DEFAULT_TIME_ESTIMATES = {
    "literature_search": 60,
    "ingestion": 30,
    "gap_analysis": 45,
    "idea_generation": 90,
    "novelty_checking": 30,
    "feasibility_scoring": 20,
    "mechanical_metrics": 10,
    "proposal_synthesis": 120,
    "export": 5,
}

# Default token estimates per stage
DEFAULT_TOKEN_ESTIMATES = {
    "literature_search": 0,
    "ingestion": 500,
    "gap_analysis": 2000,
    "idea_generation": 3000,
    "novelty_checking": 1500,
    "feasibility_scoring": 1000,
    "mechanical_metrics": 200,
    "proposal_synthesis": 4000,
    "export": 100,
}


@dataclass
class StagePlan:
    """Plan for a single pipeline stage."""
    stage_name: str
    enabled: bool = True
    estimated_time_s: float = 0.0
    estimated_tokens: int = 0
    dependencies: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class ExecutionPlan:
    """Complete execution plan for a pipeline run."""
    stages: list[StagePlan] = field(default_factory=list)
    total_estimated_time_s: float = 0.0
    total_estimated_tokens: int = 0
    blockers: list[str] = field(default_factory=list)
    strategy: str = "deep_research"
    domain: str = ""

    @property
    def enabled_stages(self) -> list[StagePlan]:
        return [s for s in self.stages if s.enabled]

    @property
    def has_blockers(self) -> bool:
        return bool(self.blockers)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "domain": self.domain,
            "total_estimated_time_s": self.total_estimated_time_s,
            "total_estimated_tokens": self.total_estimated_tokens,
            "blockers": self.blockers,
            "stages": [
                {
                    "name": s.stage_name,
                    "enabled": s.enabled,
                    "estimated_time_s": s.estimated_time_s,
                    "estimated_tokens": s.estimated_tokens,
                    "dependencies": s.dependencies,
                    "blockers": s.blockers,
                }
                for s in self.stages
            ],
        }


class PlanningAgent:
    """Pre-execution planner for pipeline runs.

    Analyzes the requested strategy and domain to create an
    execution plan with estimates and blocker identification.
    """

    def __init__(
        self,
        time_estimates: dict[str, float] | None = None,
        token_estimates: dict[str, int] | None = None,
        stage_order: list[str] | None = None,
    ) -> None:
        self._time_estimates = time_estimates or DEFAULT_TIME_ESTIMATES
        self._token_estimates = token_estimates or DEFAULT_TOKEN_ESTIMATES
        self._stage_order = stage_order or list(self._time_estimates.keys())

    def plan(
        self,
        domain: str = "",
        strategy: str = "deep_research",
        disabled_stages: list[str] | None = None,
    ) -> ExecutionPlan:
        """Create an execution plan.

        Args:
            domain: Research domain.
            strategy: Pipeline strategy.
            disabled_stages: Stages to skip (e.g. from fast_scan strategy).

        Returns:
            ExecutionPlan with per-stage estimates.
        """
        disabled = set(disabled_stages or [])
        stages: list[StagePlan] = []
        total_time = 0.0
        total_tokens = 0
        blockers: list[str] = []

        for i, stage_name in enumerate(self._stage_order):
            enabled = stage_name not in disabled

            # Dependency: each stage depends on the previous one
            deps = [self._stage_order[i - 1]] if i > 0 else []

            # Estimate
            est_time = self._time_estimates.get(stage_name, 30)
            est_tokens = self._token_estimates.get(stage_name, 500)

            # Strategy adjustments
            if strategy == "fast_scan":
                est_time *= 0.5
                est_tokens *= 0.5

            # Blocker detection
            stage_blockers = []
            if stage_name == "literature_search" and not domain:
                stage_blockers.append("No domain specified — search may return empty")
            if stage_name == "proposal_synthesis" and "idea_generation" in disabled:
                stage_blockers.append("Idea generation disabled — synthesis may lack content")

            if enabled:
                total_time += est_time
                total_tokens += est_tokens

            stages.append(StagePlan(
                stage_name=stage_name,
                enabled=enabled,
                estimated_time_s=est_time if enabled else 0,
                estimated_tokens=est_tokens if enabled else 0,
                dependencies=deps,
                blockers=stage_blockers,
            ))

            blockers.extend(stage_blockers)

        return ExecutionPlan(
            stages=stages,
            total_estimated_time_s=total_time,
            total_estimated_tokens=total_tokens,
            blockers=blockers,
            strategy=strategy,
            domain=domain,
        )
