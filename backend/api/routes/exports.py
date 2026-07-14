"""Export API routes — PDF export and bulk ZIP export."""

import io
import json
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.api.errors import NotFoundError
from backend.api.schemas import ExportPdfRequest, BulkExportRequest
from starlette.responses import PlainTextResponse

router = APIRouter()


def _render_quarantined_sections(sections: dict | None, proposal_id: int | None) -> dict | None:
    """STOPGAP: apply quarantine redaction to parsed sections for export.

    Returns the input unchanged on any error or when no quarantine rows exist
    (fail-soft). Mirrors ideas._load_quarantine_rows + render_quarantined_view.
    """
    if not sections or proposal_id is None:
        return sections
    try:
        from sqlalchemy import select

        from backend.db.database import get_session
        from backend.db.models import QuarantinedCitation
        from backend.pipeline.quarantine import render_quarantined_view

        with get_session() as session:
            qrows = list(session.execute(
                select(QuarantinedCitation).where(
                    QuarantinedCitation.proposal_id == proposal_id
                )
            ).scalars().all())
            if qrows:
                return render_quarantined_view(sections, qrows)
    except Exception:
        pass
    return sections


def _idea_to_html(idea: dict, proposal_md: str | None) -> str:
    """Render an idea as a simple HTML document for PDF conversion."""
    title = idea.get("title", "Untitled Idea")
    domain = idea.get("domain", "N/A")
    problem = idea.get("problem_statement", "")
    method = idea.get("proposed_method", "")
    contributions = idea.get("expected_contributions", "")
    novelty = idea.get("novelty_score")
    feasibility = idea.get("feasibility_score")
    overall = idea.get("overall_score")
    created = idea.get("created_at", "")

    scores_html = ""
    if novelty is not None or feasibility is not None or overall is not None:
        scores_html = "<h2>Scores</h2><table border='1' cellpadding='6' cellspacing='0'>"
        if novelty is not None:
            scores_html += f"<tr><td><strong>Novelty</strong></td><td>{novelty:.2f}</td></tr>"
        if feasibility is not None:
            scores_html += f"<tr><td><strong>Feasibility</strong></td><td>{feasibility:.2f}</td></tr>"
        if overall is not None:
            scores_html += f"<tr><td><strong>Overall</strong></td><td>{overall:.2f}</td></tr>"
        scores_html += "</table>"

    proposal_html = ""
    if proposal_md:
        try:
            import markdown as md_lib
            proposal_html = f"<h2>Proposal</h2>{md_lib.markdown(proposal_md)}"
        except ImportError:
            proposal_html = f"<h2>Proposal</h2><pre>{proposal_md}</pre>"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; color: #222; }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #333; padding-bottom: 8px; }}
  h2 {{ font-size: 18px; margin-top: 24px; color: #444; }}
  .meta {{ color: #666; font-size: 14px; margin-bottom: 16px; }}
  table {{ border-collapse: collapse; margin: 8px 0; }}
  td {{ padding: 4px 12px; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="meta">Domain: {domain} &middot; Created: {created}</p>
<h2>Problem Statement</h2>
<p>{problem}</p>
<h2>Proposed Method</h2>
<p>{method}</p>
<h2>Expected Contributions</h2>
<p>{contributions}</p>
{scores_html}
{proposal_html}
</body>
</html>"""


@router.post(
    "/pdf",
    summary="Export idea as PDF",
    description="Generate a PDF document for a single research idea using WeasyPrint HTML-to-PDF conversion.",
)
async def export_pdf(request: ExportPdfRequest):
    """Export a single idea as PDF.

    Args:
        request: Contains idea_id to export.

    Returns:
        PDF file as application/pdf streaming response.
    """
    from backend.db.crud import get_idea as db_get_idea, get_proposal_by_idea
    from backend.db.database import get_session

    with get_session() as session:
        idea = db_get_idea(session, request.idea_id)
        if not idea:
            raise NotFoundError("Idea not found")

        proposal = get_proposal_by_idea(session, idea.id)
        proposal_md = proposal.content_md if proposal else None

        idea_data = {
            "title": idea.title,
            "domain": idea.domain,
            "problem_statement": idea.problem_statement,
            "proposed_method": idea.proposed_method,
            "expected_contributions": idea.expected_contributions,
            "novelty_score": idea.novelty_score,
            "feasibility_score": idea.feasibility_score,
            "overall_score": idea.overall_score,
            "created_at": str(idea.created_at),
        }

    html = _idea_to_html(idea_data, proposal_md)

    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html).write_pdf()
    except Exception:
        # Fallback: return HTML if WeasyPrint unavailable
        pdf_bytes = html.encode("utf-8")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename=idea_{request.idea_id}.html"
            },
        )

    safe_title = idea_data["title"].replace(" ", "_")[:50]
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={safe_title}.pdf"
        },
    )


@router.post(
    "/bulk",
    summary="Bulk export ideas as ZIP",
    description="Export multiple ideas as a ZIP archive containing individual PDF files or Markdown files.",
)
async def bulk_export(request: BulkExportRequest):
    """Bulk export ideas as a ZIP archive.

    Args:
        request: Contains idea_ids list and optional format (pdf/markdown).

    Returns:
        ZIP archive as application/zip streaming response.
    """
    from backend.db.crud import get_idea as db_get_idea, get_proposal_by_idea
    from backend.db.database import get_session

    export_format = request.format or "markdown"
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        with get_session() as session:
            for idea_id in request.idea_ids:
                idea = db_get_idea(session, idea_id)
                if not idea:
                    continue

                proposal = get_proposal_by_idea(session, idea.id)
                proposal_md = proposal.content_md if proposal else None
                safe_title = idea.title.replace(" ", "_")[:50]

                if export_format == "pdf":
                    idea_data = {
                        "title": idea.title,
                        "domain": idea.domain,
                        "problem_statement": idea.problem_statement,
                        "proposed_method": idea.proposed_method,
                        "expected_contributions": idea.expected_contributions,
                        "novelty_score": idea.novelty_score,
                        "feasibility_score": idea.feasibility_score,
                        "overall_score": idea.overall_score,
                        "created_at": str(idea.created_at),
                    }
                    html = _idea_to_html(idea_data, proposal_md)
                    try:
                        from weasyprint import HTML

                        pdf_bytes = HTML(string=html).write_pdf()
                        zf.writestr(f"{safe_title}.pdf", pdf_bytes)
                    except Exception:
                        zf.writestr(f"{safe_title}.html", html.encode("utf-8"))
                else:
                    # Markdown export
                    md_content = f"# {idea.title}\n\n"
                    md_content += f"**Domain:** {idea.domain}\n\n"
                    md_content += f"## Problem Statement\n\n{idea.problem_statement}\n\n"
                    md_content += f"## Proposed Method\n\n{idea.proposed_method}\n\n"
                    md_content += f"## Expected Contributions\n\n{idea.expected_contributions}\n\n"
                    if idea.novelty_score is not None:
                        md_content += f"- **Novelty Score:** {idea.novelty_score:.2f}\n"
                    if idea.feasibility_score is not None:
                        md_content += f"- **Feasibility Score:** {idea.feasibility_score:.2f}\n"
                    if idea.overall_score is not None:
                        md_content += f"- **Overall Score:** {idea.overall_score:.2f}\n"
                    if proposal_md:
                        md_content += f"\n## Proposal\n\n{proposal_md}\n"

                    # Review Summary + Quality Checks
                    from backend.api.quality_checks import compute_quality_checks as _qc
                    _sections_json = (
                        json.loads(proposal.sections_json)
                        if proposal and proposal.sections_json
                        else None
                    )
                    _sections_json = _render_quarantined_sections(
                        _sections_json, getattr(proposal, "id", None)
                    )
                    if _sections_json and isinstance(_sections_json.get("ensemble_review"), dict):
                        rv = _sections_json["ensemble_review"]
                        md_content += "\n## Proposal Review\n\n"
                        if rv.get("overall_score") is not None:
                            md_content += f"**Overall Score:** {rv['overall_score']:.0%}\n\n"
                        if rv.get("summary"):
                            md_content += f"{rv['summary']}\n\n"
                        if rv.get("consensus_strengths"):
                            md_content += "**Strengths:**\n\n"
                            for s in rv["consensus_strengths"]:
                                md_content += f"- {s}\n"
                            md_content += "\n"
                        if rv.get("critical_weaknesses"):
                            md_content += "**Weaknesses:**\n\n"
                            for w in rv["critical_weaknesses"]:
                                md_content += f"- {w}\n"
                            md_content += "\n"
                        if rv.get("actionable_suggestions"):
                            md_content += "**Suggestions:**\n\n"
                            for s in rv["actionable_suggestions"]:
                                md_content += f"- {s}\n"
                            md_content += "\n"

                    _qc_result = _qc(_sections_json)
                    if _qc_result:
                        _passed = sum(1 for c in _qc_result if c["passed"])
                        _total = len(_qc_result)
                        md_content += f"\n## Quality Checks ({_passed}/{_total} sections passed)\n\n"
                        for c in _qc_result:
                            if c["present"]:
                                mark = "\u2705" if c["passed"] else "\u274c"
                                wc_note = f" ({c['word_count']}/{c['min_words']} words)" if not c["meets_word_count"] else ""
                                fail_note = f" \u2014 {'; '.join(c['failures'])}" if c["failures"] else ""
                                md_content += f"- {mark} {c['label']}{wc_note}{fail_note}\n"
                            else:
                                md_content += f"- \u26a0\ufe0f {c['label']} (missing)\n"
                        md_content += "\n"

                    # Evidence Trace (Phase C)
                    from backend.api.traceability import (
                        resolve_source_gaps as _resolve,
                        extract_proposal_references as _extract_refs,
                    )
                    from backend.pipeline.provenance.reference_resolver import resolve_references as _resolve_refs
                    from backend.db.models import IdeaPaperLink as _IPL, Paper as _PaperModel
                    from sqlalchemy import select as _sel

                    try:
                        raw_gids = json.loads(idea.source_gap_ids) if idea.source_gap_ids else []
                    except (json.JSONDecodeError, TypeError):
                        raw_gids = []
                    sg_list = _resolve(session, raw_gids, idea.pipeline_run_id)

                    # Supporting papers via junction table
                    _bulk_links = session.execute(
                        _sel(_IPL).where(_IPL.idea_id == idea.id)
                    ).scalars().all()
                    _bulk_papers = []
                    for _link in _bulk_links:
                        _bp = session.get(_PaperModel, _link.paper_id)
                        if _bp:
                            _bulk_papers.append((_bp, _link.role))

                    # Structured references
                    _bulk_raw_refs = _extract_refs(proposal) if proposal else None
                    _bulk_resolved = (
                        _resolve_refs(_bulk_raw_refs, session, idea.pipeline_run_id)
                        if _bulk_raw_refs else []
                    )

                    if sg_list or _bulk_papers or _bulk_resolved:
                        md_content += "\n## Evidence Trace\n\n"

                        if _bulk_papers:
                            md_content += "**Supporting Papers:**\n\n"
                            for _bp, _brole in _bulk_papers:
                                _pline = f"- {_bp.title}"
                                if _bp.year:
                                    _pline += f" ({_bp.year})"
                                if _bp.venue:
                                    _pline += f". {_bp.venue}"
                                _pline += f" [{_brole}]\n"
                                md_content += _pline
                            md_content += "\n"

                        if sg_list:
                            md_content += "**Source Research Gaps:**\n\n"
                            for sg in sg_list:
                                if sg["resolved"]:
                                    md_content += (
                                        f"- [{sg['gap_type']}] {sg['title']} "
                                        f"({sg['confidence']:.0%} confidence)\n"
                                    )
                                else:
                                    md_content += f"- [unresolved] {sg['raw']}\n"
                            md_content += "\n"

                        if _bulk_resolved:
                            md_content += "**Proposal References:**\n\n"
                            for _br in _bulk_resolved:
                                _bmark = "\u2705" if _br.resolved else "\u2753"
                                _bline = f"- {_bmark} {_br.title or _br.raw}"
                                if _br.resolved and _br.paper:
                                    _bline += f" \u2192 matched: \"{_br.paper.get('title', '')}\""
                                    _bline += f" [{_br.match_method}, {round(_br.match_confidence * 100)}%]"
                                elif not _br.resolved:
                                    _bline += " [unresolved]"
                                md_content += f"{_bline}\n"
                            md_content += "\n"

                    zf.writestr(f"{safe_title}.md", md_content.encode("utf-8"))

    buffer.seek(0)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=ideas_export_{timestamp}.zip"
        },
    )


@router.get(
    "/markdown/{run_id}",
    summary="Export run proposals as Markdown",
    response_class=PlainTextResponse,
)
async def export_run_markdown(run_id: int):
    """Export a pipeline run's proposals as Markdown."""
    from backend.db.database import get_session
    from backend.db.crud import get_ideas_for_run, get_proposal_by_idea
    from backend.api.traceability import resolve_source_gaps, extract_proposal_references
    from backend.api.quality_checks import compute_quality_checks
    from backend.pipeline.provenance.reference_resolver import resolve_references
    from backend.db.models import IdeaPaperLink, Paper as PaperModel

    try:
        with get_session() as session:
            ideas = get_ideas_for_run(session, run_id)
            if not ideas:
                return PlainTextResponse("# No ideas found for this run.", status_code=404)

            sections = [f"# Research Proposals — Run {run_id}\n"]
            for i, idea in enumerate(ideas, 1):
                proposal = get_proposal_by_idea(session, idea.id)
                title = getattr(idea, "title", f"Idea {i}")
                content = getattr(proposal, "content_md", "") if proposal else ""
                sections.append(f"## {i}. {title}\n\n{content}\n")

                # Review Summary (if ensemble review exists in persisted sections)
                sections_json = (
                    json.loads(proposal.sections_json)
                    if proposal and proposal.sections_json
                    else None
                )
                sections_json = _render_quarantined_sections(
                    sections_json, getattr(proposal, "id", None)
                )
                if sections_json and isinstance(sections_json.get("ensemble_review"), dict):
                    rv = sections_json["ensemble_review"]
                    sections.append("### Proposal Review\n")
                    if rv.get("overall_score") is not None:
                        sections.append(f"**Overall Score:** {rv['overall_score']:.0%}\n")
                    if rv.get("summary"):
                        sections.append(f"{rv['summary']}\n")
                    if rv.get("consensus_strengths"):
                        sections.append("**Strengths:**\n")
                        for s in rv["consensus_strengths"]:
                            sections.append(f"- {s}\n")
                    if rv.get("critical_weaknesses"):
                        sections.append("**Weaknesses:**\n")
                        for w in rv["critical_weaknesses"]:
                            sections.append(f"- {w}\n")
                    if rv.get("actionable_suggestions"):
                        sections.append("**Suggestions:**\n")
                        for s in rv["actionable_suggestions"]:
                            sections.append(f"- {s}\n")
                    sections.append("")

                # Quality Checks (deterministic, computed at export time)
                qc = compute_quality_checks(sections_json)
                if qc:
                    passed = sum(1 for c in qc if c["passed"])
                    total = len(qc)
                    sections.append(f"### Quality Checks ({passed}/{total} sections passed)\n")
                    for c in qc:
                        mark = "\u2705" if c["passed"] else "\u274c"
                        wc_note = f" ({c['word_count']}/{c['min_words']} words)" if not c["meets_word_count"] else ""
                        fail_note = f" — {'; '.join(c['failures'])}" if c["failures"] else ""
                        if c["present"]:
                            sections.append(f"- {mark} {c['label']}{wc_note}{fail_note}\n")
                        else:
                            sections.append(f"- \u26a0\ufe0f {c['label']} (missing)\n")
                    sections.append("")

                # Evidence Trace (Phase C: Source Traceability)
                try:
                    raw_gap_ids = json.loads(idea.source_gap_ids) if idea.source_gap_ids else []
                except (json.JSONDecodeError, TypeError):
                    raw_gap_ids = []
                source_gaps = resolve_source_gaps(
                    session, raw_gap_ids, idea.pipeline_run_id,
                )

                # Supporting papers via junction table
                from sqlalchemy import select as _sel
                _links = session.execute(
                    _sel(IdeaPaperLink).where(IdeaPaperLink.idea_id == idea.id)
                ).scalars().all()
                _papers = []
                for _link in _links:
                    _p = session.get(PaperModel, _link.paper_id)
                    if _p:
                        _papers.append((_p, _link.role))

                # Structured proposal references
                _raw_refs = extract_proposal_references(proposal) if proposal else None
                _resolved_refs = (
                    resolve_references(_raw_refs, session, idea.pipeline_run_id)
                    if _raw_refs else []
                )

                has_evidence = bool(source_gaps) or _papers or _resolved_refs
                if has_evidence:
                    sections.append("### Evidence Trace\n")

                    if _papers:
                        sections.append("**Supporting Papers:**\n")
                        for _p, _role in _papers:
                            _line = f"- {_p.title}"
                            if _p.year:
                                _line += f" ({_p.year})"
                            if _p.venue:
                                _line += f". {_p.venue}"
                            _line += f" [{_role}]"
                            sections.append(f"{_line}\n")
                        sections.append("")

                    if source_gaps:
                        sections.append("**Source Research Gaps:**\n")
                        for sg in source_gaps:
                            if sg["resolved"]:
                                sections.append(
                                    f"- [{sg['gap_type']}] {sg['title']} "
                                    f"({sg['confidence']:.0%} confidence)\n"
                                )
                            else:
                                sections.append(
                                    f"- [unresolved] {sg['raw']}\n"
                                )
                        sections.append("")

                    if _resolved_refs:
                        sections.append("**Proposal References:**\n")
                        for _r in _resolved_refs:
                            _mark = "\u2705" if _r.resolved else "\u2753"
                            _line = f"- {_mark} {_r.title or _r.raw}"
                            if _r.resolved and _r.paper:
                                _line += f" \u2192 matched: \"{_r.paper.get('title', '')}\""
                                _line += f" [{_r.match_method}, {round(_r.match_confidence * 100)}%]"
                            elif not _r.resolved:
                                _line += " [unresolved]"
                            sections.append(f"{_line}\n")
                        sections.append("")

            return PlainTextResponse("\n".join(sections), media_type="text/markdown")
    except Exception as e:
        return PlainTextResponse(f"# Export error\n\n{e}", status_code=500)


@router.get(
    "/bibtex/{run_id}",
    summary="Export run papers as BibTeX",
    response_class=PlainTextResponse,
)
async def export_run_bibtex(run_id: int):
    """Export a pipeline run's source papers as BibTeX."""
    from backend.db.database import get_session
    from backend.db.crud import get_ideas_for_run
    from backend.pipeline.export.bibtex_exporter import paper_to_bibtex
    from backend.pipeline.literature.models import Paper
    from sqlalchemy import text

    try:
        with get_session() as session:
            # Get papers linked to the run's ideas via source_papers JSON
            ideas = get_ideas_for_run(session, run_id)
            if not ideas:
                return PlainTextResponse("% No ideas found for this run.", status_code=404)

            # Get all source papers for this run from the pipeline run's config
            run_row = session.execute(
                text("SELECT config_json FROM pipeline_runs WHERE id = :rid"),
                {"rid": run_id},
            ).fetchone()

            if not run_row:
                return PlainTextResponse("% Run not found.", status_code=404)

            # Fallback: generate BibTeX from idea references
            entries = []
            for i, idea in enumerate(ideas, 1):
                paper = Paper(
                    id=f"idea:{idea.id}",
                    title=getattr(idea, "title", f"Idea {i}"),
                    source="elephant_rock",
                    authors=[],
                    year=2026,
                )
                entries.append(paper_to_bibtex(paper))

            return PlainTextResponse("\n".join(entries), media_type="application/x-bibtex")
    except Exception as e:
        return PlainTextResponse(f"% Export error: {e}", status_code=500)
