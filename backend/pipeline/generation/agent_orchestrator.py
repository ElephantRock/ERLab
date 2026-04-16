"""Multi-agent orchestrator for idea generation.

Runs the Ideator → Critic → Refiner loop with metacognitive strategy
selection, convergence detection, loop detection, and quality gating.
"""

import logging

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.critic_agent import CriticAgent
from backend.pipeline.generation.ideator_agent import IdeatorAgent
from backend.pipeline.generation.models import Critique, ResearchIdea
from backend.pipeline.generation.refiner_agent import RefinerAgent
from backend.pipeline.generation.strategies import (
    CriticStrategy,
    check_convergence,
    detect_loop,
    keep_best_n,
    select_strategy,
)
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Runs the Ideator → Critic → Refiner loop for N rounds."""

    def __init__(self, provider: LLMProvider):
        self._provider = provider
        self._ideator = IdeatorAgent(provider)
        self._critic = CriticAgent(provider)
        self._refiner = RefinerAgent(provider)

    async def run(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        rounds: int = 2,
        ideas_per_round: int = 3,
    ) -> list[ResearchIdea]:
        """Run multi-agent ideation loop.

        For each round:
          1. Ideator generates raw ideas
          2. Critic evaluates each idea (with metacognitive strategy selection)
          3. Refiner produces strengthened versions
        Includes convergence detection, loop detection, and quality gating.
        Returns final list of ResearchIdea objects sorted by score.
        """
        all_ideas: list[ResearchIdea] = []
        prior_critiques: list[str] = []
        critique_history: list[list[Critique]] = []
        previous_ideas: list[ResearchIdea] = []
        last_converged = False

        for round_num in range(1, rounds + 1):
            logger.info("=== Generation Round %d/%d ===", round_num, rounds)

            # Step 1: Ideate
            strategy = select_strategy(round_num, rounds, last_converged)
            logger.info(
                "Generating %d ideas (strategy: %s)...",
                ideas_per_round,
                strategy.value,
            )

            raw_ideas = await self._ideator.generate_ideas(
                gaps=gaps,
                context_papers=context_papers,
                prior_critique=prior_critiques if prior_critiques else None,
                n_ideas=ideas_per_round,
            )

            if not raw_ideas:
                logger.warning("IdeatorAgent produced no ideas in round %d", round_num)
                continue

            logger.info("Generated %d raw ideas", len(raw_ideas))

            # Step 2: Critique with strategy-aware evaluation
            logger.info("Critiquing ideas (strategy: %s)...", strategy.value)
            critiques = await self._critic.critique_ideas(
                ideas=raw_ideas,
                context_papers=context_papers,
                strategy=strategy,
            )
            logger.info("Produced %d critiques", len(critiques))

            # Loop detection
            if detect_loop(critiques, critique_history):
                logger.warning(
                    "Loop detected: critiques similar to a prior round. "
                    "Switching to META_REFLECTION strategy."
                )
                strategy = CriticStrategy.META_REFLECTION
                critiques = await self._critic.critique_ideas(
                    ideas=raw_ideas,
                    context_papers=context_papers,
                    strategy=strategy,
                )

            critique_history.append(critiques)

            # Collect critique summaries for next round
            prior_critiques = [
                f"{c.idea_title}: {'; '.join(c.weaknesses[:3])} → {'; '.join(c.suggestions[:3])}"
                for c in critiques
            ]

            # Step 3: Refine
            logger.info("Refining ideas based on critiques...")
            refined = await self._refiner.refine_ideas(
                ideas=raw_ideas,
                critiques=critiques,
                context_papers=context_papers,
                round_num=round_num,
            )

            logger.info("Refined to %d ideas", len(refined))

            # Convergence detection
            if previous_ideas:
                convergence = check_convergence(refined, previous_ideas, critiques)
                if convergence.converged:
                    logger.info(
                        "Convergence detected at round %d: %s",
                        round_num,
                        convergence.reason,
                    )
                    all_ideas.extend(refined)
                    break
                last_converged = convergence.converged

            previous_ideas = refined
            all_ideas.extend(refined)

        # Quality gate: keep only the best ideas
        max_ideas = rounds * ideas_per_round
        all_ideas = keep_best_n(all_ideas, max_ideas, min_score=0.3)

        # Sort by score and return
        return sorted(all_ideas, key=lambda i: i.score, reverse=True)
