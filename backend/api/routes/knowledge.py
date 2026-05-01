"""Knowledge base API routes."""

from fastapi import APIRouter

from backend.api.errors import ServiceUnavailableError
from backend.api.schemas import SearchRequest

router = APIRouter()


@router.get(
    "/stats",
    summary="Knowledge base statistics",
    description="Get knowledge base configuration and statistics.",
)
async def knowledge_stats():
    """Get knowledge base statistics.

    Returns:
        {"chroma_persist_dir": "...", "embedding_provider": "...", "embedding_model": "..."}

    Example response:
        {"chroma_persist_dir": "./data/chroma", "embedding_provider": "openai", "embedding_model": "text-embedding-3-small"}
    """
    from backend.config import get_settings

    settings = get_settings()
    return {
        "chroma_persist_dir": settings.chroma_persist_dir,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }


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
