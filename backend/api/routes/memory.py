"""Memory API routes."""

from fastapi import APIRouter, Query

from backend.api.errors import NotFoundError, ServiceUnavailableError
from backend.config import get_settings
from backend.pipeline.memory.models import MemoryQuery, MemoryType

router = APIRouter()


@router.get(
    "/recall",
    summary="Recall memories",
    description="Query the agent memory system for relevant stored knowledge.",
)
async def recall_memories(
    query: str,
    memory_type: MemoryType | None = None,
    top_k: int = Query(default=10, ge=1, le=100),
):
    """Query the agent memory system.

    Args:
        query: Natural language query to search memories.
        memory_type: Optional filter by memory type.
        top_k: Maximum number of results to return.

    Returns:
        {"query": "...", "results": [...]}

    Example response:
        {"query": "novel transformer", "results": [{"content": "...", "type": "insight", "confidence": 0.85, "created_at": "..."}]}
    """
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


@router.get(
    "/stats",
    summary="Memory statistics",
    description="Get memory system statistics including counts by type.",
)
async def memory_stats():
    """Get memory system statistics.

    Returns:
        {"total_memories": 42, "by_type": {"insight": 20, "fact": 22}}

    Example response:
        {"total_memories": 42, "by_type": {"insight": 20, "fact": 22}}
    """
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


@router.delete(
    "/{entry_id}",
    summary="Delete a memory entry",
    description="Delete a memory entry by its unique identifier.",
)
async def delete_memory(entry_id: str):
    """Delete a memory entry by ID.

    Args:
        entry_id: The unique memory entry identifier.

    Returns:
        {"status": "deleted", "entry_id": "..."}

    Example response:
        {"status": "deleted", "entry_id": "mem_abc123"}
    """
    settings = get_settings()
    if not settings.memory_enabled:
        raise ServiceUnavailableError("Memory system is disabled")

    from backend.pipeline.memory.service import MemoryService

    memory = MemoryService(settings.memory_persist_dir)
    deleted = await memory.delete(entry_id)
    if not deleted:
        raise NotFoundError("Memory entry not found")
    return {"status": "deleted", "entry_id": entry_id}
