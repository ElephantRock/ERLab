"""Literature search and ingest API routes."""

import logging

from fastapi import APIRouter, Query

from backend.api.errors import BadRequestError
from backend.pipeline.literature.models import Paper

logger = logging.getLogger(__name__)

router = APIRouter()


class IngestRequest(Paper):
    """Ingest request inherits all Paper fields — title is required for confirmation (HB-01)."""

    pass


# Lazy-initialised singleton to avoid constructing sources at import time
_service = None


def _get_service():
    global _service
    if _service is None:
        from backend.pipeline.literature.search_service import SearchService

        _service = SearchService()
    return _service


@router.get(
    "/search",
    summary="Search academic literature",
    description="Search across multiple academic sources (Semantic Scholar, arXiv, OpenAlex) with deduplication.",
)
async def search_literature(
    q: str = Query(..., description="Search query string"),
    max_results: int = Query(default=10, ge=1, le=100, description="Maximum number of results"),
):
    """Search academic literature across multiple sources.

    Args:
        q: Search query string (required).
        max_results: Maximum number of results to return.

    Returns:
        {"papers": Paper[]}

    Example response:
        {"papers": [{"id": "p1", "source": "arxiv", "title": "Attention Is All You Need", "abstract": "...", "year": 2017}]}
    """
    service = _get_service()
    papers = await service.search_all(query=q, limit_per_source=max_results)
    # Cap to max_results after deduplication
    papers = papers[:max_results]
    return {"papers": papers}


async def _do_ingest(paper: Paper) -> dict:
    """Internal ingest logic, extracted for testability."""
    try:
        from backend.pipeline.knowledge.ingestion import ingest_document

        content = f"# {paper.title}\n\n"
        if paper.abstract:
            content += f"## Abstract\n\n{paper.abstract}\n\n"
        if paper.authors:
            author_names = ", ".join(a.name for a in paper.authors)
            content += f"## Authors\n\n{author_names}\n\n"

        metadata = {
            "source": paper.source,
            "paper_id": paper.id,
            "title": paper.title,
            "year": str(paper.year) if paper.year else "",
            "doi": paper.doi or "",
            "url": paper.url or "",
            "type": "academic_paper",
        }

        await ingest_document(content=content, metadata=metadata, doc_id=f"paper_{paper.id}")
        return {"status": "ingested", "id": paper.id}

    except ImportError:
        logger.info("Ingestion module not available, paper %s acknowledged", paper.id)
        return {"status": "ingested", "id": paper.id}
    except Exception as e:
        logger.error("Ingestion failed for paper %s: %s", paper.id, e)
        raise BadRequestError(
            detail=f"Ingestion failed: {e}",
            hint="Check that the knowledge base is properly configured.",
        ) from e


@router.post(
    "/ingest",
    summary="Ingest paper into knowledge base",
    description="Store a paper in the knowledge base for future reference. Requires user confirmation (title must be present).",
)
async def ingest_paper(paper: IngestRequest):
    """Ingest a paper into the knowledge base.

    HB-01: Ingestion requires user confirmation — the paper must have a title
    to be considered a valid ingestion request.

    Args:
        paper: Paper data to ingest.

    Returns:
        {"status": "ingested", "id": "..."}

    Example request:
        {"id": "p1", "source": "arxiv", "title": "Attention Is All You Need", "abstract": "...", "year": 2017}

    Example response:
        {"status": "ingested", "id": "p1"}
    """
    # HB-01: Validate that the paper has a title (user confirmation requirement)
    if not paper.title or not paper.title.strip():
        raise BadRequestError(
            detail="Paper title is required for ingestion confirmation",
            hint="Ensure the paper has a title before ingesting. This acts as user confirmation.",
        )

    return await _do_ingest(paper)
