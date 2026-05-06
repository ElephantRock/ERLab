"""Pipeline run comparison: compare two runs side-by-side.

Compares papers found, gaps identified, ideas generated,
scores, duration, and strategies.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RunComparison:
    """Side-by-side comparison of two pipeline runs."""
    run_a_id: str
    run_b_id: str
    papers_a: int = 0
    papers_b: int = 0
    gaps_a: int = 0
    gaps_b: int = 0
    ideas_a: int = 0
    ideas_b: int = 0
    duration_a: float = 0.0
    duration_b: float = 0.0
    strategy_a: str = ""
    strategy_b: str = ""
    domain_a: str = ""
    domain_b: str = ""

    @property
    def paper_delta(self) -> int:
        return self.papers_b - self.papers_a

    @property
    def gap_delta(self) -> int:
        return self.gaps_b - self.gaps_a

    @property
    def idea_delta(self) -> int:
        return self.ideas_b - self.ideas_a

    @property
    def duration_delta(self) -> float:
        return self.duration_b - self.duration_a

    def summary(self) -> dict:
        """Return a summary dictionary."""
        return {
            "run_a": self.run_a_id,
            "run_b": self.run_b_id,
            "papers": {"a": self.papers_a, "b": self.papers_b, "delta": self.paper_delta},
            "gaps": {"a": self.gaps_a, "b": self.gaps_b, "delta": self.gap_delta},
            "ideas": {"a": self.ideas_a, "b": self.ideas_b, "delta": self.idea_delta},
            "duration_s": {"a": self.duration_a, "b": self.duration_b, "delta": self.duration_delta},
            "strategy": {"a": self.strategy_a, "b": self.strategy_b},
        }


class RunComparator:
    """Compares two pipeline runs."""

    def compare(self, run_a: dict, run_b: dict) -> RunComparison:
        """Compare two run dictionaries.

        Args:
            run_a: First run data (dict with id, paper_count, gap_count, etc.)
            run_b: Second run data.

        Returns:
            RunComparison with side-by-side metrics.
        """
        return RunComparison(
            run_a_id=str(run_a.get("id", "unknown")),
            run_b_id=str(run_b.get("id", "unknown")),
            papers_a=run_a.get("paper_count", 0) or 0,
            papers_b=run_b.get("paper_count", 0) or 0,
            gaps_a=run_a.get("gap_count", 0) or 0,
            gaps_b=run_b.get("gap_count", 0) or 0,
            ideas_a=run_a.get("idea_count", 0) or 0,
            ideas_b=run_b.get("idea_count", 0) or 0,
            duration_a=run_a.get("duration_seconds", 0) or 0,
            duration_b=run_b.get("duration_seconds", 0) or 0,
            strategy_a=run_a.get("strategy", "") or "",
            strategy_b=run_b.get("strategy", "") or "",
            domain_a=run_a.get("domain", "") or "",
            domain_b=run_b.get("domain", "") or "",
        )
