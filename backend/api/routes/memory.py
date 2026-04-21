"""Memory API routes."""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.api.errors import ServiceUnavailableError
from backend.config import get_settings
from backend.pipeline.memory.models import MemoryQuery, MemoryType

router = APIRouter()


@router.get("/recall")
async def recall_memories(
    query: str,
    memory_type: MemoryType | None = None,
    top_k: int = Query(default=10, ge=1, le=100),
):
    """Query the agent memory system."""
    settings = get_settings()
    if not settings.memory_enabled:
        raise ServiceUnavailableError("Memory system is disabled")

    from backend.pipeline.memory.service import MemoryService

    memory = MemoryService(settings.memory_persist_dir)
    results = await memory.recall(
        MemoryQuery(
            query=query,
            memory_type=memory_type,
            top_k=top_k,
        )
    )
    return {
        "query": query,
        "results": [
            {
                "content": r.content[:200],
                "type": r.memory_type.value,
                "confidence": r.truth.confidence,
                "created_at": str(r.created_at),
            }
            for r in results
        ],
    }


@router.get("/stats")
async def memory_stats():
    """Get memory system statistics."""
    settings = get_settings()
    if not settings.memory_enabled:
        raise ServiceUnavailableError("Memory system is disabled")

    from backend.pipeline.memory.service import MemoryService

    memory = MemoryService(settings.memory_persist_dir)
    all_entries = list(memory._index.values())
    return {
        "total_memories": len(all_entries),
        "by_type": {
            mt.value: sum(1 for e in all_entries if e.memory_type == mt) for mt in MemoryType
        },
    }


@router.delete("/{entry_id}")
async def delete_memory(entry_id: str):
    """Delete a memory entry by ID."""
    settings = get_settings()
    if not settings.memory_enabled:
        raise ServiceUnavailableError("Memory system is disabled")

    from backend.pipeline.memory.service import MemoryService

    memory = MemoryService(settings.memory_persist_dir)
    deleted = await memory.delete(entry_id)
    if not deleted:
        return JSONResponse(status_code=404, content={"error": "Memory entry not found"})
    return {"status": "deleted", "entry_id": entry_id}
