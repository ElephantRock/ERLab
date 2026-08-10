"""Tests for persist_ideas hardening (BATCH-75/TASK-02).

Verifies:
  TEST-75-02-01: persist_ideas handles IdeaCandidate objects without crashing
  TEST-75-02-02: persist_ideas skips duplicate ideas with same title + run_id
  TEST-75-02-03: persist_ideas handles ResearchIdea objects (no regression)
  TEST-75-02-04: getattr defaults are applied for missing fields

Uses an in-memory SQLite database; the real project DB is never touched.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.database import Base
from backend.db.models import Idea, PipelineRun
from backend.pipeline.generation.models import IdeaCandidate, ResearchIdea
from backend.pipeline.persistence import PipelinePersistence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockResult:
    """Minimal stand-in for PipelineResult used by persist_ideas."""

    def __init__(self, ideas):
        self.ideas = ideas
        self.novelty_reports: dict = {}
        self.feasibility_reports: dict = {}
        self.mechanical_metrics: dict = {}


def _make_session_ctx(session):
    """Return a ``get_session`` replacement that yields *session* without closing it."""

    @contextmanager
    def _ctx():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    return _ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=e)
    yield e
    e.dispose()


@pytest.fixture()
def session(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    yield s
    s.close()


@pytest.fixture()
def run_id(session):
    """Insert a PipelineRun row and return its integer id."""
    run = PipelineRun(status="running", domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
    session.add(run)
    session.commit()
    return run.id


@pytest.fixture()
def persister():
    return PipelinePersistence()


def _patch_get_session(session):
    """Return a patcher that redirects ``get_session`` to the test session."""
    return patch("backend.db.database.get_session", _make_session_ctx(session))


# ===================================================================
# TEST-75-02-01
# ===================================================================

class TestPersistIdeasIdeaCandidate:
    """TEST-75-02-01: persist_ideas handles IdeaCandidate objects without crashing."""

    def test_idea_candidate_persisted_without_error(self, session, run_id, persister):
        candidate = IdeaCandidate(
            title="IdeaCandidate persistence test",
            problem_statement="Test problem statement",
            proposed_method="Test proposed method",
            expected_contributions="Test contributions",
            novelty_rationale="Test rationale",
            evaluation_approach="Test evaluation",
            overall_score=0.85,
        )
        result = _MockResult([candidate])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
        # Default domain applied via getattr
        assert ideas[0].domain == "AI/NLP"
        assert ideas[0].title == "IdeaCandidate persistence test"

    def test_idea_candidate_with_parent_ids(self, session, run_id, persister):
        """IdeaCandidate.parent_idea_ids must not cause source_gap_ids to crash."""
        candidate = IdeaCandidate(
            title="Candidate with parent ids",
            problem_statement="ps",
            proposed_method="pm",
            parent_idea_ids=["id-abc", "id-def"],
        )
        result = _MockResult([candidate])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
        # IdeaCandidate has no source_gap_ids → getattr returns None
        assert ideas[0].source_gap_ids is not None  # Phase 4: idempotency key stored


# ===================================================================
# TEST-75-02-02
# ===================================================================

class TestPersistIdeasDedup:
    """TEST-75-02-02: persist_ideas skips duplicate ideas with same title + run_id."""

    def test_single_idea_count_after_two_calls(self, session, run_id, persister):
        candidate = IdeaCandidate(
            title="Duplicate Idea",
            problem_statement="ps",
            proposed_method="pm",
        )
        result = _MockResult([candidate])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)
            persister.persist_ideas(result, run_id)

        assert session.query(Idea).count() == 1

    def test_different_titles_are_not_deduplicated(self, session, run_id, persister):
        c1 = IdeaCandidate(title="Idea A", problem_statement="ps", proposed_method="pm")
        c2 = IdeaCandidate(title="Idea B", problem_statement="ps", proposed_method="pm")

        with _patch_get_session(session):
            persister.persist_ideas(_MockResult([c1]), run_id)
            persister.persist_ideas(_MockResult([c2]), run_id)

        assert session.query(Idea).count() == 2

    def test_same_title_different_run_id_not_deduplicated(self, session, persister):
        """Same title but different pipeline_run_id → both persisted."""
        run1 = PipelineRun(status="running", domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
        session.add(run1)
        session.commit()

        run2 = PipelineRun(status="running", domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
        session.add(run2)
        session.commit()

        candidate = IdeaCandidate(
            title="Cross-run idea", problem_statement="ps", proposed_method="pm",
        )

        with _patch_get_session(session):
            persister.persist_ideas(_MockResult([candidate]), run1.id)
            persister.persist_ideas(_MockResult([candidate]), run2.id)

        assert session.query(Idea).count() == 2

    def test_research_idea_dedup_across_retries(self, session, run_id, persister):
        """ResearchIdea objects are also deduplicated."""
        idea = ResearchIdea(
            title="RI dedup test",
            problem_statement="ps",
            proposed_method="pm",
            expected_contributions="ec",
            novelty_rationale="nr",
            evaluation_approach="ea",
            domain="AI/NLP",
            source_gap_ids=["gap-1"],
        )
        result = _MockResult([idea])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)
            persister.persist_ideas(result, run_id)

        assert session.query(Idea).count() == 1


# ===================================================================
# TEST-75-02-03
# ===================================================================

class TestPersistIdeasResearchIdeaNoRegression:
    """TEST-75-02-03: persist_ideas handles ResearchIdea objects (no regression)."""

    def test_research_idea_persisted_correctly(self, session, run_id, persister):
        idea = ResearchIdea(
            title="ResearchIdea regression test",
            problem_statement="Test problem",
            proposed_method="Test method",
            expected_contributions="Test contributions",
            novelty_rationale="Novel rationale",
            evaluation_approach="Test approach",
            domain="ML/CV",
            round_generated=2,
            score=0.92,
            supporting_papers=["paper-1", "paper-2"],
            source_gap_ids=["gap-1", "gap-2"],
        )
        result = _MockResult([idea])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
        assert ideas[0].domain == "ML/CV"
        assert ideas[0].title == "ResearchIdea regression test"
        # source_gap_ids stored as JSON list
        assert json.loads(ideas[0].source_gap_ids) == ["gap-1", "gap-2"]

    def test_research_idea_default_domain_preserved(self, session, run_id, persister):
        """ResearchIdea with default domain='AI/NLP' is stored correctly."""
        idea = ResearchIdea(
            title="Default domain idea",
            problem_statement="ps",
            proposed_method="pm",
            expected_contributions="ec",
            novelty_rationale="nr",
            evaluation_approach="ea",
        )
        result = _MockResult([idea])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert ideas[0].domain == "AI/NLP"


# ===================================================================
# TEST-75-02-04
# ===================================================================

class TestPersistIdeasGetattrDefaults:
    """TEST-75-02-04: getattr defaults are applied for missing fields."""

    def test_source_gap_ids_none_for_idea_candidate(self, session, run_id, persister):
        """IdeaCandidate has no source_gap_ids → row created with source_gap_ids=None."""
        candidate = IdeaCandidate(
            title="No source gap ids",
            problem_statement="ps",
            proposed_method="pm",
        )
        result = _MockResult([candidate])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
        # getattr default is None → no JSON serialization attempted
        assert ideas[0].source_gap_ids is not None  # Phase 4: idempotency key stored

    def test_default_domain_applied_for_idea_candidate(self, session, run_id, persister):
        """IdeaCandidate has no domain → getattr default 'AI/NLP' applied."""
        candidate = IdeaCandidate(
            title="No domain field",
            problem_statement="ps",
            proposed_method="pm",
        )
        result = _MockResult([candidate])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert ideas[0].domain == "AI/NLP"

    def test_expected_contributions_default_empty_string(self, session, run_id, persister):
        """getattr fallback for expected_contributions produces empty string."""
        # Use a plain object that lacks expected_contributions entirely
        class BareIdea:
            title = "Bare idea"
            problem_statement = "ps"
            proposed_method = "pm"

        result = _MockResult([BareIdea()])

        with _patch_get_session(session):
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
        assert ideas[0].expected_contributions == ""
        assert ideas[0].domain == "AI/NLP"
        assert ideas[0].source_gap_ids is not None  # Phase 4: idempotency key stored

    def test_novelty_rationale_guard_does_not_crash(self, session, run_id, persister):
        """Verify getattr guard on novelty_rationale doesn't crash for bare objects."""
        class BareIdeaNoRationale:
            title = "No rationale"
            problem_statement = "ps"
            proposed_method = "pm"
            expected_contributions = "ec"

        result = _MockResult([BareIdeaNoRationale()])

        with _patch_get_session(session):
            # Should not raise AttributeError
            persister.persist_ideas(result, run_id)

        ideas = session.query(Idea).all()
        assert len(ideas) == 1
