"""Tests for BATCH-34 TASK-01: Comments + Sharing API routes."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Comment, Idea, SharedIdea

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_idea(db_session):
    idea = Idea(
        title="Test Idea for Collaboration",
        problem_statement="Testing comments and sharing",
        proposed_method="Unit tests",
        domain="AI/NLP",
    )
    db_session.add(idea)
    db_session.commit()
    db_session.refresh(idea)
    return idea


@contextmanager
def _session_ctx(session):
    """Mimic get_session() context manager."""
    yield session


# ── TEST-34-01-01: POST /ideas/{id}/comments adds comment ────────


@pytest.mark.anyio
async def test_34_01_01_post_comment_adds_comment(db_session, sample_idea):
    """Verify that POST /ideas/{id}/comments adds a comment to the idea."""
    from backend.api.routes.collaboration import CommentCreateRequest, add_comment

    req = CommentCreateRequest(author="alice", content="Great idea!", parent_id=None)

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea):
        result = await add_comment(sample_idea.id, req)

    assert result["author"] == "alice"
    assert result["content"] == "Great idea!"
    assert result["idea_id"] == sample_idea.id
    assert result["parent_id"] is None
    assert "id" in result
    assert "created_at" in result

    # Verify persisted
    comments = db_session.execute(select(Comment)).scalars().all()
    assert len(comments) == 1
    assert comments[0].content == "Great idea!"


# ── TEST-34-01-02: GET /ideas/{id}/comments lists comments ───────


@pytest.mark.anyio
async def test_34_01_02_get_comments_lists_comments(db_session, sample_idea):
    """Verify that GET /ideas/{id}/comments returns all comments for an idea."""
    from backend.api.routes.collaboration import list_comments

    # Seed two comments
    c1 = Comment(idea_id=sample_idea.id, author="alice", content="First comment")
    c2 = Comment(idea_id=sample_idea.id, author="bob", content="Second comment")
    db_session.add_all([c1, c2])
    db_session.commit()

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)):
        result = await list_comments(sample_idea.id)

    assert result["total"] == 2
    assert len(result["comments"]) == 2
    # Chronological order
    assert result["comments"][0]["author"] == "alice"
    assert result["comments"][1]["author"] == "bob"
    assert result["comments"][0]["content"] == "First comment"


# ── TEST-34-01-03: POST /ideas/{id}/share creates share link ────


@pytest.mark.anyio
async def test_34_01_03_post_share_creates_share_link(db_session, sample_idea):
    """Verify that POST /ideas/{id}/share generates a unique token."""
    from backend.api.routes.collaboration import create_share_link

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)), \
         patch("backend.db.crud.get_idea", return_value=sample_idea):
        result = await create_share_link(sample_idea.id)

    assert "token" in result
    assert len(result["token"]) > 10  # token_urlsafe(32) generates ~43 chars
    assert result["idea_id"] == sample_idea.id
    assert result["share_url"].startswith("/shared/")
    assert result["token"] in result["share_url"]

    # Verify persisted
    shares = db_session.execute(select(SharedIdea)).scalars().all()
    assert len(shares) == 1
    assert shares[0].idea_id == sample_idea.id


# ── TEST-34-01-04: GET /shared/{token} returns shared idea ──────


@pytest.mark.anyio
async def test_34_01_04_get_shared_idea_returns_idea(db_session, sample_idea):
    """Verify that GET /shared/{token} returns the shared idea."""
    from backend.api.routes.collaboration import get_shared_idea

    token = "test_share_token_abc123"
    shared = SharedIdea(idea_id=sample_idea.id, token=token)
    db_session.add(shared)
    db_session.commit()

    with patch("backend.db.database.get_session", return_value=_session_ctx(db_session)):
        result = await get_shared_idea(token)

    assert result["idea"]["id"] == sample_idea.id
    assert result["idea"]["title"] == "Test Idea for Collaboration"
    assert result["idea"]["domain"] == "AI/NLP"
    assert result["idea"]["problem_statement"] == "Testing comments and sharing"
    # Should NOT include proposal content (read-only share)
    assert "proposal_md" not in result["idea"]
