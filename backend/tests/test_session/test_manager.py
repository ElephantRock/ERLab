"""Tests for session manager — lifecycle, budget, persistence."""

import time

import pytest

from backend.pipeline.session.manager import SessionManager
from backend.pipeline.session.models import SessionBudget, SessionState


class TestSessionManager:
    def test_create_and_get(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        loaded = mgr.get(s.id)
        assert loaded is not None
        assert loaded.name == "test"
        assert loaded.state == SessionState.CREATED

    def test_get_missing_returns_none(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        assert mgr.get("nonexistent") is None

    def test_list_sessions(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        mgr.create(name="a")
        mgr.create(name="b")
        sessions = mgr.list()
        assert len(sessions) == 2

    def test_list_filter_by_state(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        mgr.create(name="a")
        active = mgr.create(name="b")
        mgr.activate(active.id)
        created_only = mgr.list(state=SessionState.CREATED)
        assert len(created_only) == 1
        assert created_only[0].name == "a"

    def test_list_filter_by_tags(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        mgr.create(name="a", tags=["ml"])
        mgr.create(name="b", tags=["nlp"])
        mgr.create(name="c", tags=["ml", "nlp"])
        ml = mgr.list(tags=["ml"])
        assert len(ml) == 2

    def test_activate(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        activated = mgr.activate(s.id)
        assert activated.state == SessionState.ACTIVE

    def test_pause_and_resume(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        mgr.activate(s.id)
        paused = mgr.pause(s.id)
        assert paused.state == SessionState.PAUSED
        resumed = mgr.resume(s.id)
        assert resumed.state == SessionState.ACTIVE

    def test_end(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        mgr.activate(s.id)
        ended = mgr.end(s.id)
        assert ended.state == SessionState.ENDED
        assert ended.ended_at is not None

    def test_invalid_transition_raises(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        with pytest.raises(ValueError, match="Cannot transition"):
            mgr.pause(s.id)  # CREATED → PAUSED not allowed

    def test_register_and_complete_run(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test")
        mgr.register_run(s.id, "run_001")
        loaded = mgr.get(s.id)
        assert loaded.run_count == 1
        assert loaded.runs[0].status == "running"

        mgr.complete_run(s.id, "run_001", tokens_used=500, cost_usd=1.5)
        loaded = mgr.get(s.id)
        assert loaded.runs[0].status == "completed"
        assert loaded.runs[0].tokens_used == 500
        assert loaded.total_cost == 1.5

    def test_check_budget(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="test", budget=SessionBudget(max_runs=2, max_total_cost_usd=10.0))
        mgr.register_run(s.id, "r1")
        mgr.complete_run(s.id, "r1", tokens_used=100, cost_usd=3.0)
        budget = mgr.check_budget(s.id)
        assert budget["remaining_runs"] == 1
        assert budget["remaining_cost"] == 7.0
        assert budget["over_budget"] is False

    def test_expire_stale(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="old")
        mgr.activate(s.id)
        # Simulate old session by backdating
        loaded = mgr.get(s.id)
        loaded.updated_at = time.time() - 100_000
        loaded.runs = []
        mgr._save(loaded)

        expired = mgr.expire_stale(max_idle_hours=1.0)
        assert s.id in expired
        assert mgr.get(s.id).state == SessionState.EXPIRED

    def test_cleanup_expired(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        s = mgr.create(name="old")
        mgr.activate(s.id)
        mgr.end(s.id)
        # Manually set to expired
        loaded = mgr.get(s.id)
        loaded.state = SessionState.EXPIRED
        loaded.ended_at = time.time() - 200_000
        mgr._save(loaded)

        cleaned = mgr.cleanup_expired(max_age_hours=1.0)
        assert s.id in cleaned

    def test_list_limit(self, tmp_path):
        mgr = SessionManager(data_dir=str(tmp_path / "sessions"))
        for i in range(5):
            mgr.create(name=f"s{i}")
        assert len(mgr.list(limit=3)) == 3
