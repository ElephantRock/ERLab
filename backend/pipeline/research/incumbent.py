"""Incumbent + Frontier search heuristic for research direction selection.

Instead of treating all gaps equally, identifies ONE strongest direction
(incumbent) and a small set of alternatives (frontier, 2-3 items).

Inspired by DeepScientist's research search heuristic:
"Don't optimize for generating many possibilities. Optimize for
 identifying the most defensible next route."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.gap_analysis.models import ResearchGap
    from backend.pipeline.knowledge.retriever import Paper

logger = logging.getLogger(__name__)


@dataclass
class ResearchDirection:
    """A research direction with incumbent/frontier classification."""

    gap: "ResearchGap"
    is_incumbent: bool
    frontier_rank: int | None  # 1, 2, 3 for frontier; None for incumbent
    evidence_strength: float  # confidence * paper_support_count
    rationale: str  # why this was selected


class IncumbentFrontierSelector:
    """Classify gaps into incumbent (strongest) and frontier (alternatives).

    Scoring formula:
        evidence_strength = confidence × (1 + log(paper_support_count))

    The top-scoring gap becomes the incumbent.
    The next 2-3 become frontier (ranked 1, 2, 3).
    The rest remain unclassified (treated as background evidence).
    """

    FRONTIER_SIZE = 3  # Number of frontier alternatives

    def select(
        self,
        gaps: list["ResearchGap"],
        papers: list | None = None,
    ) -> list[ResearchDirection]:
        """Classify gaps into incumbent/frontier.

        Args:
            gaps: Research gaps, ideally already sorted by confidence (descending).
            papers: Corpus papers for evidence counting (optional).

        Returns:
            List of ResearchDirection objects, one per gap.
        """
        if not gaps:
            return []

        # Score each gap by evidence strength
        scored = []
        for gap in gaps:
            confidence = getattr(gap, "confidence", 0.5)
            paper_count = self._count_supporting_papers(gap, papers)
            import math

            # log-scaled paper support: diminishing returns
            paper_factor = 1.0 + (math.log(max(1, paper_count)) if paper_count > 0 else 0.0)
            evidence_strength = confidence * paper_factor

            scored.append((evidence_strength, gap, confidence, paper_count))

        # Sort by evidence strength (descending)
        scored.sort(key=lambda x: x[0], reverse=True)

        directions: list[ResearchDirection] = []

        for idx, (strength, gap, confidence, paper_count) in enumerate(scored):
            if idx == 0:
                # Incumbent
                directions.append(ResearchDirection(
                    gap=gap,
                    is_incumbent=True,
                    frontier_rank=None,
                    evidence_strength=round(strength, 3),
                    rationale=self._incumbent_rationale(confidence, paper_count),
                ))
            elif idx <= self.FRONTIER_SIZE:
                # Frontier (ranked 1 to FRONTIER_SIZE)
                directions.append(ResearchDirection(
                    gap=gap,
                    is_incumbent=False,
                    frontier_rank=idx,  # 1, 2, 3
                    evidence_strength=round(strength, 3),
                    rationale=self._frontier_rationale(idx, confidence, paper_count),
                ))
            else:
                # Background
                directions.append(ResearchDirection(
                    gap=gap,
                    is_incumbent=False,
                    frontier_rank=None,
                    evidence_strength=round(strength, 3),
                    rationale="Supporting evidence for primary directions",
                ))

        return directions

    def _count_supporting_papers(self, gap: "ResearchGap", papers: list | None) -> int:
        """Count how many papers in the corpus support this gap."""
        if not papers:
            return 0

        # Use gap's supporting_papers field if available
        supporting = getattr(gap, "supporting_papers", None)
        if supporting is not None:
            return len(supporting) if hasattr(supporting, "__len__") else 0

        # Fall back to keyword matching against paper titles/abstracts
        gap_text = (getattr(gap, "title", "") + " " + getattr(gap, "description", "")).lower()
        if not gap_text.strip():
            return 0

        gap_words = set(w for w in gap_text.split() if len(w) > 3)
        if not gap_words:
            return 0

        count = 0
        for paper in papers[:100]:  # cap at 100 for performance
            paper_text = (
                getattr(paper, "title", "") + " " + getattr(paper, "abstract", "") or ""
            ).lower()
            paper_words = set(w for w in paper_text.split() if len(w) > 3)
            overlap = len(gap_words & paper_words)
            if overlap >= 2:  # at least 2 significant word overlap
                count += 1

        return count

    @staticmethod
    def _incumbent_rationale(confidence: float, paper_count: int) -> str:
        return (
            f"Highest evidence strength (confidence={confidence:.2f}, "
            f"paper_support={paper_count}). Primary research direction."
        )

    @staticmethod
    def _frontier_rationale(rank: int, confidence: float, paper_count: int) -> str:
        return (
            f"Frontier alternative #{rank} (confidence={confidence:.2f}, "
            f"paper_support={paper_count}). Explores a different angle."
        )
