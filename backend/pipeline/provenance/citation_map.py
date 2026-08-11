"""Phase 4 / WP-4C — citation-map reader: the single read-path for consumers.

Exports (Markdown/LaTeX/BibTeX) and Trust & Sources must all consume the SAME
persisted marker→source map (``paper_source_markers``). This module loads that
map for a proposal and exposes resolved bibliographic identity per marker, so
every consumer renders the same source list instead of re-deriving different
ones from the LLM-generated ``references_json`` (the Phase 3 defect).

Truth rules:
  * A mapped marker carries its resolved ``Paper`` row (DOI/arXiv/title/...).
  * An unmapped marker carries ``source_paper=None`` — identity is NEVER guessed.
  * An empty list is returned when no markers exist (consumer falls back
    gracefully rather than fabricating entries).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.db.models import Paper, PaperSourceMarker


@dataclass
class CitationMapEntry:
    """One row of the persisted marker→source map, with resolved identity."""

    marker_index: int
    marker: str
    source_paper_id: int | None
    mapping_status: str  # "mapped" | "unmapped"
    source_paper: Paper | None


def load_citation_map(session: Session, proposal_id: int) -> list[CitationMapEntry]:
    """Load the marker→source map for a proposal, ordered by marker_index.

    Each entry's ``source_paper`` is loaded so callers read bibliographic
    identity (DOI/arXiv/title/authors/year/venue/url) without a second query.

    Returns an empty list when the proposal has no persisted markers (e.g. a
    paper generated before the Phase 4 manifest existed, or a failed paper).
    Consumers should treat an empty map as "no provenance available" rather
    than synthesizing a different source list.
    """
    from backend.db import crud

    rows: list[PaperSourceMarker] = crud.get_source_markers_for_proposal(
        session, proposal_id
    )
    return [
        CitationMapEntry(
            marker_index=row.marker_index,
            marker=row.marker,
            source_paper_id=row.source_paper_id,
            mapping_status=row.mapping_status,
            source_paper=row.source_paper,
        )
        for row in rows
    ]


def _author_list(paper) -> list[str]:
    """Parse the JSON-encoded authors column on a Paper row into a name list."""
    import json

    raw = getattr(paper, "authors", None)
    if not raw:
        return []
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(parsed, list):
        return [str(a) for a in parsed]
    return []


def render_bibliography_markdown(entries: list[CitationMapEntry]) -> str:
    """Render a Markdown references section from the citation map.

    Only mapped entries with a resolved source paper are rendered as full
    citations; unmapped markers are listed explicitly so the reader can see
    which citations have no recoverable source (truth rule: never silently
    drop, never guess).
    """
    if not entries:
        return ""
    lines = ["", "## References", ""]
    for e in entries:
        p = e.source_paper
        if p is not None:
            authors = _author_list(p)
            author_str = ", ".join(authors) if authors else "Unknown"
            year = getattr(p, "year", None) or "n.d."
            title = getattr(p, "title", "Untitled") or "Untitled"
            venue = getattr(p, "venue", None) or ""
            venue_str = f" *{venue}.*" if venue else ""
            doi = getattr(p, "doi", None)
            arxiv = getattr(p, "arxiv_id", None)
            url = getattr(p, "url", None)
            extras = []
            if doi:
                extras.append(f"DOI: {doi}")
            if arxiv:
                extras.append(f"arXiv: {arxiv}")
            elif url:
                extras.append(f"URL: {url}")
            extras_str = f" ({'; '.join(extras)})" if extras else ""
            lines.append(
                f"- [{e.marker}] {author_str} ({year}). *{title}.*{venue_str}{extras_str}"
            )
        else:
            lines.append(f"- [{e.marker}] *Citation marker has no recoverable source (unmapped).*")
    return "\n".join(lines)


def render_bibliography_bibtex(
    entries: list[CitationMapEntry], key_prefix: str
) -> list[str]:
    """Render BibTeX @article entries for mapped sources from the citation map.

    Returns one BibTeX entry string per mapped entry (unmapped markers are
    omitted from BibTeX — they have no citable identity). Each entry's cite key
    is deterministic: ``{key_prefix}_source_{marker_index}``.
    """
    out: list[str] = []
    for e in entries:
        p = e.source_paper
        if p is None:
            continue
        authors = _author_list(p)
        author_str = " and ".join(authors) if authors else "Unknown"
        fields = [f"  title = {{{getattr(p, 'title', 'Untitled') or 'Untitled'}}}"]
        fields.append(f"  author = {{{author_str}}}")
        if getattr(p, "year", None):
            fields.append(f"  year = {{{p.year}}}")
        if getattr(p, "venue", None):
            fields.append(f"  journal = {{{p.venue}}}")
        if getattr(p, "doi", None):
            fields.append(f"  doi = {{{p.doi}}}")
        elif getattr(p, "arxiv_id", None):
            fields.append(f"  eprint = {{{p.arxiv_id}}}")
        elif getattr(p, "url", None):
            fields.append(f"  url = {{{p.url}}}")
        cite_key = f"{key_prefix}_source_{e.marker_index}"
        out.append(f"@article{{{cite_key},\n" + ",\n".join(fields) + ",\n}\n")
    return out

