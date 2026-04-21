"""Knowledge base API routes."""

from fastapi import APIRouter

from backend.api.errors import ServiceUnavailableError
from backend.api.schemas import SearchRequest

router = APIRouter()


@router.get("/stats")
async def knowledge_stats():
    """Get knowledge base statistics."""
    from backend.config import get_settings

    settings = get_settings()
    return {
        "chroma_persist_dir": settings.chroma_persist_dir,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    """Semantic search across the knowledge base."""
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
        raise ServiceUnavailableError("ChromaDB not installed. Run: pip install chromadb") from None
