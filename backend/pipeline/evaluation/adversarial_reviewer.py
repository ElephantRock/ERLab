"""Adversarial reviewer — cross-model critical evaluation of research proposals.

Uses a different model family than the proposal synthesizer to provide
an adversarial, critical review. Proposals must score ≥ 7/10 overall
(on Soundness, Novelty, Feasibility, Clarity) to be accepted.

HB-02: Must use a different provider than the synthesizer.
HB-03: Graceful fallback on LLM failure.
HB-05: All scores clamped to [1, 10].
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "adversarial_review.md"

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "soundness": {"type": "integer"},
        "novelty": {"type": "integer"},
        "feasibility": {"type": "integer"},
        "clarity": {"type": "integer"},
        "soundness_justification": {"type": "string"},
        "novelty_justification": {"type": "string"},
        "feasibility_justification": {"type": "string"},
        "clarity_justification": {"type": "string"},
        "revision_notes": {"type": "string"},
    },
    "required": [
        "soundness", "novelty", "feasibility", "clarity",
        "soundness_justification", "novelty_justification",
        "feasibility_justification", "clarity_justification",
        "revision_notes",
    ],
}


def _clamp(value: int, low: int = 1, high: int = 10) -> int:
    """Clamp a score to the valid range."""
    if value < low:
        logger.warning("Score %d below minimum %d — clamping", value, low)
        return low
    if value > high:
        logger.warning("Score %d above maximum %d — clamping", value, high)
        return high
    return value


@dataclass
class AdversarialReviewScore:
    """Structured adversarial review score for a research proposal.

    12 fields: 4 dimension scores, overall (computed), 4 justifications,
    revision notes, round, and model_used.
    """

    soundness: int
    novelty: int
    feasibility: int
    clarity: int
    overall: float
    soundness_justification: str
    novelty_justification: str
    feasibility_justification: str
    clarity_justification: str
    revision_notes: str | None
    round: int
    model_used: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdversarialReviewer:
    """Critical cross-model reviewer for research proposals.

    Accepts an injected provider (must differ from the synthesizer's provider).
    Uses structured LLM output to score proposals on 4 dimensions.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        try:
            self._prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning("Adversarial review prompt not found at %s — using inline default", PROMPT_PATH)
            self._prompt_template = (
                "You are a critical adversarial reviewer. Evaluate the following research proposal.\n"
                "Score each dimension 1-10. Be harsh. Find weaknesses. Challenge assumptions.\n\n"
                "{proposal_text}\n\nSource Papers:\n{source_papers}"
            )

    async def review(
        self,
        proposal_text: str,
        source_papers: list[str] | None = None,
        round_num: int = 1,
        context_window: int = 8192,
    ) -> AdversarialReviewScore:
        """Run adversarial review on a proposal.

        Uses a compressed review packet instead of passing the full proposal + sources.
        The critic doesn't need the entire artifact — it needs the core claims,
        method, and evaluation plan.

        Args:
            proposal_text: Full text of the research proposal.
            source_papers: Optional list of source paper abstracts/titles.
            round_num: Review round number (1=initial, 2-3=revisions).
            context_window: Model's context window for budget estimation.

        Returns:
            AdversarialReviewScore with dimension scores and justifications.
            On failure, returns a fallback score with all zeros.
        """
        # Build a compressed review packet instead of passing raw text
        review_packet = self._build_review_packet(proposal_text, source_papers)

        # Estimate if review packet fits in context
        estimated_tokens = len(review_packet) // 3 + 1500  # prompt + output
        if estimated_tokens > context_window:
            logger.info(
                "Adversarial review: compressed review packet (%d est tokens) for ctx=%d",
                estimated_tokens, context_window,
            )
            # Further compress — strip to essentials
            review_packet = self._build_minimal_review_packet(proposal_text)

        prompt = self._prompt_template.format(
            proposal_text=review_packet,
            source_papers="See embedded references in review packet.",
        )

        try:
            result = await self._provider.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an adversarial peer reviewer. Your job is to find "
                            "weaknesses, challenge assumptions, and demand rigor. Be critical. "
                            "Score each dimension as an integer from 1 to 10. "
                            "If the overall quality is below 7.0, provide detailed revision notes."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                schema=SCORE_SCHEMA,
                temperature=0.3,
            )

            return self._parse_result(result, round_num)

        except Exception as e:
            logger.warning(
                "Adversarial review LLM call failed (HB-03): %s — returning fallback score", e,
            )
            return AdversarialReviewScore(
                soundness=0,
                novelty=0,
                feasibility=0,
                clarity=0,
                overall=0.0,
                soundness_justification=f"Review skipped: {e}",
                novelty_justification=f"Review skipped: {e}",
                feasibility_justification=f"Review skipped: {e}",
                clarity_justification=f"Review skipped: {e}",
                revision_notes=None,
                round=0,
                model_used="none",
            )

    def _parse_result(self, result: dict[str, Any], round_num: int) -> AdversarialReviewScore:
        """Parse structured LLM output into AdversarialReviewScore.

        Clamps all scores to [1, 10] (HB-05). Computes overall as mean.
        """
        soundness = _clamp(int(result.get("soundness", 5)))
        novelty = _clamp(int(result.get("novelty", 5)))
        feasibility = _clamp(int(result.get("feasibility", 5)))
        clarity = _clamp(int(result.get("clarity", 5)))
        overall = (soundness + novelty + feasibility + clarity) / 4.0

        revision_notes = result.get("revision_notes", "") or ""
        # Only populate revision notes when overall < 7.0
        if overall >= 7.0:
            revision_notes = None
        elif not revision_notes.strip():
            revision_notes = "Overall score below 7.0 — revision recommended."
        else:
            # Cap at 500 words
            words = revision_notes.split()
            if len(words) > 500:
                revision_notes = " ".join(words[:500])
                logger.warning("Revision notes truncated to 500 words")

        return AdversarialReviewScore(
            soundness=soundness,
            novelty=novelty,
            feasibility=feasibility,
            clarity=clarity,
            overall=overall,
            soundness_justification=str(result.get("soundness_justification", "")),
            novelty_justification=str(result.get("novelty_justification", "")),
            feasibility_justification=str(result.get("feasibility_justification", "")),
            clarity_justification=str(result.get("clarity_justification", "")),
            revision_notes=revision_notes,
            round=round_num,
            model_used=getattr(self._provider, "provider_name", type(self._provider).__name__),
        )

    @staticmethod
    def _build_review_packet(
        proposal_text: str,
        source_papers: list[str] | None = None,
        max_chars: int = 4000,
    ) -> str:
        """Build a compressed review packet for the adversarial reviewer.

        Instead of passing the full proposal + all sources, extract:
        - Title
        - Core claim list
        - Method summary
        - Evaluation plan summary
        - Top cited evidence cards
        - Known weak points

        This reduces the prompt from ~9000 tokens to ~3000-4000.
        """
        lines = []

        # Extract sections by common headings
        sections = AdversarialReviewer._extract_sections(proposal_text)

        # Title
        title = sections.get("title", "")
        if not title:
            # Try to get first line as title
            first_line = proposal_text.strip().split("\n")[0]
            title = first_line.lstrip("# ").strip()[:200]
        lines.append(f"# Title: {title}")

        # Core claims / introduction
        intro = sections.get("introduction", "")
        if intro:
            lines.append(f"\n## Introduction (first 500 chars)\n{intro[:500]}")

        # Method summary
        method = sections.get("proposed_method", sections.get("method", ""))
        if method:
            lines.append(f"\n## Proposed Method (first 800 chars)\n{method[:800]}")

        # Evaluation plan
        eval_plan = sections.get("evaluation_plan", sections.get("evaluation", ""))
        if eval_plan:
            lines.append(f"\n## Evaluation Plan (first 500 chars)\n{eval_plan[:500]}")

        # Related work summary (just citations count)
        related = sections.get("related_work", "")
        if related:
            cite_count = len(re.findall(r'\[SOURCE-\d+\]', related))
            lines.append(f"\n## Related Work: {cite_count} citations referenced")

        # Source paper cards (compressed)
        if source_papers:
            lines.append("\n## Referenced Sources (titles only):")
            for i, paper in enumerate(source_papers[:15]):
                # Extract just the first line (citation + title)
                first_line = paper.split("\n")[0][:150]
                lines.append(f"  {first_line}")

        # Assemble and truncate to max_chars
        packet = "\n".join(lines)
        if len(packet) > max_chars:
            packet = packet[:max_chars] + "\n\n[Review packet truncated to fit context]"

        return packet

    @staticmethod
    def _build_minimal_review_packet(proposal_text: str, max_chars: int = 2000) -> str:
        """Ultra-compressed review packet for very small context windows."""
        lines = []

        # Title (first non-empty line)
        for line in proposal_text.strip().split("\n"):
            stripped = line.strip().lstrip("# ")
            if stripped and len(stripped) > 5:
                lines.append(f"Title: {stripped[:200]}")
                break

        # First 1000 chars as summary
        lines.append(f"\nSummary:\n{proposal_text[:1000]}")

        # Last 500 chars as conclusion
        if len(proposal_text) > 1500:
            lines.append(f"\nConclusion:\n{proposal_text[-500:]}")

        return "\n".join(lines)[:max_chars]

    @staticmethod
    def _extract_sections(text: str) -> dict[str, str]:
        """Extract sections from markdown text by ## headings."""
        sections = {}
        current_heading = "title"
        current_content: list[str] = []

        for line in text.split("\n"):
            if line.startswith("## "):
                # Save previous section
                if current_content:
                    sections[current_heading] = "\n".join(current_content).strip()
                current_heading = line.lstrip("# ").strip().lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_heading] = "\n".join(current_content).strip()

        return sections
