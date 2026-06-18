"""Tests for governance decision and timeline endpoints."""

import pytest
from pydantic import ValidationError

from backend.api.routes.governance import (
    GovernanceDecisionRequest,
    create_decision,
    list_decisions,
    get_timeline,
)
from backend.api.auth import TokenData
from backend.api.errors import NotFoundError
from backend.db.database import Base
from backend.db.models import Idea, Comment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    idea = Idea(
        title="Test Idea",
        problem_statement="A problem",
        proposed_method="A method",
        expected_contributions="Contributions",
        domain="test",
    )
    session.add(idea)
    session.commit()

    yield session, idea.id
    session.close()


@pytest.fixture(autouse=True)
def patch_get_session(monkeypatch, db_session):
    """Route get_session calls to our test DB."""
    session, _ = db_session

    @contextmanager
    def mock_get_session():
        yield session

    import backend.api.routes.governance as gov_mod
    monkeypatch.setattr(gov_mod, "get_session", mock_get_session)


class TestGovernanceDecisionValidation:
    """Test Pydantic validation of decision requests."""

    def test_accepts_approved(self):
        req = GovernanceDecisionRequest(decision="approved")
        assert req.decision == "approved"

    def test_accepts_denied(self):
        req = GovernanceDecisionRequest(decision="denied")
        assert req.decision == "denied"

    def test_accepts_needs_changes(self):
        req = GovernanceDecisionRequest(decision="needs_changes")
        assert req.decision == "needs_changes"

    def test_rejects_invalid_decision(self):
        with pytest.raises(ValidationError):
            GovernanceDecisionRequest(decision="maybe")

    def test_rejects_empty_decision(self):
        with pytest.raises(ValidationError):
            GovernanceDecisionRequest(decision="")

    def test_reviewer_defaults_to_none(self):
        req = GovernanceDecisionRequest(decision="approved")
        assert req.reviewer is None

    def test_note_defaults_to_none(self):
        req = GovernanceDecisionRequest(decision="approved")
        assert req.note is None


class TestCreateDecision:
    """Tests for the create_decision endpoint."""

    @pytest.mark.asyncio
    async def test_creates_decision(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="approved", note="Looks good")
        user = TokenData(username="alice")

        result = await create_decision(idea_id, req, user)

        assert result["decision"] == "approved"
        assert result["reviewer"] == "alice"
        assert result["note"] == "Looks good"
        assert result["idea_id"] == idea_id
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_reviewer_defaults_to_anonymous(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="denied")
        user = TokenData(username=None)

        result = await create_decision(idea_id, req, user)

        assert result["reviewer"] == "anonymous"

    @pytest.mark.asyncio
    async def test_reviewer_uses_auth_username(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="approved")
        user = TokenData(username="bob")

        result = await create_decision(idea_id, req, user)

        assert result["reviewer"] == "bob"

    @pytest.mark.asyncio
    async def test_reviewer_override_takes_precedence(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="approved", reviewer="override")
        user = TokenData(username="alice")

        result = await create_decision(idea_id, req, user)

        assert result["reviewer"] == "override"

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_idea(self, db_session):
        _, _ = db_session
        req = GovernanceDecisionRequest(decision="approved")
        user = TokenData(username="alice")

        with pytest.raises(NotFoundError):
            await create_decision(99999, req, user)


class TestListDecisions:
    """Tests for listing decisions."""

    @pytest.mark.asyncio
    async def test_empty_list(self, db_session):
        _, idea_id = db_session
        result = await list_decisions(idea_id)
        assert result["decisions"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_multiple_decisions_newest_first(self, db_session):
        _, idea_id = db_session

        for dec in ["needs_changes", "approved"]:
            req = GovernanceDecisionRequest(decision=dec)
            await create_decision(idea_id, req, TokenData(username="reviewer"))

        result = await list_decisions(idea_id)
        assert result["total"] == 2
        # Newest first (approved was created last)
        assert result["decisions"][0]["decision"] == "approved"
        assert result["decisions"][1]["decision"] == "needs_changes"


class TestTimeline:
    """Tests for the unified timeline."""

    @pytest.mark.asyncio
    async def test_empty_timeline(self, db_session):
        _, idea_id = db_session
        result = await get_timeline(idea_id)
        assert result["events"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_timeline_includes_decisions(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="approved", note="Good")
        await create_decision(idea_id, req, TokenData(username="alice"))

        result = await get_timeline(idea_id)

        assert result["total"] == 1
        event = result["events"][0]
        assert event["type"] == "decision"
        assert event["actor"] == "alice"
        assert event["summary"] == "Approved"
        assert event["detail"]["decision"] == "approved"

    @pytest.mark.asyncio
    async def test_timeline_includes_comments(self, db_session):
        session, idea_id = db_session
        comment = Comment(
            idea_id=idea_id,
            author="bob",
            content="This needs more detail in the methodology section.",
        )
        session.add(comment)
        session.commit()

        result = await get_timeline(idea_id)

        comment_events = [e for e in result["events"] if e["type"] == "comment"]
        assert len(comment_events) == 1
        assert comment_events[0]["actor"] == "bob"
        assert "This needs more detail" in comment_events[0]["detail"]["content_preview"]

    @pytest.mark.asyncio
    async def test_timeline_mixed_events_sorted_newest_first(self, db_session):
        session, idea_id = db_session

        # Add a comment first
        comment = Comment(
            idea_id=idea_id,
            author="alice",
            content="First comment",
        )
        session.add(comment)
        session.commit()

        # Add a decision slightly later
        import asyncio
        await asyncio.sleep(0.05)
        req = GovernanceDecisionRequest(decision="approved")
        await create_decision(idea_id, req, TokenData(username="alice"))

        result = await get_timeline(idea_id)

        assert result["total"] == 2
        # Decision (created later) should be first
        assert result["events"][0]["type"] == "decision"
        assert result["events"][1]["type"] == "comment"

    @pytest.mark.asyncio
    async def test_timeline_event_shape(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="needs_changes", note="Fix methodology")
        await create_decision(idea_id, req, TokenData(username="reviewer"))

        result = await get_timeline(idea_id)
        event = result["events"][0]

        # Verify stable discriminated union shape
        assert set(event.keys()) == {"type", "timestamp", "actor", "summary", "detail"}
        assert isinstance(event["type"], str)
        assert isinstance(event["timestamp"], str)
        assert isinstance(event["actor"], str)
        assert isinstance(event["summary"], str)
        assert isinstance(event["detail"], dict)

    @pytest.mark.asyncio
    async def test_timeline_needs_changes_summary(self, db_session):
        _, idea_id = db_session
        req = GovernanceDecisionRequest(decision="needs_changes")
        await create_decision(idea_id, req, TokenData(username="alice"))

        result = await get_timeline(idea_id)
        assert result["events"][0]["summary"] == "Needs Changes"
