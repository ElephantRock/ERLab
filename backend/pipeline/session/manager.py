"""Session lifecycle manager — CRUD, state transitions, budget enforcement."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from backend.pipeline.session.models import Session, SessionBudget, SessionRunRecord, SessionState

logger = logging.getLogger(__name__)

_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.CREATED: {SessionState.ACTIVE},
    SessionState.ACTIVE: {SessionState.PAUSED, SessionState.ENDED, SessionState.EXPIRED},
    SessionState.PAUSED: {SessionState.ACTIVE, SessionState.ENDED, SessionState.EXPIRED},
    SessionState.ENDED: {SessionState.CLEANED_UP},
    SessionState.EXPIRED: {SessionState.CLEANED_UP},
    SessionState.CLEANED_UP: set(),
}


class SessionManager:
    def __init__(self, data_dir: str = "./data/sessions", hooks=None):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._hooks = hooks

    def create(
        self,
        name: str = "",
        budget: SessionBudget | None = None,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Session:
        session = Session(
            name=name or "session",
            budget=budget or SessionBudget(),
            tags=tags or [],
            metadata=metadata or {},
        )
        self._save(session)
        return session

    def get(self, session_id: str) -> Session | None:
        return self._load(session_id)

    def list(
        self,
        state: SessionState | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[Session]:
        sessions: list[Session] = []
        for path in sorted(self._dir.glob("*.json"), reverse=True):
            try:
                s = Session.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if state and s.state != state:
                continue
            if tags and not all(t in s.tags for t in tags):
                continue
            sessions.append(s)
            if len(sessions) >= limit:
                break
        return sessions

    def activate(self, session_id: str) -> Session:
        return self._transition(session_id, SessionState.ACTIVE, event="session.start")

    def pause(self, session_id: str) -> Session:
        return self._transition(session_id, SessionState.PAUSED)

    def resume(self, session_id: str) -> Session:
        return self._transition(session_id, SessionState.ACTIVE)

    def end(self, session_id: str) -> Session:
        session = self._transition(session_id, SessionState.ENDED, event="session.end")
        session.ended_at = time.time()
        self._save(session)
        return session

    def expire_stale(self, max_idle_hours: float = 48.0) -> list[str]:
        expired: list[str] = []
        cutoff = time.time() - max_idle_hours * 3600
        for session in self.list():
            if session.state in (SessionState.ACTIVE, SessionState.PAUSED):
                if session.last_activity() < cutoff:
                    try:
                        self._transition(session.id, SessionState.EXPIRED)
                        expired.append(session.id)
                    except ValueError:
                        pass
        return expired

    def cleanup_expired(self, max_age_hours: float = 168.0) -> list[str]:
        cleaned: list[str] = []
        cutoff = time.time() - max_age_hours * 3600
        for session in self.list():
            if session.state == SessionState.EXPIRED and session.ended_at and session.ended_at < cutoff:
                try:
                    self._transition(session.id, SessionState.CLEANED_UP)
                    path = self._dir / f"{session.id}.json"
                    path.unlink(missing_ok=True)
                    cleaned.append(session.id)
                except ValueError:
                    pass
        return cleaned

    def register_run(self, session_id: str, run_id: str) -> None:
        session = self._require(session_id)
        session.runs.append(SessionRunRecord(run_id=run_id, started_at=time.time()))
        session.updated_at = time.time()
        self._save(session)

    def complete_run(
        self, session_id: str, run_id: str, tokens_used: int = 0, cost_usd: float = 0.0
    ) -> None:
        session = self._require(session_id)
        for run in session.runs:
            if run.run_id == run_id:
                run.completed_at = time.time()
                run.status = "completed"
                run.tokens_used = tokens_used
                run.cost_usd = cost_usd
                break
        session.updated_at = time.time()
        self._save(session)

    def check_budget(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        b = session.budget
        return {
            "remaining_runs": max(0, b.max_runs - session.run_count),
            "remaining_cost": max(0.0, b.max_total_cost_usd - session.total_cost),
            "remaining_tokens": max(0, b.max_total_tokens - session.total_tokens),
            "remaining_hours": max(0.0, b.max_duration_hours - session.duration_hours),
            "over_budget": session.is_over_budget,
        }

    def _transition(self, session_id: str, new_state: SessionState, event: str | None = None) -> Session:
        session = self._require(session_id)
        allowed = _TRANSITIONS.get(session.state, set())
        if new_state not in allowed:
            raise ValueError(f"Cannot transition {session.state.value} → {new_state.value}")
        session.state = new_state
        session.updated_at = time.time()
        self._save(session)
        if event and self._hooks:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._hooks.dispatch(event, {"session_id": session.id, "state": new_state.value}))
            except RuntimeError:
                pass
        return session

    def _save(self, session: Session) -> None:
        path = self._dir / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    def _load(self, session_id: str) -> Session | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        return Session.model_validate_json(path.read_text(encoding="utf-8"))

    def _require(self, session_id: str) -> Session:
        session = self._load(session_id)
        if session is None:
            raise LookupError(f"Session not found: {session_id}")
        return session
