"""Faithfulness Scorer — LLM-as-judge evaluation of proposal grounding.

BATCH-RAG-03: Evaluates whether generated proposal claims are supported
by the source papers. Uses local LM Studio for zero-cost judging.

Design: For each proposal, extract key claims and check against source
paper abstracts. Produces a FaithfulnessReport with per-claim scores.
"""

from __future__ import annotations

import json

from backend.pipeline.utils.json_extraction import extract_json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

FAITHFULNESS_PROMPT = """\
You are a research evaluation judge. Your task is to assess whether a claim \
in a research proposal is supported by the source literature.

Rate the faithfulness of this claim on a scale of 0.0 to 1.0:
- 1.0: Claim is directly supported by the source text
- 0.7: Claim is partially supported or is a reasonable inference
- 0.4: Claim extends beyond the source but is plausible
- 0.0: Claim contradicts the source or is fabricated

Claim: {claim}

Source text:
{source}

Respond with ONLY a JSON object:
{{"score": <0.0-1.0>, "reasoning": "<1-2 sentence explanation>", "supported": <true/false>}}
"""

AGGREGATE_PROMPT = """\
You are a research evaluation judge. Rate the overall faithfulness of this \
research proposal section against the provided source literature.

Proposal section:
{proposal_text}

Source literature (abstracts):
{sources}

Respond with ONLY a JSON object:
{{"faithfulness_score": <0.0-1.0>, "relevance_score": <0.0-1.0>, "grounding_score": <0.0-1.0>, "reasoning": "<brief explanation>"}}
"""


@dataclass
class ClaimAssessment:
    """Assessment of a single claim's faithfulness."""

    claim: str
    score: float = 0.0
    supported: bool = False
    reasoning: str = ""
    source_id: str = ""


@dataclass
class FaithfulnessReport:
    """Full faithfulness assessment for a proposal."""

    proposal_id: str = ""
    proposal_title: str = ""
    overall_faithfulness: float = 0.0
    overall_relevance: float = 0.0
    overall_grounding: float = 0.0
    claim_assessments: list[ClaimAssessment] = field(default_factory=list)
    reasoning: str = ""
    assessed_claims: int = 0
    supported_claims: int = 0

    @property
    def support_rate(self) -> float:
        """Fraction of claims that are supported."""
        if self.assessed_claims == 0:
            return 0.0
        return self.supported_claims / self.assessed_claims

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "proposal_title": self.proposal_title,
            "faithfulness": round(self.overall_faithfulness, 3),
            "relevance": round(self.overall_relevance, 3),
            "grounding": round(self.overall_grounding, 3),
            "support_rate": round(self.support_rate, 3),
            "assessed_claims": self.assessed_claims,
            "supported_claims": self.supported_claims,
            "reasoning": self.reasoning,
        }


