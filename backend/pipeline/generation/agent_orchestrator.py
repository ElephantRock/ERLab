"""Multi-agent orchestrator for idea generation.

Runs the Ideator → Critic → Refiner loop with metacognitive strategy
selection, convergence detection, loop detection, and quality gating.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.generation.borda import (
    BordaTournament,
)
from backend.pipeline.tracing.spans import SpanKind, create_span
from backend.pipeline.generation.critic_agent import CriticAgent
from backend.pipeline.generation.ideator_agent import IdeatorAgent
from backend.pipeline.generation.impasse import ImpasseDetector, Resolution
from backend.pipeline.generation.models import Critique, ResearchIdea
from backend.pipeline.generation.refiner_agent import RefinerAgent
from backend.pipeline.generation.strategies import (
    CriticStrategy,
    StrategyOutcome,
    StrategyTracker,
    check_convergence,
    check_plateau,
    detect_loop,
    keep_best_n,
    select_strategy,
)
from backend.pipeline.literature.models import Paper
from backend.providers.base import LLMProvider

if TYPE_CHECKING:
    from backend.pipeline.knowledge.retriever import TwoStageRetriever
    from backend.pipeline.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Runs the Ideator → Critic → Refiner loop for N rounds."""

    def __init__(
        self,
        provider: LLMProvider,
        retriever: TwoStageRetriever | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self._provider = provider
        self._retriever = retriever
        self._tool_registry = tool_registry
        self._ideator = IdeatorAgent(provider, retriever=retriever)
        self._critic = CriticAgent(provider)
        self._refiner = RefinerAgent(provider)
        self._impasse_detector = ImpasseDetector()
        self._strategy_tracker = StrategyTracker()
        self._pending_resolution: Resolution | None = None
        self.last_critique_history: dict[int, list] = {}
        self.last_refinement_history: dict[int, list[dict]] = {}
        self._hooks = None
        self._metacog = None

        # In-loop context compression
        from backend.pipeline.compaction.agent_context import WorkingContext
        self._working_context = WorkingContext(provider)

        # Evolved temperature overrides (set by orchestrator from PipelineEvolver)
        self._temperature_overrides: dict[str, float] = {}

    def set_temperature_overrides(self, temps: dict[str, float]) -> None:
        """Set per-agent temperature overrides from evolved parameters."""
        self._temperature_overrides = temps

    def set_hooks(self, hooks: "HookDispatcher") -> None:
        """Set hook dispatcher for impasse events."""
        self._hooks = hooks

    async def generate_ideas(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        num_ideas: int = 3,
        n_ideas: int | None = None,
        prior_critiques: list[str] | None = None,
        prior_critique: str | None = None,
    ) -> list[ResearchIdea]:
        """Generate ideas by delegating to the IdeatorAgent.

        Supports multiple parameter names for compatibility with
        TreeSearchEngine (n_ideas, prior_critique) and other callers.
        """
        count = n_ideas if n_ideas is not None else num_ideas
        critiques = prior_critiques or []
        if prior_critique:
            critiques.append(prior_critique)
        return await self._ideator.generate_ideas(
            gaps=gaps,
            context_papers=context_papers,
            n_ideas=count,
            prior_critique=critiques if critiques else None,
        )

    async def run(
        self,
        gaps: list[ResearchGap],
        context_papers: list[Paper],
        rounds: int = 2,
        ideas_per_round: int = 3,
        use_borda: bool = False,
        *,
        provider: LLMProvider | None = None,
        receipts: list | None = None,
    ) -> list[ResearchIdea]:
        """Run multi-agent ideation loop.

        For each round:
          1. Ideator generates raw ideas
          2. Critic evaluates each idea (with metacognitive strategy selection)
          3. Refiner produces strengthened versions
        Includes convergence detection, loop detection, and quality gating.
        Set use_borda=True to use Borda tournament convergence (autoreason pattern).
        Returns final list of ResearchIdea objects sorted by score.
        """
        all_ideas: list[ResearchIdea] = []
        prior_critiques: list[str] = []
        critique_history: list[list[Critique]] = []
        previous_ideas: list[ResearchIdea] = []
        last_converged = False
        tournament = BordaTournament() if use_borda else None
        gap_ids = [g.title for g in gaps]

        # When a provider override is given, create scoped sub-agents so the
        # original sub-agents' providers are never mutated.  When no override,
        # use the default sub-agents.
        if provider is not None:
            ideator = IdeatorAgent(provider, retriever=self._retriever)
            critic = CriticAgent(provider)
            refiner = RefinerAgent(provider)
            # Collect receipt for the provider used in this run
            if receipts is not None:
                from backend.pipeline.operations.provider_conformance import build_receipt_from_provider
                receipts.append(build_receipt_from_provider(provider))
        else:
            ideator = self._ideator
            critic = self._critic
            refiner = self._refiner
            # Collect receipt for the default provider
            if receipts is not None:
                from backend.pipeline.operations.provider_conformance import build_receipt_from_provider
                receipts.append(build_receipt_from_provider(self._provider))

        # Accumulators for traceability
        self.last_critique_history = {}
        self.last_refinement_history = {}

        for round_num in range(1, rounds + 1):
            logger.info("=== Generation Round %d/%d ===", round_num, rounds)

            # Step 1: Ideate — use StrategyTracker if enough history, else rule-based
            if self._strategy_tracker.record_count >= 5:
                strategy = self._strategy_tracker.recommend(round_num, rounds)
            else:
                strategy = select_strategy(round_num, rounds, last_converged)

            # Apply pending impasse resolution from previous round
            if self._pending_resolution:
                res = self._pending_resolution
                if res.action == "inject_constraint":
                    prior_critiques.append(f"CONSTRAINT: {res.params.get('constraint', '')}")
                elif res.action == "switch_strategy":
                    strategy = CriticStrategy.META_REFLECTION
                elif res.action == "change_perspective":
                    prior_critiques.append(f"PERSPECTIVE: {res.params.get('perspective', '')}")
                logger.info("Applied impasse resolution: %s", res.action)
                self._pending_resolution = None

            logger.info(
                "Generating %d ideas (strategy: %s)...",
                ideas_per_round,
                strategy.value,
            )

            with create_span(SpanKind.AGENT, "ideator.generate", round=round_num) as _span:
                raw_ideas = await ideator.generate_ideas(
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
            with create_span(SpanKind.AGENT, "critic.evaluate", strategy=strategy.value) as _cspan:
                critiques = await critic.critique_ideas(
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
                critiques = await critic.critique_ideas(
                    ideas=raw_ideas,
                    context_papers=context_papers,
                    strategy=strategy,
                )

            critique_history.append(critiques)
            self.last_critique_history[round_num] = [c.model_dump() for c in critiques]

            # Collect critique summaries for next round
            prior_critiques = [
                f"{c.idea_title}: {'; '.join(c.weaknesses[:3])} → {'; '.join(c.suggestions[:3])}"
                for c in critiques
            ]

            # Step 3: Refine
            logger.info("Refining ideas based on critiques...")
            with create_span(SpanKind.AGENT, "refiner.refine", round=round_num) as _rspan:
                refined = await refiner.refine_ideas(
                ideas=raw_ideas,
                critiques=critiques,
                context_papers=context_papers,
                round_num=round_num,
            )

            logger.info("Refined to %d ideas", len(refined))

            # Record strategy outcome for data-driven selection
            avg_refined_score = sum(i.score for i in refined) / max(1, len(refined))
            self._strategy_tracker.record(StrategyOutcome(
                strategy=strategy,
                round_num=round_num,
                idea_count=len(refined),
                avg_score=avg_refined_score,
            ))

            # Record round-level metrics for metacognitive tracking
            if self._metacog:
                self._metacog.record_stage("idea_generation", {
                    "avg_refined_score": avg_refined_score,
                }, round_num=round_num)

            # Tag refined ideas with source gap IDs
            for idea in refined:
                if not idea.source_gap_ids:
                    idea.source_gap_ids = gap_ids

            # Record refinement traceability
            self.last_refinement_history[round_num] = {
                "round": round_num,
                "original_titles": [i.title for i in raw_ideas],
                "refined_titles": [i.title for i in refined],
                "score_changes": [
                    {"before": getattr(raw_ideas[j], "score", 0) if j < len(raw_ideas) else 0,
                     "after": refined[j].score}
                    for j in range(len(refined))
                ],
            }

            # Convergence detection
            if previous_ideas:
                if use_borda and tournament:
                    # Borda tournament convergence (autoreason pattern)
                    # In production, judge_fn would call a fresh LLM agent.
                    # For now, use score-based heuristic as judge proxy.
                    incumbent_best = max((i.score for i in previous_ideas), default=0.0)
                    refined_best = max((i.score for i in refined), default=0.0)
                    winner = "A" if incumbent_best >= refined_best else "B"
                    scores = {"A": int(incumbent_best * 10), "B": int(refined_best * 10), "AB": 0}
                    converged = tournament.check_converged(winner, scores)
                    if converged:
                        logger.info(
                            "Borda convergence at round %d (incumbent streak=%d)",
                            round_num,
                            tournament.state.streak,
                        )
                        all_ideas.extend(refined)
                        break
                else:
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

                    # Plateau detection (autonovel pattern)
                    plateau = check_plateau(critiques)
                    if plateau.converged:
                        logger.info("Plateau detected at round %d: %s", round_num, plateau.reason)
                        all_ideas.extend(refined)
                        break

                # Impasse detection (after round 1+)
                impasse = self._impasse_detector.detect(
                    current_ideas=refined,
                    previous_ideas=previous_ideas,
                    critiques=critiques,
                    critique_history=critique_history,
                    scores=[i.score for i in all_ideas],
                )
                if impasse:
                    self._pending_resolution = self._impasse_detector.resolve(impasse)
                    logger.info(
                        "Impasse detected: %s (severity=%.2f). Resolution: %s",
                        impasse.impasse_type.value,
                        impasse.severity,
                        self._pending_resolution.action,
                    )
                    # Dispatch impasse events
                    if self._hooks:
                        await self._hooks.dispatch_sync_safe(
                            "impasse.detected",
                            {"type": impasse.impasse_type.value, "severity": impasse.severity},
                        )
                        await self._hooks.dispatch_sync_safe(
                            "impasse.resolved",
                            {"action": self._pending_resolution.action},
                        )

            previous_ideas = refined
            all_ideas.extend(refined)

            # Context compression between rounds
            if round_num < rounds and prior_critiques:
                accumulated = [
                    {"role": "system", "content": f"Round {round_num} prior context"},
                    {"role": "assistant", "content": "\n".join(prior_critiques)},
                ]
                compressed = await self._working_context.compress_if_needed(
                    accumulated, round_num
                )
                if len(compressed) < len(accumulated):
                    logger.info("Context compressed between rounds %d → %d", round_num, round_num + 1)

        # Quality gate: keep only the best ideas
        max_ideas = rounds * ideas_per_round
        all_ideas = keep_best_n(all_ideas, max_ideas, min_score=0.3)

        # Sort by score and return
        return sorted(all_ideas, key=lambda i: i.score, reverse=True)
