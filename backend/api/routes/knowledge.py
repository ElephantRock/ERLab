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


# B160: Supported extensions for generic ingestion
_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".md", ".docx"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _validate_upload(filename: str, data: bytes) -> None:
    """Validate uploaded file extension and size (B160, HB-01)."""
    if not filename:
        raise BadRequestError("No filename provided", hint="Upload a file with a valid filename.")
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise BadRequestError(
            f"Unsupported file type: {ext}",
            hint=f"Supported types: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )
    if len(data) > _MAX_FILE_SIZE:
        raise BadRequestError(
            f"File too large: {len(data) / 1024 / 1024:.1f} MB",
            hint=f"Maximum file size is {_MAX_FILE_SIZE // 1024 // 1024} MB",
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
        from backend.db.database import get_session
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.legacy_collection_freeze import (
            LegacyCollectionFrozenError,
            assert_legacy_not_frozen,
        )
        from backend.providers.provider_factory import create_provider

        # P0.3.6: Check if legacy collection is frozen
        with get_session() as freeze_session:
            assert_legacy_not_frozen(freeze_session)

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
    "/search/governed",
    summary="Scoped knowledge search (governed)",
    description=(
        "Perform scoped semantic search for a governed pipeline run. "
        "Requires explicit run_id and scope_mode. No global fallback."
    ),
)
async def search_knowledge_governed(
    run_id: int,
    query: str,
    scope_mode: str = "current_run_only",
    top_k: int = 10,
    selected_paper_ids: list[int] | None = None,
):
    """Governed scoped vector search.

    Requires a provenance_v1 run and an explicit scope mode.
    Returns retrieval_event_id and coverage metadata.
    """


    from backend.config import get_settings
    from backend.db.database import _get_engine, get_session
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.provenance_gate import (
        ProvenanceContractError,
        load_run_provenance_contract,
        select_run_execution_mode,
    )
    from backend.pipeline.scoped_vector_service import query_vectors
    from backend.pipeline.vector_contracts import (
        ScopedVectorRetrievalRequest,
        VectorRetrievalScope,
    )
    from backend.providers.provider_factory import create_provider

    # Verify governed run
    try:
        with get_session() as s:
            contract = load_run_provenance_contract(s, run_id)
            mode = select_run_execution_mode(contract)
    except ProvenanceContractError:
        raise BadRequestError(
            f"Run {run_id} not found",
            hint="Provide a valid pipeline run ID.",
        )

    if mode != "governed":
        raise BadRequestError(
            f"Run {run_id} is not governed (mode={mode})",
            hint="Use /search for legacy searches or create a provenance_v1 run.",
        )

    # Validate scope mode
    valid_modes = {"current_run_only", "same_domain_prior_runs", "global_library", "selected_papers"}
    if scope_mode not in valid_modes:
        raise BadRequestError(
            f"Invalid scope_mode {scope_mode!r}",
            hint=f"Choose from: {sorted(valid_modes)}",
        )

    if scope_mode == "selected_papers" and not selected_paper_ids:
        raise BadRequestError(
            "selected_papers scope requires selected_paper_ids",
        )

    # Use governed vector runtime (constructed from settings at call time)
    from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

    runtime = build_governed_vector_runtime_from_settings(_get_engine())
    if runtime is None:
        raise ServiceUnavailableError(
            "Governed vector runtime unavailable",
            hint="Ensure embedding provider and ChromaDB are configured.",
        )

    profile_id = runtime.effective_embedding_config.embedding_profile_id
    settings = get_settings()
    provider = create_provider()
    embedding = EmbeddingService(provider)

    # Generate explicit query vector
    query_embeddings = await embedding.embed_texts([query])
    query_vector = tuple(query_embeddings[0]) if query_embeddings else ()

    if not query_vector:
        raise BadRequestError("Could not generate query embedding")

    # Build scoped request
    scope = VectorRetrievalScope(
        schema_version="vector_scope_v1",
        mode=scope_mode,
        run_id=run_id,
        embedding_profile_id=profile_id,
        selected_paper_ids=tuple(selected_paper_ids) if selected_paper_ids else (),
    )

    request = ScopedVectorRetrievalRequest(
        schema_version="vector_retrieval_v1",
        run_id=run_id,
        stage_name="knowledge_search",
        retrieval_key=f"knowledge_search:{uuid.uuid4().hex[:8]}",
        scope=scope,
        query_vector=query_vector,
        top_k=top_k,
        allow_partial_index_coverage=True,
    )

    outcome = await query_vectors(
        session_factory=runtime.session_factory,
        backend=runtime.backend,
        request=request,
    )

    return {
        "retrieval_event_id": outcome.retrieval_event_id,
        "scope_mode": scope_mode,
        "coverage_status": outcome.coverage_status,
        "allowed_paper_count": outcome.allowed_paper_count,
        "indexed_paper_count": outcome.indexed_paper_count,
        "returned_result_count": len(outcome.results),
        "results": [
            {
                "paper_id": r.paper_id,
                "rank": r.rank,
                "score": r.raw_score,
                "vector_record_id": r.vector_record_id,
            }
            for r in outcome.results
        ],
    }


@router.post(
    "/ingest",
    summary="Upload and ingest a document",
    description=(
        "Upload a document (PDF, TXT, CSV, MD, DOCX) for ingestion into the knowledge base. "
        "The file is validated, parsed, chunked, and embedded (B160)."
    ),
)
async def ingest_pdf(file: UploadFile = File(...)):
    """Upload and ingest a document into the knowledge base.

    Accepts multipart/form-data with a single 'file' field.
    Supports PDF, TXT, CSV, MD, DOCX formats.

    Returns:
        {"status": "ingested", "filename": "...", "chunks": N, "format": "..."}
    """
    if not file.filename:
        raise BadRequestError("No filename provided", hint="Upload a file with a valid filename.")

    # Read file content
    content = await file.read()

    # B160: Validate extension and size
    _validate_upload(file.filename, content)

    # Format-specific magic-byte validation
    ext = Path(file.filename).suffix.lower()
    if ext == ".pdf":
        _validate_pdf_magic(content)

    # Write to temporary file for parsing
    tmp_dir = tempfile.mkdtemp()
    tmp_path = Path(tmp_dir) / f"{uuid.uuid4().hex}{ext}"
    try:
        tmp_path.write_bytes(content)

        paper_id = Path(file.filename).stem
        from backend.pipeline.ingestion.document_parser import DocumentParser

        parser = DocumentParser()
        chunks = await parser.parse_and_chunk(
            str(tmp_path),
            paper_id=paper_id,
            filename=file.filename,
        )

        if not chunks:
            return {
                "status": "ingested",
                "filename": file.filename,
                "chunks": 0,
                "format": ext.lstrip("."),
            }

        # Embed and store chunks
        from backend.config import get_settings
        from backend.db.database import get_session
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.legacy_collection_freeze import assert_legacy_not_frozen
        from backend.pipeline.literature.models import Paper
        from backend.providers.provider_factory import create_provider

        # P0.3.6: Check if legacy collection is frozen
        with get_session() as freeze_session:
            assert_legacy_not_frozen(freeze_session)

        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(settings.chroma_persist_dir, embedding)

        paper = Paper(
            id=paper_id,
            source="local_upload",
            title=file.filename,
            abstract=chunks[0].text[:500] if chunks else "",
        )
        stored = await store.add_papers([paper], [chunks])

        return {
            "status": "ingested",
            "filename": file.filename,
            "chunks": stored,
            "format": ext.lstrip("."),
        }
    except ImportError:
        raise ServiceUnavailableError(
            "Required dependencies not installed",
            hint="Run: pip install chromadb pymupdf",
        ) from None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get(
    "/documents",
    summary="List uploaded documents",
    description="Get a list of all locally uploaded documents in the knowledge base (B160).",
)
async def list_documents():
    """List all documents that were uploaded locally (source=local_upload)."""
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
        docs = []
        seen_ids = set()
        for m in (all_meta.get("metadatas") or []):
            if m and m.get("paper_id") not in seen_ids:
                seen_ids.add(m.get("paper_id"))
                docs.append({
                    "id": m.get("paper_id", ""),
                    "source": m.get("source", "unknown"),
                    "title": m.get("title", m.get("paper_id", "")),
                })
        return {"documents": docs, "total": len(docs)}
    except Exception as e:
        return {"documents": [], "total": 0, "error": str(e)}
