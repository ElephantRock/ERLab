"""Tests for session data models."""

from backend.pipeline.session.models import Session, SessionBudget, SessionRunRecord, SessionState


class TestSessionState:
    def test_all_states(self):
        assert SessionState.CREATED.value == "created"
        assert SessionState.ACTIVE.value == "active"
        assert SessionState.PAUSED.value == "paused"
        assert SessionState.ENDED.value == "ended"
        assert SessionState.EXPIRED.value == "expired"
        assert SessionState.CLEANED_UP.value == "cleaned_up"


class TestSessionBudget:
    def test_defaults(self):
        b = SessionBudget()
        assert b.max_runs == 10
        assert b.max_total_cost_usd == 50.0
        assert b.max_total_tokens == 5_000_000
        assert b.max_duration_hours == 24.0

    def test_custom(self):
        b = SessionBudget(max_runs=5, max_total_cost_usd=100.0)
        assert b.max_runs == 5
        assert b.max_total_cost_usd == 100.0


class TestSession:
    def test_default_session(self):
        s = Session(name="test")
        assert s.state == SessionState.CREATED
        assert s.name == "test"
        assert s.runs == []
        assert s.id  # auto-generated

    def test_total_tokens_and_cost(self):
        s = Session(
            name="t",
            runs=[
                SessionRunRecord(run_id="r1", started_at=0, tokens_used=100, cost_usd=1.0),
                SessionRunRecord(run_id="r2", started_at=0, tokens_used=200, cost_usd=2.0),
            ],
        )
        assert s.total_tokens == 300
        assert s.total_cost == 3.0
        assert s.run_count == 2

    def test_is_over_budget_runs(self):
        s = Session(
            name="t",
            budget=SessionBudget(max_runs=2),
            runs=[
                SessionRunRecord(run_id="r1", started_at=0),
                SessionRunRecord(run_id="r2", started_at=0),
                SessionRunRecord(run_id="r3", started_at=0),
            ],
        )
        assert s.is_over_budget is True

    def test_is_over_budget_cost(self):
        s = Session(
            name="t",
            budget=SessionBudget(max_total_cost_usd=5.0),
            runs=[SessionRunRecord(run_id="r1", started_at=0, cost_usd=10.0)],
        )
        assert s.is_over_budget is True

    def test_is_within_budget(self):
        s = Session(
            name="t",
            budget=SessionBudget(max_runs=10, max_total_cost_usd=50.0),
            runs=[SessionRunRecord(run_id="r1", started_at=0, tokens_used=100, cost_usd=1.0)],
        )
        assert s.is_over_budget is False

    def test_serialization_roundtrip(self):
        s = Session(name="roundtrip", tags=["a", "b"], metadata={"key": "val"})
        json_str = s.model_dump_json()
        restored = Session.model_validate_json(json_str)
        assert restored.name == "roundtrip"
        assert restored.tags == ["a", "b"]
        assert restored.metadata == {"key": "val"}

    def test_last_activity_from_runs(self):
        s = Session(
            name="t",
            runs=[SessionRunRecord(run_id="r1", started_at=100, completed_at=200)],
        )
        assert s.last_activity() == 200

    def test_last_activity_no_runs(self):

        s = Session(name="t")
        assert s.last_activity() >= s.created_at
