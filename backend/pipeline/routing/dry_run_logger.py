"""Dry-run logger — records routing decisions alongside actual execution.

In dry_run mode, the gateway executes the legacy provider path but logs
what the SmartRouter would have chosen. This makes it easy to compare
router recommendations against current behavior before enforcement.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.pipeline.routing.routing_decision import RoutingDecision

logger = logging.getLogger(__name__)


@dataclass
class DryRunEntry:
    """A single dry-run comparison entry."""

    timestamp: float
    stage: str
    routed_model: str
    actual_model: str
    routed_strategy: str
    actual_strategy: str
    routed_provider: str
    actual_provider: str
    decision_reason: str
    decision_warnings: list[str]
    confidence: float
    degraded: bool
    run_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "stage": self.stage,
            "routed_model": self.routed_model,
            "actual_model": self.actual_model,
            "routed_strategy": self.routed_strategy,
            "actual_strategy": self.actual_strategy,
            "routed_provider": self.routed_provider,
            "actual_provider": self.actual_provider,
            "decision_reason": self.decision_reason,
            "decision_warnings": self.decision_warnings,
            "confidence": round(self.confidence, 3),
            "degraded": self.degraded,
            "run_id": self.run_id,
        }


class DryRunLogger:
    """Logs routing decisions alongside actual execution for comparison."""

    def __init__(self, log_dir: str | Path | None = None) -> None:
        self._entries: list[DryRunEntry] = []
        self._log_dir = Path(log_dir) if log_dir else None

    def log(
        self,
        decision: RoutingDecision,
        actual_model_used: str,
        actual_strategy: str = "unknown",
        actual_provider: str = "unknown",
        run_id: str = "",
    ) -> DryRunEntry:
        """Log a routing decision alongside actual execution.

        Args:
            decision: The SmartRouter's RoutingDecision.
            actual_model_used: The model that actually executed.
            actual_strategy: The strategy actually used.
            actual_provider: The provider actually used.
            run_id: Pipeline run ID.

        Returns:
            The DryRunEntry for inspection.
        """
        entry = DryRunEntry(
            timestamp=time.time(),
            stage=decision.stage,
            routed_model=decision.model_id,
            actual_model=actual_model_used,
            routed_strategy=decision.strategy,
            actual_strategy=actual_strategy,
            routed_provider=decision.provider,
            actual_provider=actual_provider,
            decision_reason=decision.reason,
            decision_warnings=list(decision.warnings),
            confidence=decision.confidence,
            degraded=decision.degraded,
            run_id=run_id,
        )

        self._entries.append(entry)

        # Keep bounded
        if len(self._entries) > 1000:
            self._entries = self._entries[-500:]

        # Persist if log_dir configured
        if self._log_dir:
            self._persist(entry)

        return entry

    def get_log(self, stage: str = "", limit: int = 100) -> list[DryRunEntry]:
        """Get logged entries, optionally filtered by stage."""
        entries = self._entries
        if stage:
            entries = [e for e in entries if e.stage == stage]
        return entries[-limit:]

    def get_mismatches(self) -> list[DryRunEntry]:
        """Get entries where routed model != actual model."""
        return [e for e in self._entries if e.routed_model != e.actual_model]

    def _persist(self, entry: DryRunEntry) -> None:
        """Append entry to log file."""
        if not self._log_dir:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self._log_dir / "dry_run_log.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
