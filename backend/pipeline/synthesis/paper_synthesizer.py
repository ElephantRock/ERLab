"""Paper synthesis — expand a research proposal into a full academic paper.

Uses the generation provider (A-01) to convert proposal text + source papers
into a structured academic paper with proper sections and [SOURCE-X] citations.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "paper_synthesis_system.md"


@dataclass
class PaperSynthesisResult:
    """Result of expanding a proposal into a full academic paper."""

    proposal_id: int
    paper_markdown: str
    word_count: int
    venue: str
    model_used: str
    source_count: int

    def to_dict(self) -> dict:
        return asdict(self)


class PaperSynthesizer:
    """Expand a research proposal into a full academic paper via LLM.

    Uses the generation provider (cloud) — this is a generation task (A-01).
    Gracefully returns None on LLM failure (HB-02).
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        self._system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def synthesize(
        self,
        proposal_text: str,
        source_papers: list[str],
        domain: str = "AI/NLP",
        venue: str = "Generic",
        proposal_id: int = 0,
    ) -> PaperSynthesisResult | None:
        """Expand proposal text into a full academic paper.

        Args:
            proposal_text: The proposal markdown (post-adversarial-review).
            source_papers: List of formatted source strings (e.g. "[SOURCE-1] ...").
            domain: Research domain (e.g. "AI/NLP").
            venue: Target venue name (e.g. "IEEE", "ACM").
            proposal_id: Identifier for the proposal.

        Returns:
            PaperSynthesisResult on success, None on LLM failure (HB-02).
        """
        user_content = self._build_user_prompt(proposal_text, source_papers, domain)

        try:
            raw = await self._provider.complete(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.4,
                max_tokens=8192,
            )
        except Exception as e:
            logger.warning("Paper synthesis LLM call failed (HB-02): %s", e)
            return None

        if not raw or not raw.strip():
            logger.warning("Paper synthesis returned empty output (HB-02)")
            return None

        word_count = len(raw.split())

        model_used = getattr(self._provider, "default_model", "unknown")
        if callable(model_used):
            model_used = model_used()
        model_used = str(model_used)

        source_count = len(source_papers)

        if word_count < 2000:
            logger.warning(
                "Paper synthesis produced only %d words (HB-05: minimum 2000). "
                "Accepting best-effort output.",
                word_count,
            )

        return PaperSynthesisResult(
            proposal_id=proposal_id,
            paper_markdown=raw,
            word_count=word_count,
            venue=venue,
            model_used=model_used,
            source_count=source_count,
        )

    @staticmethod
    def _build_user_prompt(
        proposal_text: str,
        source_papers: list[str],
        domain: str,
    ) -> str:
        """Build the user prompt with proposal + source literature."""
        parts = [
            f"## Research Domain\n{domain}\n",
            "## Supporting Literature (CLOSED-BOOK — cite only these)\n",
        ]

        if source_papers:
            for paper_str in source_papers:
                parts.append(paper_str)
        else:
            parts.append("No specific supporting papers provided.")

        parts.append("\n## Research Proposal to Expand\n")
        parts.append(proposal_text)

        parts.append(
            "\n\nNow write a complete academic paper expanding this proposal. "
            "Follow the section structure from your instructions. "
            "Use [SOURCE-X] citations referencing only the papers listed above."
        )

        return "\n".join(parts)
