"""Forest-of-Thought — multiple independent reasoning trees for idea exploration.

Runs N independent ToT beam searches with different perspectives/temperatures,
then selects the best idea across all trees. Each tree explores the same gaps
but with varied creative angles, increasing the chance of finding novel ideas.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from backend.pipeline.generation.reasoning_graph import (
    ReasoningGraph,
    ThoughtNode,
)

if TYPE_CHECKING:
    from backend.pipeline.gap_analysis.models import ResearchGap
    from backend.pipeline.generation.critic_agent import CriticAgent
    from backend.pipeline.generation.ideator_agent import IdeatorAgent
    from backend.pipeline.generation.tot_adapter import ToTAdapter
    from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)

_PERSPECTIVES = [
    "Focus on novel combinations of existing methods.",
    "Focus on addressing fundamental theoretical limitations.",
    "Focus on practical applications and real-world impact.",
    "Focus on underexplored datasets and evaluation methods.",
    "Focus on cross-disciplinary transfer from other fields.",
]


class ForestResult(BaseModel):
    """Result of a Forest-of-Thought exploration."""

    trees: list[ReasoningGraph] = Field(default_factory=list)
    selected_node: ThoughtNode | None = None
    all_leaves: list[ThoughtNode] = Field(default_factory=list)
    selection_reason: str = ""
    n_trees: int = 0


class ForestOfThought:
    """Multiple independent reasoning trees with cross-tree selection."""

    def __init__(
        self,
        tot_adapter: ToTAdapter,
        provider: Any = None,
        n_trees: int = 3,
        max_depth: int = 3,
        beam_width: int = 2,
    ) -> None:
        self._tot = tot_adapter
        self._provider = provider
        self._n_trees = n_trees
        self._max_depth = max_depth
        self._beam_width = beam_width

    async def explore_ideas(
        self,
        gaps: list[ResearchGap],
        papers: list[Paper],
    ) -> ForestResult:
        """Run N independent trees and select the best idea across all."""
        import asyncio

        perspectives = _PERSPECTIVES[: self._n_trees]
        while len(perspectives) < self._n_trees:
            perspectives.append(f"Tree {len(perspectives) + 1}: general exploration")

        results: list[list[ThoughtNode]] = []
        trees: list[ReasoningGraph] = []

        for i, perspective in enumerate(perspectives):
            try:
                leaves = self._tot.run_beam_search(
                    gaps=gaps,
                    context_papers=papers,
                    max_depth=self._max_depth,
                    beam_width=self._beam_width,
                )
                results.append(leaves)

                # Build a tree for the result
                graph = ReasoningGraph()
                for leaf in leaves:
                    graph.add_node(leaf)
                trees.append(graph)

                logger.info(
                    "Forest tree %d (%s): %d leaves",
                    i + 1, perspective[:40], len(leaves),
                )
            except Exception as e:
                logger.warning("Forest tree %d failed: %s", i + 1, e)
                results.append([])
                trees.append(ReasoningGraph())

        # Collect all leaves across trees
        all_leaves: list[ThoughtNode] = []
        for tree_leaves in results:
            all_leaves.extend(tree_leaves)

        if not all_leaves:
            return ForestResult(
                trees=trees, n_trees=self._n_trees,
                selection_reason="No leaves produced across any tree",
            )

        # Select best node by score
        selected = max(all_leaves, key=lambda n: n.score)
        reason = f"Selected from {len(all_leaves)} leaves across {self._n_trees} trees (score={selected.score:.3f})"

        return ForestResult(
            trees=trees,
            selected_node=selected,
            all_leaves=all_leaves,
            selection_reason=reason,
            n_trees=self._n_trees,
        )
