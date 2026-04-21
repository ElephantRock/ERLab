"""Context isolation for parallel agent execution.

Provides deep-copy isolation so parallel agent invocations cannot
mutate each other's data. Each agent gets its own copy of gaps and
papers, preventing cross-contamination during concurrent execution.
"""

from __future__ import annotations

import copy

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.literature.models import Paper


class ContextIsolator:
    """Provides isolated context copies for parallel agent invocations."""

    def __init__(self, gaps: list[ResearchGap], papers: list[Paper]) -> None:
        self._gaps = gaps
        self._papers = papers

    def isolated_context(self) -> tuple[list[ResearchGap], list[Paper]]:
        """Return deep copies of all gaps and papers."""
        return copy.deepcopy(self._gaps), copy.deepcopy(self._papers)

    def isolated_context_for_gap(
        self, gap: ResearchGap
    ) -> tuple[list[ResearchGap], list[Paper]]:
        """Return deep-copied single-gap + papers context."""
        return [copy.deepcopy(gap)], copy.deepcopy(self._papers)
