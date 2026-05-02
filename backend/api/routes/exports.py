"""Export API routes — PDF export and bulk ZIP export."""

import io
import json
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.api.errors import NotFoundError
from backend.api.schemas import ExportPdfRequest, BulkExportRequest

router = APIRouter()


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