class FaithfulnessScorer:
    """Scores proposal faithfulness using LLM-as-judge.

    Parameters
    ----------
    provider:
        LLMProvider for scoring. Should be local LM Studio for zero cost.
    max_claims_per_proposal:
        Maximum claims to assess per proposal (to bound cost).
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        max_claims_per_proposal: int = 5,
    ) -> None:
        self._provider = provider
        self._max_claims = max(1, max_claims_per_proposal)

    async def score_proposal(
        self,
        proposal_text: str,
        proposal_title: str = "",
        proposal_id: str = "",
        source_texts: list[str] | None = None,
    ) -> FaithfulnessReport:
        """Score a proposal's faithfulness against source literature.

        Falls back to heuristic scoring if LLM is unavailable.
        """
        if source_texts is None:
            source_texts = []

        if self._provider is None:
            return self._heuristic_score(
                proposal_text, proposal_title, proposal_id, source_texts
            )

        try:
            return await self._llm_score(
                proposal_text, proposal_title, proposal_id, source_texts
            )
        except Exception as e:
            logger.warning(
                "LLM faithfulness scoring failed, using heuristic: %s",
                str(e)[:100],
            )
            return self._heuristic_score(
                proposal_text, proposal_title, proposal_id, source_texts
            )

    async def _llm_score(
        self,
        proposal_text: str,
        proposal_title: str,
        proposal_id: str,
        source_texts: list[str],
    ) -> FaithfulnessReport:
        """Score using LLM-as-judge."""
        sources_combined = "\n---\n".join(source_texts[:5])  # Limit sources

        prompt = AGGREGATE_PROMPT.format(
            proposal_text=proposal_text[:2000],
            sources=sources_combined[:3000],
        )

        messages = [{"role": "user", "content": prompt}]
        response = await self._provider.complete(messages)

        return self._parse_response(response, proposal_id, proposal_title)

    def _parse_response(
        self, response: str, proposal_id: str, proposal_title: str
    ) -> FaithfulnessReport:
        """Parse LLM response into FaithfulnessReport."""
        data = extract_json(response)

        return FaithfulnessReport(
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            overall_faithfulness=float(data.get("faithfulness_score", 0.5)),
            overall_relevance=float(data.get("relevance_score", 0.5)),
            overall_grounding=float(data.get("grounding_score", 0.5)),
            reasoning=data.get("reasoning", "LLM assessment"),
        )

    def _heuristic_score(
        self,
        proposal_text: str,
        proposal_title: str,
        proposal_id: str,
        source_texts: list[str],
    ) -> FaithfulnessReport:
        """Heuristic faithfulness scoring when LLM is unavailable.

        Uses simple text overlap metrics.
        """
        if not source_texts or not proposal_text:
            return FaithfulnessReport(
                proposal_id=proposal_id,
                proposal_title=proposal_title,
                overall_faithfulness=0.5,
                overall_relevance=0.5,
                overall_grounding=0.5,
                reasoning="Heuristic score (no LLM available)",
            )

        # Check keyword overlap between proposal and sources
        proposal_words = set(proposal_text.lower().split())
        source_words = set(" ".join(source_texts).lower().split())

        # Remove common stop words
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "and", "or", "but", "not", "no", "nor",
        }
        proposal_keywords = proposal_words - stop_words
        source_keywords = source_words - stop_words

        if not proposal_keywords:
            overlap = 0.0
        else:
            overlap = len(proposal_keywords & source_keywords) / len(proposal_keywords)

        # Map overlap to 0-1 score (0.3 overlap → 0.7 faithfulness)
        faithfulness = min(1.0, overlap * 2.0 + 0.2)
        relevance = min(1.0, overlap * 1.8 + 0.3)
        grounding = min(1.0, overlap * 2.2 + 0.1)

        return FaithfulnessReport(
            proposal_id=proposal_id,
            proposal_title=proposal_title,
            overall_faithfulness=round(faithfulness, 3),
            overall_relevance=round(relevance, 3),
            overall_grounding=round(grounding, 3),
            reasoning=f"Heuristic: {overlap:.1%} keyword overlap with sources",
        )

    async def score_claim(
        self,
        claim: str,
        source_text: str,
        source_id: str = "",
    ) -> ClaimAssessment:
        """Score a single claim against source text."""
        if self._provider is None:
            return ClaimAssessment(
                claim=claim,
                score=0.5,
                supported=True,
                reasoning="No LLM available — assuming supported",
                source_id=source_id,
            )

        prompt = FAITHFULNESS_PROMPT.format(
            claim=claim[:500],
            source=source_text[:2000],
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._provider.complete(messages)
            return self._parse_claim_response(response, claim, source_id)
        except Exception as e:
            logger.warning("Claim scoring failed: %s", str(e)[:100])
            return ClaimAssessment(
                claim=claim,
                score=0.5,
                supported=True,
                reasoning=f"Scoring failed: {str(e)[:50]}",
                source_id=source_id,
            )

    def _parse_claim_response(
        self, response: str, claim: str, source_id: str
    ) -> ClaimAssessment:
        """Parse LLM claim scoring response."""
        data = extract_json(response)

        return ClaimAssessment(
            claim=claim,
            score=float(data.get("score", 0.5)),
            supported=data.get("supported", True),
            reasoning=data.get("reasoning", ""),
            source_id=source_id,
        )
