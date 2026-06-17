"""Reference resolver — parse raw proposal references and match to Paper rows.

Lives in the domain/service layer (not the API layer).  API routes consume
this module; they do not own parsing logic.

Matching priority (most confident first):
  1. DOI exact match
  2. arXiv ID exact match
  3. Exact normalized title match
  4. High-threshold token-set similarity (≥ 0.8 Jaccard)

Every result includes ``match_method`` and ``match_confidence`` so callers
can surface provenance quality honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import Paper


# ---------------------------------------------------------------------------
# Regex patterns for parsing raw reference strings
# ---------------------------------------------------------------------------

# [1] or [2] etc.
_NUMBERED_PATTERN = re.compile(r"^\[(\d+)\]\s*")

# (2024) or (2024a) — year in parentheses
_YEAR_PATTERN = re.compile(r"\((\d{4}[a-z]?)\)")

# DOI
_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\)]+", re.IGNORECASE)

# arXiv ID (e.g., 2401.12345 or arXiv:2401.12345)
_ARXIV_PATTERN = re.compile(r"(?:arXiv:)?(\d{4}\.\d{4,5})", re.IGNORECASE)

# Authors — text before the year parenthesis
_AUTHORS_PATTERN = re.compile(r"^(.+?)\s*\(\d{4}")

# Title — text after year parenthesis, before period+space or end
_TITLE_PATTERN = re.compile(r"\)\.\s*(.+?)(?:\.\s|$)")


@dataclass
class StructuredReference:
    """Parsed reference with fields extracted from a raw string."""

    raw: str
    number: int | None = None
    authors: str | None = None
    year: str | None = None
    title: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None


@dataclass
class ResolvedReference:
    """A reference that may or may not be matched to a Paper row.

    Always preserves ``raw`` so no provenance data is lost, even when
    no match is found.
    """

    raw: str
    number: int | None = None
    authors: str | None = None
    year: str | None = None
    title: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    resolved: bool = False
    paper: dict[str, Any] | None = None
    match_method: str | None = None
    match_confidence: float = 0.0


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Normalize a title for matching: lowercase, strip punctuation, collapse spaces."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", title.lower())).strip()


def _token_set(text: str) -> set[str]:
    """Extract a set of lowercase word tokens from text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Conservative threshold: scientific titles are specific enough that
# legitimate matches should share most words.  Below 0.8 produces
# too many false positives (e.g., "attention mechanism" appears everywhere).
_TITLE_SIMILARITY_THRESHOLD = 0.8


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_reference(raw: str) -> StructuredReference:
    """Parse a raw reference string into structured fields.

    Handles common formats:
      [1] Smith et al. (2024). Attention Transfer. NeurIPS.
      Smith, J. and Jones, K. (2023). Cross-Domain Eval.
      [SOURCE-1] irrelevant — treated as raw only.

    Args:
        raw: The raw reference string from ``references_json``.

    Returns:
        StructuredReference with extracted fields (None where unparseable).
    """
    text = raw.strip()
    if not text:
        return StructuredReference(raw=raw)

    # Extract [N] numbered prefix
    number = None
    numbered_match = _NUMBERED_PATTERN.match(text)
    if numbered_match:
        number = int(numbered_match.group(1))
        text = text[numbered_match.end():]

    # DOI
    doi_match = _DOI_PATTERN.search(raw)
    doi = doi_match.group(0).rstrip(".") if doi_match else None

    # arXiv ID
    arxiv_match = _ARXIV_PATTERN.search(raw)
    arxiv_id = arxiv_match.group(1) if arxiv_match else None

    # Year
    year_match = _YEAR_PATTERN.search(text)
    year = year_match.group(1) if year_match else None

    # Authors — text before year parenthesis
    authors = None
    authors_match = _AUTHORS_PATTERN.match(text)
    if authors_match:
        authors = authors_match.group(1).strip().rstrip(",")

    # Title — text after ")." following the year
    title = None
    title_match = _TITLE_PATTERN.search(text)
    if title_match:
        title = title_match.group(1).strip()
        # Venue is often the text after the title period
        remaining = text[title_match.end():]
        venue = remaining.strip().rstrip(".") if remaining.strip() else None
    else:
        venue = None

    return StructuredReference(
        raw=raw,
        number=number,
        authors=authors,
        year=year,
        title=title,
        venue=venue,
        doi=doi,
        arxiv_id=arxiv_id,
    )


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _paper_to_dict(paper: Paper) -> dict[str, Any]:
    """Convert a Paper model to a serializable dict."""
    return {
        "id": paper.id,
        "title": paper.title,
        "year": paper.year,
        "venue": paper.venue,
        "citation_count": paper.citation_count,
        "doi": paper.doi,
        "arxiv_id": paper.arxiv_id,
        "url": paper.url,
    }


