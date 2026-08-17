"""Tree-of-Thought adapter — bridges agent calls to GraphOfOperations.

Wraps the Ideator, Critic, and Refiner agents as sync callables
suitable for beam_search(). Uses event loop bridging to run async
agent calls from within the synchronous GraphOfOperations API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.gateway.transport import (
    GatewayTransportError,
)
from backend.pipeline.generation.reasoning_graph import (
    GraphOfOperations,
    ReasoningGraph,
    ThoughtNode,
)
from backend.pipeline.literature.models import Paper

if TYPE_CHECKING:
    from backend.pipeline.generation.critic_agent import CriticAgent
    from backend.pipeline.generation.ideator_agent import IdeatorAgent
    from backend.pipeline.generation.refiner_agent import RefinerAgent

logger = logging.getLogger(__name__)


class ToTAdapter:
    """Bridges agent calls to GraphOfOperations beam search callables."""

    def __init__(
        self,
        ideator: IdeatorAgent,
        critic: CriticAgent,
        refiner: RefinerAgent | None = None,
        score_threshold: float = 0.7,
    ):
        self._ideator = ideator
        self._critic = critic
        self._refiner = refiner
        self._score_threshold = score_threshold
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_event_loop()
        return self._loop

    def run_beam_search(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        max_depth: int = 3,
        beam_width: int = 2,
    ) -> list[ThoughtNode]:
        """Run full beam search, bridging async agents through the sync API.

        Creates root nodes from gaps, then runs beam_search with
        agent-backed generate/score/validate callables.
        """
        graph = ReasoningGraph()
        ops = GraphOfOperations(graph)

        # Create root nodes from gaps
        root_ids = []
        for gap in gaps:
            node = ThoughtNode(
                content=f"Gap: {gap.title}\n{gap.description}",
                metadata={"gap_title": gap.title, "gap_confidence": gap.confidence},
            )
            graph.add_node(node)
            root_ids.append(node.id)

        # Store context for callables
        self._gaps = gaps
        self._papers = context_papers

        results = ops.beam_search(
            root_ids=root_ids,
            generator=self._generate,
            scorer=self._score,
            validator=self._validate,
            max_depth=max_depth,
            n_branches=beam_width,
        )

        logger.info(
            "ToT beam search: %d roots, %d results (depth=%d, width=%d)",
            len(root_ids), len(results), max_depth, beam_width,
        )
        return results

    def _generate(self, parent_content: str, n_branches: int = 2) -> list[str]:
        """Generate N idea variants from a parent node's content."""
        try:
            loop = self._get_loop()
            ideas = loop.run_until_complete(
                self._ideator.generate_ideas(
                    gaps=self._gaps,
                    context_papers=self._papers,
                    prior_critique=[parent_content],
                    n_ideas=n_branches,
                )
            )
            return [f"{idea.title}: {idea.proposed_method[:300]}" for idea in ideas]
        except RuntimeError as e:
            if "Event loop" in str(e) and "running" in str(e):
                # Already in an async context — use nest_asyncio or fallback
                logger.warning("ToT generate: event loop already running, using sync fallback")
                return [f"Branch {i + 1} from: {parent_content[:100]}" for i in range(n_branches)]
            raise
        except GatewayTransportError:
            # Q2: transport/provider failure keeps its identity —
            # a dead endpoint reaches the stage executor's typed
            # handling, never becomes an empty ideation artifact.
            raise
        except Exception as e:
            logger.error("ToT generate failed: %s", e)
            return [f"Branch {i + 1} from: {parent_content[:100]}" for i in range(n_branches)]

    def _score(self, node_contents: list[str]) -> list[float]:
        """Score a batch of node contents using the critic."""
        try:
            loop = self._get_loop()
            from backend.pipeline.generation.models import ResearchIdea

            mock_ideas = [
                ResearchIdea(
                    title=content[:80],
                    problem_statement=content,
                    proposed_method=content,
                    expected_contributions=content[:100],
                    domain="AI/NLP",
                )
                for content in node_contents
            ]
            critiques = loop.run_until_complete(
                self._critic.critique_ideas(mock_ideas, self._papers)
            )
            return [c.score for c in critiques]
        except RuntimeError as e:
            if "Event loop" in str(e) and "running" in str(e):
                logger.warning("ToT score: event loop already running, using heuristic")
                return [0.5 + 0.1 * i for i in range(len(node_contents))]
            raise
        except GatewayTransportError:
            # Q2: transport/provider failure keeps its identity —
            # a dead endpoint reaches the stage executor's typed
            # handling, never becomes an empty ideation artifact.
            raise
        except Exception as e:
            logger.error("ToT score failed: %s", e)
            return [0.5] * len(node_contents)

    def _validate(self, content: str, score: float) -> bool:
        """Validate whether a node meets the quality threshold."""
        return score >= self._score_threshold
