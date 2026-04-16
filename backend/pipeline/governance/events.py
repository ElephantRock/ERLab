"""Cryptographic audit trail for governance decisions.

ESAA-inspired event sourcing with SHA-256 hash chain verification.
"""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class GovernanceEvent(BaseModel):
    event_type: str     # "output.accepted", "output.rejected", "output.revised"
    stage: str
    content_hash: str   # SHA-256 of original content
    checks_summary: str = ""
    timestamp: datetime = datetime.now()
    previous_hash: str = ""


class GovernanceAuditLog:
    """Cryptographic audit trail for governance decisions."""

    def __init__(self, persist_path: str = "./data/governance_audit.jsonl"):
        self._path = Path(persist_path)
        self._events: list[GovernanceEvent] = []
        self._load()

    def record(self, event: GovernanceEvent) -> None:
        """Record a governance event and chain it to the previous event."""
        if self._events:
            event.previous_hash = self._hash_event(self._events[-1])

        self._events.append(event)
        self._append(event)

    def verify_chain(self) -> bool:
        """Verify the integrity of the hash chain."""
        for i in range(1, len(self._events)):
            expected = self._hash_event(self._events[i - 1])
            if self._events[i].previous_hash != expected:
                logger.error("Chain broken at event %d", i)
                return False
        return True

    def get_events(self, stage: str | None = None) -> list[GovernanceEvent]:
        """Get events, optionally filtered by stage."""
        if stage:
            return [e for e in self._events if e.stage == stage]
        return list(self._events)

    @staticmethod
    def content_hash(content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @staticmethod
    def _hash_event(event: GovernanceEvent) -> str:
        """Compute hash of an event for chain linking."""
        raw = f"{event.event_type}:{event.stage}:{event.content_hash}:{event.timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _append(self, event: GovernanceEvent) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

    def _load(self) -> None:
        if not self._path.exists():
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = GovernanceEvent.model_validate_json(line)
                    self._events.append(event)
                except Exception:
                    pass
