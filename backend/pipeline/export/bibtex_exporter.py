"""BibTeX export for papers and proposals.

Converts Paper objects and proposal metadata to BibTeX format.
"""
from __future__ import annotations

import re
import logging
from typing import Any

from backend.pipeline.constants import AI_HONESTY_BADGE_BRIEF
from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)


def paper_to_bibtex(paper: Paper) -> str:
    """Convert a Paper to a BibTeX entry.

    Generates an @article entry with title, authors, year, etc.
    """
    # Generate citation key
    key = _generate_key(paper)

    # Build entry
    lines = [f"@article{{{key},"]

    if paper.title:
        lines.append(f"  title = {{{paper.title}}},")
    if paper.authors:
        author_str = " and ".join(a.name for a in paper.authors)
        lines.append(f"  author = {{{author_str}}},")
    if paper.year:
        lines.append(f"  year = {{{paper.year}}},")
    if paper.venue:
        lines.append(f"  journal = {{{paper.venue}}},")
    if paper.doi:
        lines.append(f"  doi = {{{paper.doi}}},")
    if paper.url:
        lines.append(f"  url = {{{paper.url}}},")
    if paper.abstract:
        # Truncate very long abstracts
        abstract = paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract
        lines.append(f"  abstract = {{{abstract}}},")
    if paper.source:
        lines.append(f"  note = {{Retrieved from {paper.source}}},")

    lines.append("}")
    return "\n".join(lines)


def papers_to_bibtex(papers: list[Paper]) -> str:
    """Convert multiple papers to a BibTeX file."""
    entries = [paper_to_bibtex(p) for p in papers]
    return "\n\n".join(entries)


def proposal_to_bibtex(
    title: str,
    domain: str = "",
    year: int | None = None,
) -> str:
    """Generate a BibTeX entry for a generated proposal."""
    key = f"elephant_rock_{domain.lower().replace(' ', '_')[:20]}"

    lines = [f"@misc{{{key},"]
    lines.append(f"  title = {{{title}}},")
    lines.append(f"  author = {{Elephant Rock Research Platform}},")
    if year:
        lines.append(f"  year = {{{year}}},")
    if domain:
        lines.append(f"  note = {{Research proposal for domain: {domain}}},")
    lines.append("  howpublished = {{Elephant Rock AI Research Platform}},")
    lines.append(f"  note = {{{{AI-generated proposal. {AI_HONESTY_BADGE_BRIEF}}}}},")
    lines.append("}")
    return "\n".join(lines)


def _generate_key(paper: Paper) -> str:
    """Generate a BibTeX citation key from paper metadata."""
    parts = []
    if paper.authors:
        first_author = paper.authors[0].name.split()[-1] if paper.authors else "unknown"
        parts.append(first_author.lower())
    if paper.year:
        parts.append(str(paper.year))
    if paper.title:
        # Use first meaningful word from title
        words = re.findall(r"[a-zA-Z]+", paper.title)
        meaningful = [w for w in words if len(w) > 3][:2]
        parts.extend(w.lower() for w in meaningful)

    return "_".join(parts) if parts else f"paper_{hash(paper.title) % 10000}"
