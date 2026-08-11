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


@router.get(
    "/ingested",
    summary="List ingested paper IDs",
    description=(
        "Returns the set of paper IDs that have been ingested into the "
        "knowledge base. Used by the literature UI to derive an "
        "authoritative persisted-ingestion indicator from backend state, "
        "rather than from ephemeral client state."
    ),
)
async def list_ingested_papers():
    """Return the set of paper IDs persisted in the knowledge base.

    The vector store records each ingested paper chunk with metadata
    ``{"source": "academic_paper", "paper_id": <id>}`` (see
    ``_do_ingest`` in this module). We query the collection metadata
    and return the unique paper IDs.

    Returns:
        {"ids": ["p1", "p2", ...]}

    If the vector store is unavailable or the embedding provider is
    offline, we return an empty list rather than failing — the UI
    gracefully treats this as "no persisted ingestion state known".
    """
    try:
        from backend.config import get_settings
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.providers.provider_factory import create_provider

        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)

        all_meta = store._collection.get(include=["metadatas"])
        ids: list[str] = []
        seen: set[str] = set()
        for m in (all_meta.get("metadatas") or []):
            if not m:
                continue
            # Two ingestion paths write to the vector store:
            #   - add_papers (vector_store.py): metadata type absent, paper_id present
            #   - _do_ingest (this file):       metadata type="academic_paper", paper_id present
            # We accept either as evidence of ingestion.
            paper_id = m.get("paper_id")
            if paper_id and paper_id not in seen:
                seen.add(paper_id)
                ids.append(paper_id)
        return {"ids": ids}
    except Exception as e:
        logger.info("ingested-papers lookup unavailable: %s", e)
        return {"ids": []}


async def _do_ingest(paper: Paper) -> dict:
    """Persist a paper into the vector store with paper_id metadata.

    F1.5d: This is the truthful ingest path. The paper is written via
    VectorStore.add_papers, which embeds the chunk text and upserts into
    the chromadb collection with metadata {"paper_id": paper.id, ...}.
    GET /literature/ingested reads that exact metadata, so the write
    and read paths share one source of truth.

    Failures MUST surface as errors — never return a fake success when
    nothing was persisted. The prior ImportError-fallback was a
    correctness defect (claimed "ingested" without writing anything).
    """
    from backend.api.errors import ServiceUnavailableError
    from backend.config import get_settings
    from backend.pipeline.ingestion.chunker import DocumentChunk
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.providers.provider_factory import create_provider

    # 1. Build chunk text from paper title + abstract + authors.
    #    One chunk is sufficient for title+abstract papers (matches the
    #    IngestionStage idiom in backend/pipeline/stages.py:511-524).
    parts = [paper.title]
    if paper.abstract:
        parts.append(paper.abstract)
    if paper.authors:
        parts.append(", ".join(a.name for a in paper.authors))
    text = "\n\n".join(p for p in parts if p)

    chunks = [
        DocumentChunk(
            text=text,
            paper_id=paper.id,
            section="abstract",
            chunk_index=0,
        )
    ]

    # 2. Construct the VectorStore exactly like list_ingested_papers and
    #    knowledge.ingest_pdf so the read path observes the same collection.
    try:
        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)
    except Exception as e:
        # Provider/key/chroma not configured — raise, do NOT fake success.
        logger.error("Vector store construction failed for paper %s: %s", paper.id, e)
        raise ServiceUnavailableError(
            detail=f"Knowledge base unavailable: {e}",
            hint="Set EROCK_OPENAI_API_KEY (or switch EROCK_EMBEDDING_PROVIDER to ollama) and ensure chromadb is installed.",
        ) from e

    # 3. Persist. add_papers embeds, dedupes by "{paper.id}_chunk_{i}",
    #    and writes metadata {paper_id, paper_title, source, section,
    #    year, keywords}. Returns the number of chunks upserted.
    try:
        stored = await store.add_papers([paper], [chunks])
    except Exception as e:
        logger.error("Ingestion failed for paper %s: %s", paper.id, e)
        raise BadRequestError(
            detail=f"Ingestion failed: {e}",
            hint="Check that the embedding provider is reachable and the paper has non-empty content.",
        ) from e

    if stored == 0:
        # add_papers silently drops zero-vector chunks (provider offline).
        # Surface this as failure so clients know nothing was persisted
        # and the GET /literature/ingested read path will not report the id.
        raise BadRequestError(
            detail="Ingestion wrote 0 chunks — embedding provider may be offline",
            hint="Switch EROCK_EMBEDDING_PROVIDER to a working provider (openai/gemini/ollama).",
        )

    return {"status": "ingested", "id": paper.id, "chunks": stored}


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
