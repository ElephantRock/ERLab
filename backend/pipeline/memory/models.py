"""Data models for persistent agent memory."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class MemoryType(str, Enum):
    SEMANTIC = "semantic"        # Research facts: "RAG+reranking improves retrieval 15%"
    EPISODIC = "episodic"        # Run traces: "Round 3 produced the best idea using strategy X"
    PROCEDURAL = "procedural"    # Learned skills: "For NLP tasks, start with semantic_scholar"


class MemoryEntry(BaseModel):
    """A single memory entry with content-addressable ID."""
    id: str                              # SHA-256 content hash (Ajnan pattern)
    content: str
    memory_type: MemoryType
    namespace: str                       # "research_facts" or "pipeline_experience"
    truth: TruthValue = Field(default_factory=TruthValue.initial)
    source_run_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime | None = None
    access_count: int = 0


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""
    query: str
    memory_type: MemoryType | None = None
    namespace: str | None = None
    top_k: int = 10
    min_confidence: float = 0.1
