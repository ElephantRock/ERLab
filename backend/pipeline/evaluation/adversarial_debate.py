"""Adversarial debate for idea quality assessment.

Uses three NegotiationAgent instances with distinct roles (Optimist, Skeptic,
Contrarian) to debate the merits of a research idea. The debate follows
propose -> critique -> rebut -> vote rounds, producing a consensus score
that reflects multi-perspective evaluation.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.pipeline.negotiation.agent import NegotiationAgent
from backend.pipeline.negotiation.protocol import Proposal

logger = logging.getLogger(__name__)

OPTIMIST_ROLE = (
    "optimist in a research idea debate. Argue FOR this research idea, "
    "focusing on strengths, novelty, feasibility, and potential impact."
)
SKEPTIC_ROLE = (
    "skeptic in a research idea debate. Argue AGAINST this research idea, "
    "focusing on weaknesses, risks, missing evidence, and potential flaws."
)
CONTRARIAN_ROLE = (
    "contrarian in a research idea debate. Provide ALTERNATIVE perspectives, "
    "finding angles neither optimist nor skeptic considered, including "
    "ethical, practical, and long-term implications."
)


class DebateResult(BaseModel):
    """Result of an adversarial debate on a research idea."""

    idea_title: str
    consensus_score: float = Field(ge=0.0, le=1.0)
    optimist_score: float = 0.0
    skeptic_score: float = 0.0
    contrarian_score: float = 0.0
    optimist_arguments: list[str] = Field(default_factory=list)
    skeptic_arguments: list[str] = Field(default_factory=list)
    contrarian_arguments: list[str] = Field(default_factory=list)
    rounds_completed: int = 0
    key_insights: list[str] = Field(default_factory=list)


class AdversarialDebate:
    """Three-agent adversarial debate for idea quality assessment.

    Agents: Optimist (strengths), Skeptic (weaknesses),
    Contrarian (alternative perspectives).
    Uses existing NegotiationAgent for propose->critique->rebut->vote flow.
    """

    def __init__(self, provider: Any, rounds: int = 2) -> None:
        self._provider = provider
        self._rounds = max(1, rounds)

        self._optimist = NegotiationAgent(
            agent_id="debate_optimist",
            provider=provider,
            capabilities=["propose", "critique", "rebut", "vote"],
            role=OPTIMIST_ROLE,
        )
        self._skeptic = NegotiationAgent(
            agent_id="debate_skeptic",
            provider=provider,
            capabilities=["propose", "critique", "rebut", "vote"],
            role=SKEPTIC_ROLE,
        )
        self._contrarian = NegotiationAgent(
            agent_id="debate_contrarian",
            provider=provider,
            capabilities=["propose", "critique", "rebut", "vote"],
            role=CONTRARIAN_ROLE,
        )

    async def debate(self, idea: Any, context: str = "") -> DebateResult:
        """Run an adversarial debate on a research idea.

        Args:
            idea: Research idea to debate (must have .title and string repr).
            context: Additional context (papers, gaps, domain info).

        Returns:
            DebateResult with consensus score and per-agent arguments.
        """
        idea_title = getattr(idea, "title", str(idea)[:80])
        idea_text = str(idea)
        topic = f"Research Idea: {idea_title}\n\n{idea_text}"

        optimist_args: list[str] = []
        skeptic_args: list[str] = []
        contrarian_args: list[str] = []

        current_proposal: Proposal | None = None

        for round_num in range(1, self._rounds + 1):
            # Propose phase — optimist opens with strengths
            opt_proposal = await self._optimist.propose(
                topic, context=context, prior_proposals=[current_proposal] if current_proposal else None
            )
            optimist_args.append(opt_proposal.content)
            current_proposal = opt_proposal

            # Critique phase — skeptic and contrarian critique
            skeptic_critique = await self._skeptic.critique(opt_proposal, context=context)
            skeptic_args.append(skeptic_critique)

            contrarian_critique = await self._contrarian.critique(opt_proposal, context=context)
            contrarian_args.append(contrarian_critique)

            # Rebut phase — optimist rebuts the critiques
            combined_critique = f"Skeptic: {skeptic_critique}\nContrarian: {contrarian_critique}"
            rebuttal = await self._optimist.rebut(opt_proposal, combined_critique, context=context)
            optimist_args.append(rebuttal)

        # Vote phase — all agents score the idea
        vote_proposals = [current_proposal] if current_proposal else []
        if not vote_proposals:
            return DebateResult(
                idea_title=idea_title,
                consensus_score=0.5,
                rounds_completed=self._rounds,
            )

        opt_votes = await self._optimist.vote(vote_proposals, context=context)
        skep_votes = await self._skeptic.vote(vote_proposals, context=context)
        con_votes = await self._contrarian.vote(vote_proposals, context=context)

        opt_score = opt_votes[0].score if opt_votes else 0.5
        skep_score = skep_votes[0].score if skep_votes else 0.5
        con_score = con_votes[0].score if con_votes else 0.5

        # Weighted consensus: optimist 0.3, skeptic 0.35, contrarian 0.35
        consensus = (opt_score * 0.3 + skep_score * 0.35 + con_score * 0.35)
        consensus = max(0.0, min(1.0, consensus))

        key_insights = self._extract_insights(optimist_args, skeptic_args, contrarian_args)

        return DebateResult(
            idea_title=idea_title,
            consensus_score=consensus,
            optimist_score=opt_score,
            skeptic_score=skep_score,
            contrarian_score=con_score,
            optimist_arguments=optimist_args,
            skeptic_arguments=skeptic_args,
            contrarian_arguments=contrarian_args,
            rounds_completed=self._rounds,
            key_insights=key_insights,
        )

    @staticmethod
    def _extract_insights(
        optimist_args: list[str],
        skeptic_args: list[str],
        contrarian_args: list[str],
    ) -> list[str]:
        """Extract the most insightful argument from each perspective."""
        insights = []
        for args, label in [
            (optimist_args, "Strength"),
            (skeptic_args, "Risk"),
            (contrarian_args, "Alternative"),
        ]:
            if args:
                longest = max(args, key=len)
                snippet = longest[:200].strip()
                if snippet:
                    insights.append(f"[{label}] {snippet}")
        return insights[:5]
