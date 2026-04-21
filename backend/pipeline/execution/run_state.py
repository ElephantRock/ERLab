"""Run state machine for durable execution.

Tracks pipeline execution progress across stages, enabling checkpoint/resume.
Each stage gets a StageCheckpoint tracking its status. RunCheckpoint
serializes to JSON for persistence between process restarts.

Inspired by OpenAI Agents RunState serializable pause/resume.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RunState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageCheckpoint:
    """Checkpoint for a single pipeline stage."""
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "retry_count": self.retry_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageCheckpoint:
        return cls(
            stage_name=data["stage_name"],
            status=StageStatus(data.get("status", "pending")),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0),
        )


@dataclass
class RunCheckpoint:
    """Full pipeline execution checkpoint for resume after failure."""
    run_id: str
    state: RunState = RunState.PENDING
    stages: list[StageCheckpoint] = field(default_factory=list)
    domain: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def last_completed_stage_index(self) -> int:
        """Return the index of the last completed stage, or -1 if none."""
        for i in range(len(self.stages) - 1, -1, -1):
            if self.stages[i].status == StageStatus.COMPLETED:
                return i
        return -1

    def next_stage_index(self) -> int:
        """Return the index of the next stage to run."""
        for i, s in enumerate(self.stages):
            if s.status in (StageStatus.PENDING, StageStatus.FAILED):
                return i
        return len(self.stages)

    def _resolve_index(self, index: int | str) -> int:
        """Resolve a stage index (int) or stage name (str) to an integer index."""
        if isinstance(index, int):
            return index
        for i, s in enumerate(self.stages):
            if s.stage_name == index:
                return i
        raise ValueError(f"Stage not found: {index}")

    def mark_stage_running(self, index: int | str) -> None:
        idx = self._resolve_index(index)
        self.stages[idx].status = StageStatus.RUNNING
        self.stages[idx].started_at = datetime.now().isoformat()
        self._touch()

    def mark_stage_completed(self, index: int | str) -> None:
        idx = self._resolve_index(index)
        self.stages[idx].status = StageStatus.COMPLETED
        self.stages[idx].completed_at = datetime.now().isoformat()
        self._touch()

    def mark_stage_failed(self, index: int | str, error: str) -> None:
        idx = self._resolve_index(index)
        self.stages[idx].status = StageStatus.FAILED
        self.stages[idx].error = error
        self.stages[idx].retry_count += 1
        self._touch()

    def _touch(self) -> None:
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "state": self.state.value,
            "stages": [s.to_dict() for s in self.stages],
            "domain": self.domain,
            "params": self.params,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunCheckpoint:
        return cls(
            run_id=data["run_id"],
            state=RunState(data.get("state", "pending")),
            stages=[StageCheckpoint.from_dict(s) for s in data.get("stages", [])],
            domain=data.get("domain", ""),
            params=data.get("params", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> RunCheckpoint:
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def create_new(cls, run_id: str, stage_names: list[str], domain: str = "", params: dict | None = None) -> RunCheckpoint:
        """Create a new checkpoint with all stages set to PENDING."""
        return cls(
            run_id=run_id,
            state=RunState.PENDING,
            stages=[StageCheckpoint(stage_name=name) for name in stage_names],
            domain=domain,
            params=params or {},
        )
