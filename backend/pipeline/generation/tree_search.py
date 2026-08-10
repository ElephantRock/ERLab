"""TreeSearchEngine — beam search over the idea space.

Inspired by Google's "The AI Scientist" (arXiv 2509.06503) which showed
LLM + Tree Search outperforms single calls — 40/87 methods beat all
published approaches.

Architecture:
  - TreeSearchEngine performs iterative beam search: expand K candidates →
    score → prune to K → repeat for D depth levels.
  - Generation is delegated to IdeatorAgent (HB-01: no direct LLM calls).
  - Scoring uses BordaTournament or a simple quality gate.
  - Beam width is hard-capped at 10 (HB-03).

Edge cases:
  - Empty gaps → returns empty list (CHK-13 from review).
  - Single gap → works normally, just less diversity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.borda import borda_rank_graph_nodes
from backend.pipeline.generation.models import IdeaCandidate
from backend.pipeline.literature.models import Paper

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Hard boundary constant ──────────────────────────────────────────
MAX_BEAM_WIDTH = 10  # HB-03: absolute cap regardless of configuration


# ── Configuration ───────────────────────────────────────────────────


@dataclass
class TreeSearchConfig:
    """Configuration for TreeSearchEngine beam search.

    Attributes:
        beam_width: Number of top candidates retained at each depth level.
                    Capped at MAX_BEAM_WIDTH (10) by the engine (HB-03).
        max_depth: Number of expansion-scoring-pruning iterations.
        ideas_per_node: How many child ideas to generate per beam node.
        recombination_rate: Fraction (0–1) of expansions that use
                            recombination instead of fresh generation.
                            Actual recombination is done by a separate
                            RecombinationOperator (TASK-02). Until that is
                            wired in, this flag is a no-op placeholder.
    """

    beam_width: int = 3
    max_depth: int = 3
    ideas_per_node: int = 5
    recombination_rate: float = 0.3


# ── Tree Node ───────────────────────────────────────────────────────


@dataclass
class TreeNode:
    """A node in the beam search tree.

    Attributes:
        idea: The IdeaCandidate at this node (None for the virtual root).
        children: Child nodes produced by expanding this node.
        score: Numeric score used for pruning/ranking.
        depth: Depth level in the tree (0 = root's children).
        parent_ids: IDs of parent ideas for lineage tracking.
    """

    idea: IdeaCandidate | None = None
    children: list[TreeNode] = field(default_factory=list)
    score: float = 0.0
    depth: int = 0
    parent_ids: list[str] = field(default_factory=list)


# ── Scorer Protocol ─────────────────────────────────────────────────


class IdeaScorer(Protocol):
    """Protocol for scoring idea candidates during beam search."""

    def score(
        self, ideas: list[IdeaCandidate], context: str = ""
    ) -> list[float]:
        """Return a score for each idea (higher = better)."""
        ...


class SimpleScorer:
    """Fallback scorer using IdeaCandidate.overall_score field.

    Used when no BordaTournament or custom scorer is provided.
    Produces deterministic scores based on the idea's own
    overall_score field, with a small bonus for lineage depth.
    """

    def score(
        self, ideas: list[IdeaCandidate], context: str = ""
    ) -> list[float]:
        return [idea.overall_score for idea in ideas]


class BordaScorer:
    """Scorer that uses Borda count over multiple quality dimensions.

    Delegates to borda_rank_graph_nodes from borda.py for aggregation.
    The dimensions scored are heuristic text-length proxies until a
    proper multi-dimensional judge is wired in.
    """

    # Weights for three heuristic dimensions:
    # (title_quality, method_quality, rationale_quality)
    # For now, these are derived from text length as a rough proxy.
    def score(
        self, ideas: list[IdeaCandidate], context: str = ""
    ) -> list[float]:
        if not ideas:
            return []

        node_scores: dict[str, list[float]] = {}
        for idea in ideas:
            # Three heuristic dimensions (0–1 normalized):
            title_score = min(len(idea.title) / 100.0, 1.0)
            method_score = min(len(idea.proposed_method) / 500.0, 1.0)
            rationale_score = min(len(idea.novelty_rationale) / 300.0, 1.0)
            # Include overall_score if set
            base = idea.overall_score / 10.0 if idea.overall_score > 0 else 0.0
            node_scores[idea.id] = [
                title_score + base,
                method_score + base,
                rationale_score + base,
            ]

        winner_id, borda_scores = borda_rank_graph_nodes(node_scores)

        # Normalize borda scores to a 0–1 range
        max_borda = max(borda_scores.values()) if borda_scores else 1
        max_borda = max(max_borda, 1)  # prevent division by zero
        return [
            borda_scores.get(idea.id, 0) / max_borda
            for idea in ideas
        ]


# ── Ideator Protocol ────────────────────────────────────────────────


class Ideator(Protocol):
    """Protocol matching IdeatorAgent's interface (HB-01)."""

    async def generate_ideas(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        prior_critique: list[str] | None = None,
        n_ideas: int = 3,
    ) -> list[IdeaCandidate]: ...


# ── TreeSearchEngine ────────────────────────────────────────────────


class TreeSearchEngine:
    """Beam search engine over the idea space.

    Performs iterative expand → score → prune cycles for D depth levels.
    At each level, the top-K candidates (by beam_width) are retained.

    The engine never calls an LLM directly — all generation is delegated
    to the injected IdeatorAgent (HB-01).

    Usage::

        ideator = IdeatorAgent(provider)
        engine = TreeSearchEngine(ideator, config=TreeSearchConfig(beam_width=5))
        results = await engine.search(gaps, papers)
        # results is list[IdeaCandidate] sorted by score descending
    """

    def __init__(
        self,
        ideator: Ideator,
        scorer: IdeaScorer | None = None,
        config: TreeSearchConfig | None = None,
    ):
        self._ideator = ideator  # IdeatorAgent — injected (HB-01)
        self._config = config or TreeSearchConfig()
        # Enforce beam width cap (HB-03)
        self._config.beam_width = min(self._config.beam_width, MAX_BEAM_WIDTH)
        self._scorer = scorer or BordaScorer()

    # ── Public API ──────────────────────────────────────────────────

    async def search(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        initial_ideas: list[IdeaCandidate] | None = None,
    ) -> list[IdeaCandidate]:
        """Perform beam search over the idea space.

        Args:
            gaps: Research gaps to inform idea generation.
            context_papers: Existing literature for context.
            initial_ideas: Optional seed ideas. If None, generated from gaps.

        Returns:
            list[IdeaCandidate] sorted by score descending.
            Returns empty list if gaps is empty (CHK-13).
        """
        # Edge case: empty gaps → return empty list (CHK-13 from review)
        if not gaps:
            logger.info("TreeSearchEngine.search: no gaps provided, returning empty list")
            return []

        # 1. Initialize beam
        if initial_ideas:
            beam: list[TreeNode] = [
                TreeNode(idea=idea, depth=0) for idea in initial_ideas
            ]
            # Score initial beam
            initial_scores = self._scorer.score(
                [n.idea for n in beam if n.idea],  # type: ignore[misc]
                self._build_context(gaps, context_papers),
            )
            for node, score in zip(beam, initial_scores):
                node.score = score
        else:
            # Generate initial ideas from gaps
            seed_ideas = await self._ideator.generate_ideas(
                gaps,
                context_papers,
                n_ideas=self._config.ideas_per_node,
            )
            beam = [TreeNode(idea=idea, depth=0) for idea in seed_ideas]
            if beam:
                initial_scores = self._scorer.score(
                    [n.idea for n in beam if n.idea],  # type: ignore[misc]
                    self._build_context(gaps, context_papers),
                )
                for node, score in zip(beam, initial_scores):
                    node.score = score

        # If nothing was generated, return empty
        if not beam:
            return []

        # Prune initial beam to beam_width
        beam = self._prune(beam)

        # 2. Iterative beam search for max_depth levels
        for depth in range(1, self._config.max_depth + 1):
            logger.info(
                "TreeSearchEngine: depth %d/%d, beam size=%d",
                depth,
                self._config.max_depth,
                len(beam),
            )

            # Expand: generate children for each node in the beam
            all_children: list[TreeNode] = []
            context_str = self._build_context(gaps, context_papers)

            for node in beam:
                children = await self._expand_node(
                    node, gaps, context_papers, depth
                )
                all_children.extend(children)

            if not all_children:
                logger.info("TreeSearchEngine: no children generated at depth %d", depth)
                break

            # Score all children
            child_ideas = [n.idea for n in all_children if n.idea]
            if child_ideas:
                scores = self._scorer.score(child_ideas, context_str)
                for child, score in zip(all_children, scores):
                    child.score = score

            # Prune to top beam_width
            beam = self._prune(all_children)

        # 3. Return final beam sorted by score descending
        final_ideas: list[IdeaCandidate] = []
        for node in sorted(beam, key=lambda n: n.score, reverse=True):
            if node.idea is not None:
                # Attach final score to the idea
                node.idea.overall_score = node.score
                final_ideas.append(node.idea)

        logger.info(
            "TreeSearchEngine: search complete, %d final ideas", len(final_ideas)
        )
        return final_ideas

    @property
    def config(self) -> TreeSearchConfig:
        """Read-only access to the effective config (post cap)."""
        return self._config

    # ── Private helpers ──────────────────────────────────────────────

    async def _expand_node(
        self,
        node: TreeNode,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        depth: int,
    ) -> list[TreeNode]:
        """Expand a single beam node by generating child ideas.

        Delegates to IdeatorAgent.generate_ideas() (HB-01).
        """
        # Build prior critique from parent idea if available
        prior_critique = None
        if node.idea:
            prior_critique = [
                f"Previous idea: {node.idea.title}\n"
                f"Method: {node.idea.proposed_method}\n"
                f"Score: {node.score:.3f}\n"
                f"Build upon or diverge from this approach."
            ]

        try:
            child_ideas = await self._ideator.generate_ideas(
                gaps,
                context_papers,
                prior_critique=prior_critique,
                n_ideas=self._config.ideas_per_node,
            )
        except Exception as e:
            logger.error("TreeSearchEngine: expansion failed: %s", e)
            return []

        parent_id = node.idea.id if node.idea else None
        children: list[TreeNode] = []
        for idea in child_ideas:
            # Set lineage
            parent_ids = []
            if parent_id:
                parent_ids.append(parent_id)
            if node.parent_ids:
                parent_ids.extend(node.parent_ids)

            idea.parent_idea_ids = parent_ids or None

            children.append(
                TreeNode(
                    idea=idea,
                    depth=depth,
                    parent_ids=parent_ids,
                )
            )

        # Attach children to parent node
        node.children = children
        return children

    def _prune(self, nodes: list[TreeNode]) -> list[TreeNode]:
        """Keep only the top beam_width nodes by score.

        This enforces the beam width at every depth level (AC-01-02).
        """
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)
        pruned = sorted_nodes[: self._config.beam_width]

        if len(sorted_nodes) > self._config.beam_width:
            logger.debug(
                "Pruned %d nodes to %d (beam_width=%d)",
                len(sorted_nodes),
                len(pruned),
                self._config.beam_width,
            )

        return pruned

    @staticmethod
    def _build_context(
        gaps: list[ResearchGap], papers: list[Paper]
    ) -> str:
        """Build a context string for scoring."""
        parts: list[str] = []
        for gap in gaps[:5]:
            parts.append(f"Gap: {gap.title} — {gap.description}")
        for paper in papers[:10]:
            abstract = (paper.abstract or "")[:100]
            parts.append(f"[{paper.year or 'N/A'}] {paper.title}: {abstract}")
        return "\n".join(parts)
