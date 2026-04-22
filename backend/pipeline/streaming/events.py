"""Typed stream events for pipeline progress, LLM chunks, and tool calls."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class StreamEventType(str, Enum):
    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    IDEA_GENERATED = "idea_generated"
    IDEA_SCORED = "idea_scored"
    TOOL_CALL = "tool_call"
    LLM_CHUNK = "llm_chunk"
    ERROR = "error"
    PROGRESS = "progress"
    HEARTBEAT = "heartbeat"
    DONE = "done"


class StreamEvent(BaseModel):
    type: StreamEventType
    timestamp: float = Field(default_factory=time.time)
    run_id: str = ""
    data: dict = Field(default_factory=dict)
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])

    def to_sse(self) -> str:
        """Format as SSE data line."""
        import json
        return f"data: {json.dumps(self.model_dump(mode='json'))}\n\n"
