"""Consolidated Context Window (CCW) for pipeline stages.

Ported from MOSAIC (arXiv:2510.08804v3) CCW pattern.
Instead of passing full content between pipeline stages, compresses
to function-signature-like summaries (title + one-line contribution).

MOSAIC ablation result:
  - Full prior code in context: -43% performance (catastrophic)
  - Headers + 1-line summaries only: +71% performance (best result)
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PaperSummary:
    """Compressed paper representation for downstream stages."""
    id: str
    title: str
    summary: str  # One-line contribution summary (max 200 chars)
    year: int = 0
    citation_count: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "year": self.year,
            "citation_count": self.citation_count,
        }


@dataclass
class GapSummary:
    """Compressed gap representation for downstream stages."""
    id: str
    title: str
    summary: str  # One-line gap description (max 200 chars)
    confidence: float = 0.0
    gap_type: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "confidence": self.confidence,
            "gap_type": self.gap_type,
        }


@dataclass
class IdeaSummary:
    """Compressed idea representation for downstream stages."""
    id: str
    title: str
    summary: str  # One-line idea description (max 200 chars)
    score: float = 0.0
    source_gap_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "score": self.score,
            "source_gap_ids": self.source_gap_ids,
        }


@dataclass
class ConsolidatedContextWindow:
    """Compressed context for downstream pipeline stages.

    Inspired by MOSAIC's CCW: stores only titles + one-line summaries
    instead of full abstracts/descriptions/methods. This prevents
    context overflow and reduces hallucination in downstream stages.

    Usage:
        After gap_analysis: ccw.add_papers(papers), ccw.add_gaps(gaps)
        Before idea_generation: use ccw.get_paper_summaries()
        Before proposal_synthesis: use ccw.get_idea_summaries()
    """
    papers: list[PaperSummary] = field(default_factory=list)
    gaps: list[GapSummary] = field(default_factory=list)
    ideas: list[IdeaSummary] = field(default_factory=list)

    def add_papers(self, papers: list[Any]) -> None:
        """Compress full papers into title + summary."""
        self.papers = []
        for p in papers:
            paper_id = str(getattr(p, "id", getattr(p, "paper_id", "")))
            title = getattr(p, "title", "")
            abstract = getattr(p, "abstract", "") or ""
            year = getattr(p, "year", 0) or 0
            citation_count = getattr(p, "citation_count", 0) or 0

            # One-line summary: first sentence of abstract, max 200 chars
            summary = _extract_first_sentence(abstract, max_chars=200)

            self.papers.append(PaperSummary(
                id=paper_id,
                title=title,
                summary=summary,
                year=year,
                citation_count=citation_count,
            ))

    def add_gaps(self, gaps: list[Any]) -> None:
        """Compress full gaps into title + summary."""
        self.gaps = []
        for g in gaps:
            gap_id = str(getattr(g, "id", ""))
            title = getattr(g, "title", "")
            description = getattr(g, "description", "") or ""
            confidence = getattr(g, "confidence", 0.5)
            gap_type = getattr(g, "gap_type", "")

            summary = _extract_first_sentence(description, max_chars=200)

            self.gaps.append(GapSummary(
                id=gap_id,
                title=title,
                summary=summary,
                confidence=confidence,
                gap_type=gap_type,
            ))

    def add_ideas(self, ideas: list[Any]) -> None:
        """Compress full ideas into title + summary."""
        self.ideas = []
        for idea in ideas:
            idea_id = str(getattr(idea, "id", ""))
            title = getattr(idea, "title", "")
            proposed_method = getattr(idea, "proposed_method", "") or ""
            score = getattr(idea, "score", 0.0)
            source_gap_ids = getattr(idea, "source_gap_ids", []) or []

            summary = _extract_first_sentence(proposed_method, max_chars=200)

            self.ideas.append(IdeaSummary(
                id=idea_id,
                title=title,
                summary=summary,
                score=score,
                source_gap_ids=source_gap_ids,
            ))

    def get_paper_summaries(self) -> list[dict]:
        """Get compressed paper dicts for LLM context."""
        return [p.to_dict() for p in self.papers]

    def get_gap_summaries(self) -> list[dict]:
        """Get compressed gap dicts for LLM context."""
        return [g.to_dict() for g in self.gaps]

    def get_idea_summaries(self) -> list[dict]:
        """Get compressed idea dicts for LLM context."""
        return [i.to_dict() for i in self.ideas]

    def format_for_prompt(self) -> str:
        """Format the CCW as a concise text block for LLM prompts."""
        lines = []
        if self.papers:
            lines.append(f"=== Papers ({len(self.papers)}) ===")
            for p in self.papers[:30]:  # Cap at 30
                lines.append(f"  [{p.id}] {p.title}")
                if p.summary:
                    lines.append(f"       {p.summary}")

        if self.gaps:
            lines.append(f"\n=== Gaps ({len(self.gaps)}) ===")
            for g in self.gaps:
                lines.append(f"  [{g.id}] {g.title} (conf={g.confidence:.2f})")
                if g.summary:
                    lines.append(f"       {g.summary}")

        if self.ideas:
            lines.append(f"\n=== Ideas ({len(self.ideas)}) ===")
            for i in self.ideas:
                lines.append(f"  [{i.id}] {i.title} (score={i.score:.2f})")
                if i.summary:
                    lines.append(f"       {i.summary}")

        return "\n".join(lines)

    def estimate_tokens(self) -> int:
        """Rough token estimate for the CCW content."""
        total_chars = 0
        for p in self.papers:
            total_chars += len(p.title) + len(p.summary)
        for g in self.gaps:
            total_chars += len(g.title) + len(g.summary)
        for i in self.ideas:
            total_chars += len(i.title) + len(i.summary)
        return total_chars // 4  # 4 chars per token

    def to_dict(self) -> dict:
        """Serialize the full CCW."""
        return {
            "papers": self.get_paper_summaries(),
            "gaps": self.get_gap_summaries(),
            "ideas": self.get_idea_summaries(),
            "estimated_tokens": self.estimate_tokens(),
        }


def _extract_first_sentence(text: str, max_chars: int = 200) -> str:
    """Extract the first meaningful sentence from text, truncated to max_chars.

    Prioritizes sentences that end with periods. Falls back to first
    max_chars if no period found.
    """
    if not text:
        return ""

    # Clean whitespace
    text = " ".join(text.split())

    # Find first sentence (ending with period followed by space or end)
    for i, char in enumerate(text):
        if char == "." and (i + 1 >= len(text) or text[i + 1] == " "):
            sentence = text[:i + 1]
            if len(sentence) <= max_chars:
                return sentence
            break

    # No period found or sentence too long — truncate at max_chars
    if len(text) <= max_chars:
        return text
    # Truncate at last space before max_chars
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space] + "..."
    return truncated + "..."
