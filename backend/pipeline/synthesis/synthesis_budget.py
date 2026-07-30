"""Phase 7 / 7C — evidence-based synthesis budgets.

Replaces the single undifferentiated 600-second PER_PROPOSAL_TIMEOUT with
bounded, monotonic budgets. The budget is a monotonic workflow deadline:
all timeouts are computed relative to a single start time.

Evidence from Phase 5–6 timing:
  - Phase 5 monolithic paper synthesis: timed out at 600s (B-08)
  - Phase 6 monolithic recovery: completed in ~1800s with no wrapper
  - Phase 5 section-wise: completed 5/7 sections in ~600s
  - Each section call: ~30-90s (1-3 provider round-trips)

The defaults below are selected to:
  - Allow monolithic synthesis adequate time (~400s, matching Phase 6's
    successful completion under similar conditions)
  - Reserve enough fallback time for section-wise completion (~800s)
  - Bound each section call to prevent a single slow call from consuming
    the entire budget
  - Keep the total within the 1800s stage budget
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class SynthesisBudget:
    """Monotonic synthesis budget with explicit allocations.

    All times are in seconds. The invariant:

        monolithic_attempt_timeout ≤ total_workflow_timeout − fallback_reserved_seconds

    Per-section calls receive:

        min(section_call_timeout, remaining_workflow_time)
    """

    total_workflow_timeout: float = 1200.0
    monolithic_attempt_timeout: float = 400.0
    fallback_reserved_seconds: float = 800.0
    section_call_timeout: float = 120.0

    def __post_init__(self):
        """Validate the budget invariant."""
        if self.monolithic_attempt_timeout > self.total_workflow_timeout - self.fallback_reserved_seconds:
            raise ValueError(
                f"Budget invariant violated: monolithic_attempt_timeout "
                f"({self.monolithic_attempt_timeout}) > total ({self.total_workflow_timeout}) "
                f"− fallback reserve ({self.fallback_reserved_seconds})"
            )

    @property
    def fallback_deadline(self) -> float:
        """Absolute deadline for the section-wise fallback path."""
        return self.total_workflow_timeout

    def monolithic_remaining(self, elapsed: float) -> float:
        """Remaining time for the monolithic attempt."""
        return max(0.0, self.monolithic_attempt_timeout - elapsed)

    def fallback_remaining(self, elapsed: float) -> float:
        """Remaining time for the section-wise fallback."""
        return max(0.0, self.fallback_deadline - elapsed)

    def section_remaining(self, elapsed: float) -> float:
        """Time budget for a single section call."""
        return min(self.section_call_timeout, self.fallback_remaining(elapsed))

    def should_try_fallback(self, elapsed: float) -> bool:
        """Whether enough time remains for a section-wise fallback attempt."""
        return self.fallback_remaining(elapsed) >= 120.0  # at least one section call


class BudgetTimer:
    """Tracks elapsed time against a SynthesisBudget."""

    def __init__(self, budget: SynthesisBudget):
        self._budget = budget
        self._start = time.monotonic()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start

    @property
    def monolithic_remaining(self) -> float:
        return self._budget.monolithic_remaining(self.elapsed)

    @property
    def fallback_remaining(self) -> float:
        return self._budget.fallback_remaining(self.elapsed)

    @property
    def section_remaining(self) -> float:
        return self._budget.section_remaining(self.elapsed)

    @property
    def should_try_fallback(self) -> bool:
        return self._budget.should_try_fallback(self.elapsed)
