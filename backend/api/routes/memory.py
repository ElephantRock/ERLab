"""Memory API routes."""

import asyncio
from datetime import datetime

from fastapi import APIRouter

from backend.config import get_settings
from backend.pipeline.memory.models import MemoryQuery, MemoryType
from backend.pipeline.memory.service import MemoryService

router = APIRouter()


@router.get("/recall")
async def recall_memories(
    query: str,
    memory_type: MemoryType | None = None,
    top_k: int = 10,
):
    """Query the agent memory system."""
    settings = get_settings()
    if not settings.memory_enabled:
        return {"error": "Memory system is disabled"}

    memory = MemoryService(settings.memory_persist_dir)
    results = await memory.recall(MemoryQuery(
        query=query,
        memory_type=memory_type,
        top_k=top_k,
    ))
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
        return {"error": "Memory system is disabled"}

    memory = MemoryService(settings.memory_persist_dir)
    all_entries = list(memory._index.values())
    return {
        "total_memories": len(all_entries),
        "by_type": {
            mt.value: sum(1 for e in all_entries if e.memory_type == mt)
            for mt in MemoryType
        },
    }