def resolve_reference(
    ref: StructuredReference,
    papers: Sequence[Paper],
) -> tuple[Paper | None, str | None, float]:
    """Try to match a parsed reference to a Paper row.

    Returns:
        (matched_paper, match_method, confidence) or (None, None, 0.0).
    """
    # 1. DOI exact match — highest confidence
    if ref.doi:
        for p in papers:
            if p.doi and p.doi.lower() == ref.doi.lower():
                return p, "doi", 1.0

    # 2. arXiv ID exact match
    if ref.arxiv_id:
        for p in papers:
            if p.arxiv_id and p.arxiv_id.lower() == ref.arxiv_id.lower():
                return p, "arxiv", 1.0

    # 3. Exact normalized title match
    if ref.title:
        ref_norm = _normalize_title(ref.title)
        for p in papers:
            if _normalize_title(p.title) == ref_norm:
                return p, "title_exact", 0.95

        # 4. High-threshold token similarity
        ref_tokens = _token_set(ref.title)
        best_match: Paper | None = None
        best_score = 0.0
        for p in papers:
            paper_tokens = _token_set(p.title)
            score = _jaccard(ref_tokens, paper_tokens)
            if score > best_score:
                best_score = score
                best_match = p

        if best_match and best_score >= _TITLE_SIMILARITY_THRESHOLD:
            return best_match, "title_fuzzy", best_score

    # 5. Author + year match (weaker — only as tiebreaker on title)
    if ref.authors and ref.year:
        ref_surname = ref.authors.split(",")[0].split()[-1].lower()
        for p in papers:
            if p.year and str(p.year) == ref.year:
                # Check if surname appears in paper authors JSON
                if ref_surname and ref_surname in (p.authors or "").lower():
                    return p, "author_year", 0.7

    return None, None, 0.0


def resolve_references(
    refs: list[dict[str, str]] | str | None,
    session: Session,
    pipeline_run_id: int | None = None,
) -> list[ResolvedReference]:
    """Resolve raw references against Paper rows in the DB.

    Args:
        refs: Raw references — either a list of ``{"raw": "..."}`` dicts,
            a raw string, or None.
        session: SQLAlchemy session.
        pipeline_run_id: Restrict paper lookup to this run when possible.
            Falls back to all papers if no papers are found for the run.

    Returns:
        List of ResolvedReference objects.  Always preserves ``raw``.
    """
    if not refs:
        return []

    # Normalize input to a list of raw strings
    if isinstance(refs, str):
        raw_strings = [line.strip() for line in refs.split("\n") if line.strip()]
    elif isinstance(refs, list):
        raw_strings = [
            r.get("raw", str(r)) if isinstance(r, dict) else str(r)
            for r in refs
        ]
    else:
        return []

    if not raw_strings:
        return []

    # Fetch candidate papers — prefer same run
    # Papers are not directly linked to runs, so we fetch all and filter
    # if needed.  For most deployments the corpus is manageable.
    all_papers = session.execute(select(Paper)).scalars().all()

    results: list[ResolvedReference] = []
    for raw in raw_strings:
        parsed = parse_reference(raw)
        matched_paper, method, confidence = resolve_reference(parsed, all_papers)

        results.append(ResolvedReference(
            raw=raw,
            number=parsed.number,
            authors=parsed.authors,
            year=parsed.year,
            title=parsed.title,
            venue=parsed.venue,
            doi=parsed.doi,
            arxiv_id=parsed.arxiv_id,
            resolved=matched_paper is not None,
            paper=_paper_to_dict(matched_paper) if matched_paper else None,
            match_method=method,
            match_confidence=confidence,
        ))

    return results
