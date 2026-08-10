"""Phase 1 1F: Full-paper export routes.

Exports the persisted full-paper artifact (Phase 1 1C) for a single idea as
Markdown, LaTeX, or BibTeX. Operates on the FINAL PAPER, never on proposal
text. Reuses existing exporters where they accept paper-shaped input.

Routes (mounted under /api/v1/export/paper):
  GET  /markdown/{idea_id}
  GET  /latex/{idea_id}
  GET  /bibtex/{idea_id}

Truth rules (WP-1F):
  - operate on the selected final paper only,
  - return non-empty content,
  - use a stable filename,
  - fail explicitly (404) when the paper is absent,
  - never export proposal text under a paper filename.
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

# Prefix is relative; the app mounts this router under /api/v1/export so the
# final paths are /api/v1/export/paper/{markdown,latex,bibtex}/{idea_id},
# consistent with the rest of the API and reachable by the frontend
# apiFetchBlob helper (which prepends /api/v1).
router = APIRouter(prefix="/paper", tags=["export"])


def _load_paper(idea_id: int):
    """Load the persisted paper for an idea. Returns (proposal, idea) or
    (None, None) when no proposal/paper exists. Raises nothing."""
    from sqlalchemy import select

    from backend.db.database import get_session
    from backend.db.models import Idea, Proposal

    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            return None, None
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        if proposal is None:
            return None, idea
        paper_md = getattr(proposal, "paper_md", None)
        if not paper_md or not paper_md.strip():
            return None, idea
        return proposal, idea


def _load_frozen_paper(idea_id: int):
    """Load the release-final immutable PaperRevision for an idea."""
    from sqlalchemy import select

    from backend.db.database import get_session
    from backend.db.models import Idea, Proposal
    from backend.pipeline.evaluation.paper_release import (
        PaperReleaseError,
        load_frozen_revision,
    )

    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if idea is None:
            return None, None, None
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        if proposal is None:
            return None, idea, None
        try:
            revision = load_frozen_revision(session, proposal)
        except PaperReleaseError:
            return proposal, idea, None
        # expire_on_commit/session-close safe: materialize fields the route uses.
        revision.paper_md
        revision.paper_hash
        revision.id
        revision.revision_number
        return proposal, idea, revision


def _meta(proposal) -> dict:
    raw = getattr(proposal, "paper_meta_json", None)
    if not raw:
        return {}
    try:
        return json.loads(raw) or {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _render_bibliography_for_proposal(proposal) -> str:
    """Phase 4 / WP-4C — render the Markdown references section from the
    persisted citation map. Returns '' when no map exists (legacy/failed
    papers) so the exporter is a no-op rather than fabricating sources."""
    from backend.db.database import get_session
    from backend.pipeline.provenance.citation_map import (
        load_citation_map,
        render_bibliography_markdown,
    )

    proposal_id = getattr(proposal, "id", None)
    if proposal_id is None:
        return ""
    with get_session() as session:
        entries = load_citation_map(session, proposal_id)
        return render_bibliography_markdown(entries)


def _load_citation_map_entries(proposal_id: int):
    """Load citation-map entries for a proposal (for BibTeX rendering)."""
    from backend.db.database import get_session
    from backend.pipeline.provenance.citation_map import load_citation_map

    with get_session() as session:
        return load_citation_map(session, proposal_id)


def _stable_filename(title: str | None, idea_id: int, ext: str) -> str:
    """Stable, filesystem-safe filename derived from the paper title."""
    base = "paper"
    if title:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if slug:
            base = slug[:60]
    return f"{base}--idea-{idea_id}.{ext}"


@router.get("/markdown/{idea_id}", response_class=PlainTextResponse)
async def export_paper_markdown(idea_id: int):
    """Export the final paper for an idea as Markdown."""
    proposal, idea = _load_paper(idea_id)
    if proposal is None:
        return PlainTextResponse(
            "# Paper not available for this idea. The paper may not have been "
            "generated yet (run a deep_research or academic_proposal strategy) "
            "or synthesis failed.",
            status_code=404,
        )
    paper_md = proposal.paper_md
    # Phase 4 / WP-4C: append a bibliography rendered from the persisted
    # citation map (replaces the Phase 3 zero-bibliography defect).
    bibliography = _render_bibliography_for_proposal(proposal)
    if bibliography:
        paper_md = paper_md.rstrip() + "\n" + bibliography + "\n"
    fname = _stable_filename(getattr(idea, "title", None), idea_id, "md")
    return PlainTextResponse(
        paper_md,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/release/markdown/{idea_id}", response_class=PlainTextResponse)
async def export_release_paper_markdown(idea_id: int):
    """Export the exact frozen release-final Markdown revision.

    Unlike ordinary paper export, this returns the immutable frozen paper
    byte-for-byte (no bibliography append) so the response hash identifies the
    exact released scientific content.
    """
    proposal, idea, revision = _load_frozen_paper(idea_id)
    if revision is None:
        return PlainTextResponse(
            "# Release-final paper not available for this idea.",
            status_code=404,
        )
    fname = _stable_filename(getattr(idea, "title", None), idea_id, "md")
    if fname.endswith(".md"):
        fname = fname[:-3] + "--release.md"
    return PlainTextResponse(
        revision.paper_md,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{fname}"',
            "X-ERLab-Paper-Hash": revision.paper_hash,
            "X-ERLab-Revision-Id": str(revision.id),
            "X-ERLab-Revision-Number": str(revision.revision_number),
        },
    )


@router.get("/latex/{idea_id}", response_class=PlainTextResponse)
async def export_paper_latex(idea_id: int):
    """Export the final paper for an idea as LaTeX.

    Renders the paper markdown into a minimal LaTeX document. The existing
    LatexExporter operates on ResearchProposal section structures, which the
    paper artifact is not; rather than fabricate a proposal, we wrap the paper
    markdown in a verbatim-friendly article shell so the export is honest about
    what it contains (the synthesized paper text).
    """
    proposal, idea = _load_paper(idea_id)
    if proposal is None:
        return PlainTextResponse(
            "% Paper not available for this idea.",
            status_code=404,
        )
    paper_md = proposal.paper_md
    title = getattr(idea, "title", "Untitled Paper")
    # Phase 4 / WP-4C: append a bibliography rendered from the persisted
    # citation map. Rendered as Markdown then escaped (same minimal escape
    # as the body) so the LaTeX stays compilable and honest about contents.
    bibliography_md = _render_bibliography_for_proposal(proposal)
    if bibliography_md:
        paper_md = paper_md.rstrip() + "\n" + bibliography_md + "\n"
    # Escape a minimal set of LaTeX-special characters in the body to keep the
    # output compilable. This is intentionally minimal — the paper is already
    # markdown; full markdown->latex conversion is out of Phase 1 scope.
    body = paper_md.replace("\\", "\\textbackslash{}").replace("&", "\\&").replace("%", "\\%").replace("#", "\\#")
    latex = (
        "\\documentclass{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\title{" + title.replace("_", "\\_") + "}\n"
        "\\date{}\n"
        "\\begin{document}\n"
        "\\maketitle\n"
        + body
        + "\n\\end{document}\n"
    )
    fname = _stable_filename(title, idea_id, "tex")
    return PlainTextResponse(
        latex,
        media_type="text/x-latex",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/bibtex/{idea_id}", response_class=PlainTextResponse)
async def export_paper_bibtex(idea_id: int):
    """Export the final paper's references as BibTeX.

    The synthesized paper cites source literature via [SOURCE-N] markers and
    the proposal carries resolved references. We emit a BibTeX entry for the
    paper itself (so it can be cited) plus entries for the resolved reference
    set when available. Reuses proposal_to_bibtex-style emission (no new
    bibliography generator).
    """
    from sqlalchemy import select

    from backend.db.database import get_session
    from backend.db.models import Proposal

    with get_session() as session:
        proposal = session.execute(
            select(Proposal).where(Proposal.idea_id == idea_id).limit(1)
        ).scalar_one_or_none()
        if proposal is None or not (
            getattr(proposal, "paper_md", None) or ""
        ).strip():
            return PlainTextResponse(
                "% Paper not available for this idea.",
                status_code=404,
            )
        title = None
        meta = _meta(proposal)
        from backend.db.models import Idea

        idea = session.get(Idea, idea_id)
        title = getattr(idea, "title", "Untitled Paper") if idea else "Untitled Paper"

        entries: list[str] = []
        # Entry for the paper itself.
        cite_key = f"erlab_paper_idea{idea_id}"
        entries.append(
            "@misc{"
            + cite_key
            + ",\n"
            + f"  title = {{{title}}},\n"
            + "  author = {{Elephant Rock Research Platform}},\n"
            + "  note = {Full research paper generated by the Elephant Rock pipeline},\n"
            + "}\n"
        )
        # Phase 4 / WP-4C: emit BibTeX entries for the cited external sources
        # from the persisted marker→source map. This replaces the Phase 3
        # behavior where BibTeX contained only the self-citation above.
        from backend.pipeline.provenance.citation_map import render_bibliography_bibtex

        proposal_id = getattr(proposal, "id", None)
        if proposal_id is not None:
            cm_entries = _load_citation_map_entries(proposal_id)
            entries.extend(
                render_bibliography_bibtex(cm_entries, key_prefix=f"erlab_paper_idea{idea_id}")
            )
        # Resolved references, when present on the proposal (legacy fallback).
        refs_raw = getattr(proposal, "references_json", None)
        if refs_raw:
            try:
                refs = json.loads(refs_raw)
            except (json.JSONDecodeError, TypeError):
                refs = []
            if isinstance(refs, list):
                for i, ref in enumerate(refs, 1):
                    if not isinstance(ref, dict):
                        continue
                    rt = ref.get("title") or ref.get("citation") or f"Reference {i}"
                    ra = ref.get("authors") or ref.get("author")
                    ry = ref.get("year")
                    rven = ref.get("venue") or ref.get("journal")
                    rk = ref.get("doi") or ref.get("url")
                    fields = [f"  title = {{{rt}}}"]
                    if ra:
                        fields.append(f"  author = {{{ra}}}")
                    if ry:
                        fields.append(f"  year = {{{ry}}}")
                    if rven:
                        fields.append(f"  journal = {{{rven}}}")
                    if rk:
                        fields.append(f"  doi = {{{rk}}}")
                    entries.append("@article{erlab_ref_" + f"{idea_id}_{i}" + ",\n" + ",\n".join(fields) + ",\n}\n")

        fname = _stable_filename(title, idea_id, "bib")
        return PlainTextResponse(
            "\n".join(entries),
            media_type="application/x-bibtex",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
