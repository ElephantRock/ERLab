"""Feedback history — audit trail for parameter evolution proposals.

Logs every proposal (accepted, discarded, or modified) with score deltas
for full traceability of the self-improvement process.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FeedbackRecord(BaseModel):
    """A single parameter proposal feedback entry."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = ""
    params_proposed: dict[str, Any] = Field(default_factory=dict)
    params_accepted: dict[str, Any] | None = None
    score_delta: float = 0.0
    action: str = "accepted"  # "accepted" | "discarded" | "modified"
    reason: str = ""


class FeedbackHistory:
    """Persistent audit trail of all parameter evolution proposals."""

    def __init__(self, persist_path: str = "./data/self_improve/feedback_history.json") -> None:
        self._path = Path(persist_path)
        self._records: list[FeedbackRecord] = []
        self._load()

    def record_proposal(
        self,
        proposed: dict[str, Any],
        accepted: dict[str, Any] | None,
        score_delta: float,
        action: str,
        run_id: str = "",
        reason: str = "",
    ) -> None:
        """Record a parameter proposal outcome."""
        record = FeedbackRecord(
            run_id=run_id,
            params_proposed=proposed,
            params_accepted=accepted,
            score_delta=score_delta,
            action=action,
            reason=reason,
        )
        self._records.append(record)
        self._save()

    def get_recent(self, limit: int = 20) -> list[FeedbackRecord]:
        """Return the most recent records."""
        return self._records[-limit:]

    def acceptance_rate(self) -> float:
        """Fraction of proposals that were accepted."""
        if not self._records:
            return 0.0
        accepted = sum(1 for r in self._records if r.action == "accepted")
        return accepted / len(self._records)

    @property
    def count(self) -> int:
        return len(self._records)

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._records = [FeedbackRecord(**r) for r in data.get("records", [])]
            except Exception as e:
                logger.warning("Failed to load feedback history: %s", e)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(
                    {"records": [r.model_dump(mode="json") for r in self._records]},
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Failed to save feedback history: %s", e)
