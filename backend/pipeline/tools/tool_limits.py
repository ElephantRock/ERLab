"""Tool resource limits, audit trail, and trust levels.

Provides execution boundaries for tool calls, especially
untrusted tools loaded from external plugins.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ToolLimitsConfig:
    """Per-tool resource limits."""

    timeout_seconds: float = 30.0
    max_output_bytes: int = 1_000_000  # 1MB
    max_retries: int = 2
    trust_level: str = "trusted"  # "trusted" or "untrusted"


UNTRUSTED_CONFIG = ToolLimitsConfig(
    timeout_seconds=10.0,
    max_output_bytes=100_000,  # 100KB
    max_retries=0,
    trust_level="untrusted",
)

TRUSTED_CONFIG = ToolLimitsConfig(
    timeout_seconds=120.0,
    max_output_bytes=1_000_000,
    max_retries=2,
    trust_level="trusted",
)


@dataclass
class ToolExecutionEvent:
    """Record of a single tool execution for audit purposes."""

    tool_name: str
    status: str  # "success", "timeout", "error", "blocked"
    duration_ms: float = 0.0
    input_hash: str = ""
    output_hash: str = ""
    run_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    error: str | None = None


class ToolAuditLog:
    """Records tool execution events for audit trail."""

    def __init__(self, persist_path: str | None = None):
        self._events: list[ToolExecutionEvent] = []
        self._persist_path = persist_path

    def record(self, event: ToolExecutionEvent) -> None:
        self._events.append(event)
        if self._persist_path:
            self._append_to_file(event)

    def _append_to_file(self, event: ToolExecutionEvent) -> None:
        import json
        from pathlib import Path

        Path(self._persist_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self._persist_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "tool_name": event.tool_name,
                "status": event.status,
                "duration_ms": event.duration_ms,
                "run_id": event.run_id,
                "timestamp": event.timestamp,
                "error": event.error,
            }) + "\n")

    @property
    def events(self) -> list[ToolExecutionEvent]:
        return list(self._events)

    def get_events(self, tool_name: str | None = None, status: str | None = None) -> list[ToolExecutionEvent]:
        results = self._events
        if tool_name:
            results = [e for e in results if e.tool_name == tool_name]
        if status:
            results = [e for e in results if e.status == status]
        return results
