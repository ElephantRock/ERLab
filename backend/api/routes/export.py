"""Export API routes: download proposals as Markdown or BibTeX."""

from fastapi import APIRouter, HTTPHeader
from starlette.responses import PlainTextResponse

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/markdown/{run_id}", response_class=PlainTextResponse)
async def export_markdown(run_id: str):
    """Export a pipeline run's proposals as Markdown."""
    from backend.pipeline.persistence import PipelinePersistence

    persistence = PipelinePersistence()
    try:
        proposals = persistence.get_proposals(run_id)
        if not proposals:
            return PlainTextResponse("# No proposals found for this run.", status_code=404)

        sections = [f"# Research Proposals — {run_id}\n"]
        for i, p in enumerate(proposals, 1):
            title = getattr(p, "title", f"Proposal {i}")
            content = getattr(p, "content", "")
            sections.append(f"## {i}. {title}\n\n{content}\n")

        return PlainTextResponse("\n".join(sections), media_type="text/markdown")
    except Exception as e:
        return PlainTextResponse(f"# Export error\n\n{e}", status_code=500)


@router.get("/bibtex/{run_id}", response_class=PlainTextResponse)
async def export_bibtex(run_id: str):
    """Export a pipeline run's papers as BibTeX."""
    from backend.pipeline.persistence import PipelinePersistence
    from backend.pipeline.export.bibtex_exporter import papers_to_bibtex
    from backend.pipeline.literature.models import Paper

    persistence = PipelinePersistence()
    try:
        papers = persistence.get_papers(run_id)
        if not papers:
            return PlainTextResponse("% No papers found for this run.", status_code=404)

        bibtex = papers_to_bibtex(papers)
        return PlainTextResponse(bibtex, media_type="application/x-bibtex")
    except Exception as e:
        return PlainTextResponse(f"% Export error: {e}", status_code=500)
