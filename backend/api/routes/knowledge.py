"""Knowledge base API routes."""

import shutil
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from backend.api.errors import BadRequestError, ServiceUnavailableError
from backend.api.schemas import SearchRequest

router = APIRouter()

# ── HB-01: PDF magic-bytes validation ──────────────────────────────
_PDF_MAGIC = b"%PDF"


def _validate_pdf_magic(data: bytes) -> None:
    """Validate that uploaded bytes start with the PDF magic header.

    Prevents executable or malicious file uploads (HB-01).
    Raises BadRequestError if validation fails.
    """
    if not data[:5].startswith(_PDF_MAGIC):
        raise BadRequestError(
            "Uploaded file is not a valid PDF",
            hint="Only PDF files are accepted. Ensure the file starts with the %PDF header.",
        )


@router.get(
    "/stats",
    summary="Knowledge base statistics",
    description="Get knowledge base configuration and enriched statistics including document and chunk counts.",
)
async def knowledge_stats():
    """Get enriched knowledge base statistics.

    Returns:
        {"chroma_persist_dir": "...", "embedding_provider": "...", "embedding_model": "...",
         "total_documents": N, "total_chunks": M}

    Example response:
        {"chroma_persist_dir": "./data/chroma", "embedding_provider": "openai",
         "embedding_model": "text-embedding-3-small", "total_documents": 5, "total_chunks": 42}
    """
    from backend.config import get_settings

    settings = get_settings()
    base = {
        "chroma_persist_dir": settings.chroma_persist_dir,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }
    try:
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.providers.provider_factory import create_provider

        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)
        store_stats = store.get_stats()
        base["total_chunks"] = store_stats.get("document_count", 0)

        # Count unique documents (paper_ids) from metadata
        try:
            all_meta = store._collection.get(include=["metadatas"])
            unique_papers = set()
            for m in all_meta.get("metadatas", []) or []:
                if m and "paper_id" in m:
                    unique_papers.add(m["paper_id"])
            base["total_documents"] = len(unique_papers)
        except Exception:
            base["total_documents"] = 0
    except ImportError:
        base["total_documents"] = 0
        base["total_chunks"] = 0

    return base


@router.post(
    "/search",
    summary="Search knowledge base",
    description="Perform semantic search across the knowledge base using vector similarity.",
)
async def search_knowledge(request: SearchRequest):
    """Semantic search across the knowledge base.

    Example request:
        {"query": "transformer attention mechanisms", "top_k": 10}

    Example response:
        {"query": "transformer attention mechanisms", "results": [{"content": "...", "score": 0.92, "metadata": {}}]}
    """
    try:
        from backend.config import get_settings
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.providers.provider_factory import create_provider

        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(get_settings().chroma_persist_dir, embedding)
        results = await store.query(request.query, n_results=request.top_k)
        return {"query": request.query, "results": results}
    except ImportError:
        raise ServiceUnavailableError(
            "ChromaDB not installed",
            hint="Run: pip install chromadb",
        ) from None


@router.post(
    "/ingest",
    summary="Upload and ingest a PDF",
    description=(
        "Upload a PDF file for ingestion into the knowledge base. "
        "The file is validated as a genuine PDF (HB-01), parsed, chunked, and embedded."
    ),
)
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a PDF document into the knowledge base.

    Accepts multipart/form-data with a single 'file' field.
    Validates PDF magic bytes before processing (HB-01).

    Returns:
        {"status": "ingested", "filename": "...", "chunks": N}
    """
    if not file.filename:
        raise BadRequestError("No filename provided", hint="Upload a PDF file with a valid filename.")

    # Read file content
    content = await file.read()

    # HB-01: Validate PDF magic bytes — reject executables and non-PDFs
    _validate_pdf_magic(content)

    # Write to temporary file for parsing
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir) / f"{uuid.uuid4().hex}.pdf"
    try:
        tmp_path.write_bytes(content)

        # Parse and chunk the PDF
        paper_id = file.filename.removesuffix(".pdf")
        from backend.pipeline.ingestion.pdf_service import PDFService

        pdf_service = PDFService()
        chunks = await pdf_service.parse_and_chunk(
            str(tmp_path),
            paper_id=paper_id,
        )

        if not chunks:
            return {
                "status": "ingested",
                "filename": file.filename,
                "chunks": 0,
            }

        # Embed and store chunks
        from backend.config import get_settings
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.literature.models import Paper
        from backend.providers.provider_factory import create_provider

        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)

        paper = Paper(
            id=paper_id,
            source="pdf_upload",
            title=file.filename,
            abstract="",
        )
        stored = await store.add_papers([paper], [chunks])

        return {
            "status": "ingested",
            "filename": file.filename,
            "chunks": stored,
        }
    except ImportError:
        raise ServiceUnavailableError(
            "ChromaDB or PDF parser not installed",
            hint="Run: pip install chromadb pymupdf",
        ) from None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
