"""Knowledge base API routes."""

from fastapi import APIRouter

from backend.config import get_settings

router = APIRouter()


@router.get("/stats")
async def knowledge_stats():
    """Get knowledge base statistics."""
    settings = get_settings()
    return {
        "chroma_persist_dir": settings.chroma_persist_dir,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
    }


@router.post("/search")
async def search_knowledge(query: str, top_k: int = 10):
    """Semantic search across the knowledge base."""
    try:
        from backend.pipeline.knowledge.vector_store import VectorStore
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.providers.provider_factory import create_provider

        provider = create_provider()
        embedding = EmbeddingService(provider)
        store = VectorStore(get_settings().chroma_persist_dir, embedding)
        results = await store.query(query, n_results=top_k)
        return {"query": query, "results": results}
    except ImportError:
        return {"error": "ChromaDB not installed. Run: pip install chromadb"}
    except Exception as e:
        return {"error": str(e)}
