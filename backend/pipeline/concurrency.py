"""Concurrency safety for pipeline stage execution.

Each stage declares whether it's safe to run concurrently with
other stages. The ConcurrencyManager resolves a parallel execution
plan that respects all safety flags.

Default is non-concurrent (safe) — HB-01.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConcurrencySafety(str, Enum):
    """How safe a stage is for concurrent execution."""
    EXCLUSIVE = "exclusive"      # Must run alone (e.g. LLM calls, DB writes)
    SAFE_TO_PARALLEL = "safe"    # Can run with any other stage
    READ_ONLY = "read_only"      # Only reads, safe with other reads


@dataclass
class StageConcurrency:
    """Concurrency declaration for a pipeline stage."""
    stage_name: str
    safety: ConcurrencySafety = ConcurrencySafety.EXCLUSIVE  # HB-01: default safe
    max_parallel: int = 1       # Max concurrent instances of this stage
    resource_group: str = ""    # Stages in same group can't run together

    @property
    def is_exclusive(self) -> bool:
        return self.safety == ConcurrencySafety.EXCLUSIVE


class ConcurrencyManager:
    """Resolves parallel execution plans respecting safety flags.

    Groups stages by resource_group and safety to determine
    which stages can safely run concurrently.
    """

    def __init__(self) -> None:
        self._stages: dict[str, StageConcurrency] = {}

    def register(self, stage: StageConcurrency) -> None:
        """Register a stage's concurrency declaration."""
        self._stages[stage.stage_name] = stage

    def can_run_concurrent(self, stage_a: str, stage_b: str) -> bool:
        """Check if two stages can safely run concurrently."""
        a = self._stages.get(stage_a)
        b = self._stages.get(stage_b)

        # Unknown stages are treated as exclusive (HB-01)
        if not a or not b:
            return False

        # Same stage can't run with itself unless max_parallel > 1
        if stage_a == stage_b:
            return a.max_parallel > 1

        # Both must be safe for concurrent execution
        if a.is_exclusive or b.is_exclusive:
            return False

        # Same resource group can't run together
        if a.resource_group and a.resource_group == b.resource_group:
            return False

        return True

    def resolve_groups(self, stages: list[str]) -> list[list[str]]:
        """Group stages into parallel execution waves.

        Returns a list of waves, where each wave is a list of stages
        that can run concurrently. Waves run sequentially.
        """
        if not stages:
            return []

        waves: list[list[str]] = []
        remaining = list(stages)

        while remaining:
            current_wave: list[str] = []
            next_remaining: list[str] = []

            for stage in remaining:
                can_add = True
                for existing in current_wave:
                    if not self.can_run_concurrent(stage, existing):
                        can_add = False
                        break

                if can_add:
                    current_wave.append(stage)
                else:
                    next_remaining.append(stage)

            if current_wave:
                waves.append(current_wave)
            remaining = next_remaining

            # Safety: prevent infinite loop
            if not current_wave and remaining:
                # Each remaining stage goes in its own wave
                for stage in remaining:
                    waves.append([stage])
                break

        return waves

    def get_stage(self, name: str) -> StageConcurrency | None:
        return self._stages.get(name)


# Default concurrency declarations for Elephant Rock pipeline stages
DEFAULT_STAGE_CONCURRENCY = {
    "literature_search": StageConcurrency("literature_search", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="network"),
    "ingestion": StageConcurrency("ingestion", ConcurrencySafety.SAFE_TO_PARALLEL, resource_group="network"),
    "gap_analysis": StageConcurrency("gap_analysis", ConcurrencySafety.EXCLUSIVE, resource_group="llm"),
    "idea_generation": StageConcurrency("idea_generation", ConcurrencySafety.EXCLUSIVE, resource_group="llm"),
    "novelty_checking": StageConcurrency("novelty_checking", ConcurrencySafety.EXCLUSIVE, resource_group="llm"),
    "feasibility_scoring": StageConcurrency("feasibility_scoring", ConcurrencySafety.EXCLUSIVE, resource_group="llm"),
    "mechanical_metrics": StageConcurrency("mechanical_metrics", ConcurrencySafety.SAFE_TO_PARALLEL),
    "proposal_synthesis": StageConcurrency("proposal_synthesis", ConcurrencySafety.EXCLUSIVE, resource_group="llm"),
    "export": StageConcurrency("export", ConcurrencySafety.SAFE_TO_PARALLEL),
}
