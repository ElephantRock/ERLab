"""Data models for persistent agent memory."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class MemoryType(str, Enum):
    SEMANTIC = "semantic"  # Research facts: "RAG+reranking improves retrieval 15%"
    EPISODIC = "episodic"  # Run traces: "Round 3 produced the best idea using strategy X"
    PROCEDURAL = "procedural"  # Learned skills: "For NLP tasks, start with semantic_scholar"


class MemoryRevision(BaseModel):
    """A single revision in a memory entry's provenance chain."""

    revision_number: int
    content: str
    truth: TruthValue
    agent_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: str = ""  # "conflict_resolution", "decay", "consolidation", "update"


class MemoryEntry(BaseModel):
    """A single memory entry with content-addressable ID."""

    id: str  # SHA-256 content hash (Ajnan pattern)
    content: str
    memory_type: MemoryType
    namespace: str  # "research_facts" or "pipeline_experience"
    agent_id: str | None = None  # Owning agent (for multi-tenant isolation)
    truth: TruthValue = Field(default_factory=TruthValue.initial)
    source_run_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime | None = None
    access_count: int = 0
    revision_history: list[MemoryRevision] = Field(default_factory=list)


class MemoryQuery(BaseModel):
    """Query parameters for memory retrieval."""

    query: str
    memory_type: MemoryType | None = None
    namespace: str | None = None
    agent_id: str | None = None  # Filter by owning agent
    top_k: int = 10
    min_confidence: float = 0.1
