"""ProgressLedger — structured quality trajectory tracking across pipeline stages."""

from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class LedgerEntry(BaseModel):
    stage: str
    round_num: int | None = None
    metric_name: str
    value: float
    threshold: float | None = None
    passed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class ProgressLedger:
    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def record(self, entry: LedgerEntry) -> None:
        self._entries.append(entry)

    def query(
        self,
        stage: str | None = None,
        metric: str | None = None,
    ) -> list[LedgerEntry]:
        results = self._entries
        if stage is not None:
            results = [e for e in results if e.stage == stage]
        if metric is not None:
            results = [e for e in results if e.metric_name == metric]
        return results

    def latest(self, metric: str) -> LedgerEntry | None:
        for entry in reversed(self._entries):
            if entry.metric_name == metric:
                return entry
        return None

    def trajectory(self, metric: str, last_n: int = 0) -> list[float]:
        values = [e.value for e in self._entries if e.metric_name == metric]
        if last_n > 0:
            values = values[-last_n:]
        return values

    def summary(self) -> dict[str, Any]:
        if not self._entries:
            return {"entry_count": 0, "metrics": [], "pass_rate": 0.0}
        metrics = sorted({e.metric_name for e in self._entries})
        passed = sum(1 for e in self._entries if e.passed)
        return {
            "entry_count": len(self._entries),
            "metrics": metrics,
            "pass_rate": passed / len(self._entries),
        }

    def reset(self) -> None:
        self._entries.clear()
