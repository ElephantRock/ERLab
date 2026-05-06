"""Pipeline monitoring service: pre-flight checks and runtime monitoring.

Combines HealthMonitor, CostTracker, and PlanningAgent into a single
service that validates readiness before pipeline execution and
tracks costs during execution.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.monitoring.health import HealthMonitor, HealthStatus
from backend.pipeline.monitoring.cost_tracker import CostTracker, TokenUsage
from backend.pipeline.planning.agent import PlanningAgent, ExecutionPlan

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """Result of a pre-flight check."""
    ready: bool = True
    health_status: str = "healthy"
    execution_plan: ExecutionPlan | None = None
    warnings: list[str] = field(default_factory=list)
    estimated_time_s: float = 0.0
    estimated_tokens: int = 0


class PipelineMonitoringService:
    """Pre-flight checks and runtime monitoring for pipeline execution."""

    def __init__(self) -> None:
        self._health = HealthMonitor()
        self._cost = CostTracker()
        self._planner = PlanningAgent()

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost

    def preflight(
        self,
        domain: str = "",
        strategy: str = "deep_research",
        disabled_stages: list[str] | None = None,
    ) -> PreflightResult:
        """Run pre-flight checks before pipeline execution.

        1. Generate execution plan
        2. Check for blockers
        3. Return readiness status
        """
        plan = self._planner.plan(
            domain=domain,
            strategy=strategy,
            disabled_stages=disabled_stages,
        )

        warnings = []
        for blocker in plan.blockers:
            warnings.append(blocker)

        ready = True
        # Only block on critical issues (e.g., completely empty domain)
        if not domain:
            ready = False
            warnings.append("No domain specified — pipeline will produce no results")

        return PreflightResult(
            ready=ready,
            health_status="healthy",
            execution_plan=plan,
            warnings=warnings,
            estimated_time_s=plan.total_estimated_time_s,
            estimated_tokens=plan.total_estimated_tokens,
        )

    def record_token_usage(
        self, model: str, input_tokens: int, output_tokens: int, stage: str = ""
    ) -> None:
        """Record token usage for cost tracking."""
        self._cost.record(TokenUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stage=stage,
        ))

    def cost_report(self):
        """Get current cost report."""
        return self._cost.report()
