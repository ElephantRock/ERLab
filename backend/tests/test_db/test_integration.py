"""Tests for database CRUD operations and session management."""

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


class TestCrudOperations:
    def test_create_and_get_paper(self, db_session):
        paper = crud.create_paper(
            db_session,
            source_id="test-p1",
            source="semantic_scholar",
            title="Test Paper",
            abstract="Abstract text",
        )
        assert paper.id is not None
        fetched = crud.get_paper(db_session, paper.id)
        assert fetched.title == "Test Paper"

    def test_get_paper_by_source_id(self, db_session):
        crud.create_paper(
            db_session,
            source_id="ss-123",
            source="semantic_scholar",
            title="Found Paper",
        )
        found = crud.get_paper_by_source_id(db_session, "ss-123")
        assert found is not None
        assert found.title == "Found Paper"

    def test_create_pipeline_run_with_status(self, db_session):
        run = crud.create_pipeline_run(
            db_session,
            domain="AI/NLP",
            status="running",
            current_stage="literature_search",
        )
        assert run.status == "running"
        assert run.id is not None

        crud.update_pipeline_run(db_session, run.id, status="completed")
        updated = crud.get_pipeline_run(db_session, run.id)
        assert updated.status == "completed"
        assert updated.completed_at is not None

    def test_create_idea_with_scores(self, db_session):
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = crud.create_idea(
            db_session,
            title="Test Idea",
            problem_statement="A problem",
            proposed_method="A method",
            pipeline_run_id=run.id,
        )
        assert idea.id is not None

        crud.update_idea_scores(
            db_session,
            idea.id,
            novelty_score=0.8,
            feasibility_score=7.5,
        )
        updated = crud.get_idea(db_session, idea.id)
        assert updated.novelty_score == 0.8
        assert updated.feasibility_score == 7.5
        assert updated.overall_score == pytest.approx(0.775)

    def test_create_proposal(self, db_session):
        idea = crud.create_idea(
            db_session,
            title="Test Idea",
            problem_statement="Problem",
            proposed_method="Method",
        )
        crud.create_proposal(
            db_session,
            idea_id=idea.id,
            content_md="# Test Proposal",
            references_json='["ref1"]',
        )
        fetched = crud.get_proposal_by_idea(db_session, idea.id)
        assert fetched is not None
        assert fetched.content_md == "# Test Proposal"

    def test_list_ideas(self, db_session):
        for i in range(3):
            crud.create_idea(
                db_session,
                title=f"Idea {i}",
                problem_statement=f"Problem {i}",
                proposed_method=f"Method {i}",
            )
        ideas = crud.list_ideas(db_session, limit=10)
        assert len(ideas) == 3

    def test_pipeline_run_stages_tracking(self, db_session):
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="running")
        crud.update_pipeline_run(db_session, run.id, current_stage="literature_search")
        crud.update_pipeline_run(db_session, run.id, current_stage="gap_analysis")

        updated = crud.get_pipeline_run(db_session, run.id)
        import json

        stages = json.loads(updated.stages_completed)
        assert "literature_search" in stages
        assert "gap_analysis" in stages
