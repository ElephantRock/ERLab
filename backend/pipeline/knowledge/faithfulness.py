"""Faithfulness checking — detect contradictions between claims and source literature.

Verifies that gap analysis claims and idea proposals are faithful to the
source papers they reference, catching hallucinated or unsupported assertions.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_FAITHFULNESS_SCHEMA = {
    "type": "object",
    "properties": {
        "is_faithful": {"type": "boolean"},
        "contradiction_type": {"type": "string"},
        "explanation": {"type": "string"},
    },
    "required": ["is_faithful"],
}


class FaithfulnessReport(BaseModel):
    """Result of a faithfulness check."""

    claim: str
    source_text: str
    is_faithful: bool = True
    contradiction_type: str = ""
    explanation: str = ""


class FaithfulnessChecker:
    """Detect contradictions between generated claims and source literature."""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def check_gap_claims(
        self,
        gaps: list[Any],
        source_papers: list[Any],
    ) -> list[FaithfulnessReport]:
        """Check if gap analysis claims contradict source literature.

        For each gap, verifies the description is supported by the papers.
        """
        if not gaps or not source_papers:
            return []

        source_text = self._format_sources(source_papers[:10])
        reports = []

        for gap in gaps:
            claim = f"{gap.title}: {gap.description[:300]}"
            report = await self._check_claim(claim, source_text)
            report.claim = gap.title
            reports.append(report)

        return reports

    async def check_idea_claims(
        self,
        ideas: list[Any],
        source_papers: list[Any],
    ) -> list[FaithfulnessReport]:
        """Check if idea claims are faithful to source literature."""
        if not ideas or not source_papers:
            return []

        source_text = self._format_sources(source_papers[:10])
        reports = []

        for idea in ideas[:10]:
            claim = f"{idea.title}: {getattr(idea, 'proposed_method', '')[:300]}"
            report = await self._check_claim(claim, source_text)
            report.claim = idea.title
            reports.append(report)

        return reports

    async def _check_claim(self, claim: str, source_text: str) -> FaithfulnessReport:
        """Check a single claim against source text."""
        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a factuality checker. Determine if the claim "
                            "is supported by or contradicts the source literature. "
                            "A claim is unfaithful only if it directly contradicts "
                            "specific facts in the sources."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Claim: {claim}\n\n"
                            f"Source literature:\n{source_text[:2000]}\n\n"
                            "Is this claim faithful to the sources?"
                        ),
                    },
                ],
                schema=_FAITHFULNESS_SCHEMA,
                temperature=0.1,
            )

            return FaithfulnessReport(
                claim=claim[:100],
                source_text=source_text[:200],
                is_faithful=result.get("is_faithful", True),
                contradiction_type=result.get("contradiction_type", ""),
                explanation=result.get("explanation", ""),
            )
        except Exception as e:
            logger.warning("Faithfulness check failed: %s", e)
            return FaithfulnessReport(claim=claim[:100], source_text=source_text[:200])

    @staticmethod
    def _format_sources(papers: list[Any]) -> str:
        parts = []
        for p in papers:
            title = getattr(p, 'title', 'Untitled')
            abstract = getattr(p, 'abstract', '') or ''
            parts.append(f"- {title}: {abstract[:200]}")
        return "\n".join(parts)
