"""Fast proposal synthesizer for quick-scan pipeline strategy.

Produces abbreviated 3-section proposals (Abstract, Key Idea, Method Sketch)
under 3000 chars total, optimized for speed over depth.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

logger = logging.getLogger(__name__)

# Load prompt template
_PROMPT_PATH = Path(__file__).parent / "prompts" / "fast_synthesis_system.md"


def _load_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "You are a research proposal synthesizer in FAST SCAN mode.\n"
        "Generate a brief 3-section proposal: Abstract, Key Idea, Method Sketch.\n"
        "Total text under 2000 characters. Be specific.\n"
    )


class FastProposalSynthesizer:
    """Produces abbreviated 3-section proposals for fast_scan strategy.

    Each proposal has exactly 3 sections:
    - Abstract (2-3 sentences)
    - Key Idea (3-5 sentences)
    - Method Sketch (3-5 sentences)

    Total text is kept under 3000 chars for quick reading.
    """

    MAX_TOTAL_CHARS = 3000

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider
        self._system_prompt = _load_prompt()

    async def synthesize(
        self,
        ideas: list[Any] | Any | None = None,
        gaps: list[Any] | None = None,
        papers: list[Any] | None = None,
        # Accept single-idea kwargs for compatibility with ProposalSynthesisStage
        idea: Any | None = None,
        novelty_report: Any | None = None,
        feasibility_report: Any | None = None,
        supporting_papers: list[Any] | None = None,
        framing_directive: str = "",
    ) -> list[ResearchProposal]:
        """Generate brief proposals for each idea.

        Accepts both list-based (ideas=) and single-idea (idea=) calling
        conventions for compatibility with different stage callers.

        Args:
            ideas: List of idea objects, or a single idea object.
            gaps: List of research gap objects.
            papers: Optional list of paper objects for context.
            idea: Single idea object (alternative to ideas=).
            supporting_papers: Alias for papers.
            framing_directive: Strategic framing hint (used by governance).

        Returns:
            List of ResearchProposal objects with 3 sections each.
        """
        # Normalize to list regardless of calling convention
        single_mode = idea is not None  # caller expects single ResearchProposal back
        if idea is not None and not ideas:
            ideas = [idea]
        elif idea is not None and isinstance(ideas, list):
            ideas = [idea]  # single-idea mode takes precedence
        if not isinstance(ideas, list):
            ideas = [ideas]
        if not ideas:
            return []

        # Use supporting_papers as alias for papers
        ctx_papers = papers or supporting_papers or []

        proposals: list[ResearchProposal] = []

        # Build context from gaps and papers
        gap_text = self._summarize_gaps(gaps or [])
        paper_text = self._summarize_papers(ctx_papers)

        for idea in ideas:
            try:
                proposal = await self._synthesize_one(idea, gap_text, paper_text)
                proposals.append(proposal)
            except Exception as e:
                logger.warning("Fast synthesis failed for idea '%s': %s", getattr(idea, "title", "?"), e)
                # Graceful degradation: return a minimal proposal
                proposals.append(self._fallback_proposal(idea))

        # Return single proposal in single-idea mode for ProposalSynthesisStage compat
        if single_mode:
            return proposals[0] if proposals else self._fallback_proposal(idea)
        return proposals

    async def _synthesize_one(
        self, idea: Any, gap_text: str, paper_text: str
    ) -> ResearchProposal:
        """Synthesize a single 3-section proposal via LLM."""
        if self._provider is None:
            return self._fallback_proposal(idea)

        idea_title = getattr(idea, "title", "Untitled Idea")
        idea_desc = getattr(idea, "description", "")
        idea_domain = getattr(idea, "domain", "AI/NLP")

        user_prompt = (
            f"Research Idea: {idea_title}\n"
            f"Domain: {idea_domain}\n"
            f"Description: {idea_desc}\n\n"
            f"Identified Gaps:\n{gap_text}\n\n"
            f"Key Papers:\n{paper_text}\n\n"
            f"Generate a brief 3-section proposal (Abstract, Key Idea, Method Sketch) "
            f"for this research idea. Keep total text under 2000 characters."
        )

        try:
            response = await self._provider.complete(
                system_prompt=self._system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500,
            )
        except TimeoutError:
            logger.warning("LLM timeout during fast synthesis for '%s'", idea_title)
            return self._fallback_proposal(idea)
        except Exception as e:
            logger.warning("LLM error during fast synthesis: %s", e)
            return self._fallback_proposal(idea)

        # Parse sections from response
        sections = self._parse_sections(response)
        return ResearchProposal(
            title=idea_title,
            domain=idea_domain,
            **sections,
            strategy="fast_scan",
            lightweight=True,
        )

    def _parse_sections(self, text: str) -> dict[str, str]:
        """Parse the 3 sections from LLM response."""
        sections: dict[str, str] = {
            "Abstract": "",
            "Key Idea": "",
            "Method Sketch": "",
        }

        current_section = None
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## Abstract"):
                current_section = "Abstract"
            elif stripped.startswith("## Key Idea"):
                current_section = "Key Idea"
            elif stripped.startswith("## Method Sketch"):
                current_section = "Method Sketch"
            elif current_section and stripped:
                sections[current_section] += stripped + " "

        # Trim whitespace
        for key in sections:
            sections[key] = sections[key].strip()

        # If sections are empty, put everything in Abstract
        if not any(sections.values()):
            sections["Abstract"] = text.strip()[:1000]

        return sections

    def _fallback_proposal(self, idea: Any) -> ResearchProposal:
        """Create a minimal fallback proposal when LLM fails."""
        title = getattr(idea, "title", "Untitled")
        domain = getattr(idea, "domain", "AI/NLP")
        desc = getattr(idea, "description", "")

        return ResearchProposal(
            title=title,
            domain=domain,
            **{
                "Abstract": f"Research idea: {title}. {desc[:200]}",
                "Key Idea": "Generation incomplete — run deep research for full proposal.",
                "Method Sketch": "Run deep_research strategy for detailed methodology.",
                "strategy": "fast_scan",
                "lightweight": True,
                "fallback": True,
            },
        )

    @staticmethod
    def _summarize_gaps(gaps: list[Any]) -> str:
        if not gaps:
            return "No gaps identified."
        lines = []
        for i, gap in enumerate(gaps[:5], 1):
            title = getattr(gap, "title", getattr(gap, "name", f"Gap {i}"))
            desc = getattr(gap, "description", "")
            lines.append(f"  {i}. {title}: {desc[:150]}")
        return "\n".join(lines)

    @staticmethod
    def _summarize_papers(papers: list[Any]) -> str:
        if not papers:
            return "No papers in context."
        lines = []
        for i, paper in enumerate(papers[:10], 1):
            title = getattr(paper, "title", f"Paper {i}")
            year = getattr(paper, "year", "")
            lines.append(f"  {i}. {title} ({year})")
        return "\n".join(lines)
