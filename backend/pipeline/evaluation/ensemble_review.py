"""Ensemble review for proposal quality assessment.

Three separate LLM reviews from different perspectives (methodology,
novelty, clarity), then a meta-reviewer aggregates into a unified
assessment with actionable feedback.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "number"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "weaknesses": {"type": "array", "items": {"type": "string"}},
        "suggestions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["score", "strengths", "weaknesses"],
}

_META_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {"type": "number"},
        "consensus_strengths": {"type": "array", "items": {"type": "string"}},
        "critical_weaknesses": {"type": "array", "items": {"type": "string"}},
        "actionable_suggestions": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["overall_score", "summary"],
}

METHODOLOGY_REVIEWER = (
    "You are a senior methodology reviewer. Evaluate the proposal's "
    "research design, experimental rigor, statistical validity, and "
    "reproducibility. Score 0-1."
)

NOVELTY_REVIEWER = (
    "You are a novelty assessment expert. Evaluate the proposal's "
    "originality, contribution to the field, differentiation from "
    "existing work, and creative approach. Score 0-1."
)

CLARITY_REVIEWER = (
    "You are a clarity and presentation reviewer. Evaluate the "
    "proposal's writing quality, logical flow, completeness, and "
    "whether a reader could reproduce the work. Score 0-1."
)


class PerspectiveReview(BaseModel):
    """Single-perspective review result."""

    perspective: str
    score: float = Field(ge=0.0, le=1.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class EnsembleReviewResult(BaseModel):
    """Aggregated result from multi-perspective ensemble review."""

    overall_score: float = Field(ge=0.0, le=1.0)
    methodology: PerspectiveReview | None = None
    novelty: PerspectiveReview | None = None
    clarity: PerspectiveReview | None = None
    consensus_strengths: list[str] = Field(default_factory=list)
    critical_weaknesses: list[str] = Field(default_factory=list)
    actionable_suggestions: list[str] = Field(default_factory=list)
    summary: str = ""


class EnsembleReviewer:
    """Multi-perspective review with meta-review for proposals."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def review(self, proposal: Any, idea: Any = None) -> EnsembleReviewResult:
        """Run ensemble review on a research proposal.

        Args:
            proposal: ResearchProposal to review.
            idea: Optional ResearchIdea for additional context.

        Returns:
            EnsembleReviewResult with per-perspective and aggregated scores.
        """
        proposal_text = proposal.to_markdown() if hasattr(proposal, "to_markdown") else str(proposal)

        idea_context = ""
        if idea:
            idea_context = f"\nOriginal idea: {getattr(idea, 'title', '')} — {getattr(idea, 'problem_statement', '')}"

        # Run three reviews in parallel via sequential calls (provider may not support true parallel)
        meth_review = await self._run_perspective(
            METHODOLOGY_REVIEWER, proposal_text, idea_context, "methodology"
        )
        nov_review = await self._run_perspective(
            NOVELTY_REVIEWER, proposal_text, idea_context, "novelty"
        )
        clar_review = await self._run_perspective(
            CLARITY_REVIEWER, proposal_text, idea_context, "clarity"
        )

        # Meta-review aggregation
        meta = await self._meta_review(proposal_text, meth_review, nov_review, clar_review)

        return EnsembleReviewResult(
            overall_score=meta.get("overall_score", 0.5),
            methodology=meth_review,
            novelty=nov_review,
            clarity=clar_review,
            consensus_strengths=meta.get("consensus_strengths", []),
            critical_weaknesses=meta.get("critical_weaknesses", []),
            actionable_suggestions=meta.get("actionable_suggestions", []),
            summary=meta.get("summary", ""),
        )

    async def _run_perspective(
        self,
        system_prompt: str,
        proposal_text: str,
        idea_context: str,
        perspective: str,
    ) -> PerspectiveReview:
        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Review this proposal:{idea_context}\n\n{proposal_text[:3000]}"},
                ],
                schema=_REVIEW_SCHEMA,
                temperature=0.2,
            )
            score = float(result.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            return PerspectiveReview(
                perspective=perspective,
                score=score,
                strengths=result.get("strengths", []),
                weaknesses=result.get("weaknesses", []),
                suggestions=result.get("suggestions", []),
            )
        except Exception as e:
            logger.warning("Ensemble review failed for %s: %s", perspective, e)
            return PerspectiveReview(perspective=perspective, score=0.5)

    async def _meta_review(
        self,
        proposal_text: str,
        meth: PerspectiveReview,
        nov: PerspectiveReview,
        clar: PerspectiveReview,
    ) -> dict:
        reviews_summary = (
            f"Methodology review (score: {meth.score:.2f}): "
            f"Strengths: {', '.join(meth.strengths[:3])}. "
            f"Weaknesses: {', '.join(meth.weaknesses[:3])}.\n\n"
            f"Novelty review (score: {nov.score:.2f}): "
            f"Strengths: {', '.join(nov.strengths[:3])}. "
            f"Weaknesses: {', '.join(nov.weaknesses[:3])}.\n\n"
            f"Clarity review (score: {clar.score:.2f}): "
            f"Strengths: {', '.join(clar.strengths[:3])}. "
            f"Weaknesses: {', '.join(clar.weaknesses[:3])}."
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a meta-reviewer. Synthesize three peer reviews "
                            "into a unified assessment with a composite score (0-1)."
                        ),
                    },
                    {"role": "user", "content": f"Proposal:\n{proposal_text[:2000]}\n\nReviews:\n{reviews_summary}"},
                ],
                schema=_META_SCHEMA,
                temperature=0.1,
            )
            overall = float(result.get("overall_score", 0.5))
            result["overall_score"] = max(0.0, min(1.0, overall))
            return result
        except Exception as e:
            logger.warning("Meta-review failed: %s", e)
            avg = (meth.score + nov.score + clar.score) / 3
            return {"overall_score": avg, "summary": f"Meta-review failed, averaged: {avg:.2f}"}
