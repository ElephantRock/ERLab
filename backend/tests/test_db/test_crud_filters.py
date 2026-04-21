"""Tests for server-side filtering in crud.list_ideas() (P12)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import crud
from backend.db.database import Base


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def test_list_ideas_filters_by_domain(db_session):
    """Create ideas with different domains, filter by one domain."""
    crud.create_idea(
        db_session,
        title="Idea A",
        problem_statement="Problem A",
        proposed_method="Method A",
        domain="AI/NLP",
    )
    crud.create_idea(
        db_session,
        title="Idea B",
        problem_statement="Problem B",
        proposed_method="Method B",
        domain="Computer Vision",
    )
    crud.create_idea(
        db_session,
        title="Idea C",
        problem_statement="Problem C",
        proposed_method="Method C",
        domain="AI/NLP",
    )

    results = crud.list_ideas(db_session, limit=10, domain="AI/NLP")
    assert len(results) == 2
    assert all(r.domain == "AI/NLP" for r in results)


def test_list_ideas_filters_by_min_score(db_session):
    """Create ideas with different scores, filter by min_score."""
    idea_a = crud.create_idea(
        db_session,
        title="Low Score",
        problem_statement="P",
        proposed_method="M",
    )
    idea_b = crud.create_idea(
        db_session,
        title="High Score",
        problem_statement="P",
        proposed_method="M",
    )
    crud.update_idea_scores(db_session, idea_a.id, novelty_score=0.3, feasibility_score=3.0)
    crud.update_idea_scores(db_session, idea_b.id, novelty_score=0.9, feasibility_score=9.0)

    results = crud.list_ideas(db_session, limit=10, min_score=0.7)
    assert len(results) == 1
    assert results[0].title == "High Score"


def test_list_ideas_combined_filters(db_session):
    """Test domain + min_score together."""
    idea_a = crud.create_idea(
        db_session,
        title="NLP High",
        problem_statement="P",
        proposed_method="M",
        domain="AI/NLP",
    )
    idea_b = crud.create_idea(
        db_session,
        title="NLP Low",
        problem_statement="P",
        proposed_method="M",
        domain="AI/NLP",
    )
    idea_c = crud.create_idea(
        db_session,
        title="CV High",
        problem_statement="P",
        proposed_method="M",
        domain="Computer Vision",
    )

    crud.update_idea_scores(db_session, idea_a.id, novelty_score=0.9, feasibility_score=9.0)
    crud.update_idea_scores(db_session, idea_b.id, novelty_score=0.2, feasibility_score=2.0)
    crud.update_idea_scores(db_session, idea_c.id, novelty_score=0.9, feasibility_score=9.0)

    results = crud.list_ideas(db_session, limit=10, domain="AI/NLP", min_score=0.7)
    assert len(results) == 1
    assert results[0].title == "NLP High"
