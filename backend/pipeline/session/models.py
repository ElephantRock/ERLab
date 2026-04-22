"""Session data models — lifecycle state machine, budgets, and run records."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class SessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ENDED = "ended"
    EXPIRED = "expired"
    CLEANED_UP = "cleaned_up"


class SessionBudget(BaseModel):
    max_runs: int = 10
    max_total_cost_usd: float = 50.0
    max_total_tokens: int = 5_000_000
    max_duration_hours: float = 24.0


class SessionRunRecord(BaseModel):
    run_id: str
    started_at: float
    completed_at: float | None = None
    status: str = "running"
    tokens_used: int = 0
    cost_usd: float = 0.0


class Session(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    state: SessionState = SessionState.CREATED
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    ended_at: float | None = None
    budget: SessionBudget = Field(default_factory=SessionBudget)
    runs: list[SessionRunRecord] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_used for r in self.runs)

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.runs)

    @property
    def run_count(self) -> int:
        return len(self.runs)

    @property
    def duration_hours(self) -> float:
        end = self.ended_at or time.time()
        return (end - self.created_at) / 3600.0

    @property
    def is_over_budget(self) -> bool:
        return (
            self.run_count > self.budget.max_runs
            or self.total_cost > self.budget.max_total_cost_usd
            or self.total_tokens > self.budget.max_total_tokens
            or self.duration_hours > self.budget.max_duration_hours
        )

    def last_activity(self) -> float:
        if self.runs:
            last = self.runs[-1]
            return last.completed_at or last.started_at
        return self.updated_at
