"""Tests for IdeaPaperLink persistence and junction table behavior."""

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.database import Base
from backend.db.models import Idea, IdeaPaperLink, Paper, PipelineRun


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
    yield session
    session.close()


@pytest.fixture
def run_and_papers(db_session):
    """Create a pipeline run with papers and an idea."""
    run = PipelineRun(domain="AI/NLP", status="completed")
    db_session.add(run)
    db_session.commit()

    papers = [
        Paper(
            source_id="sse-001",
            source="semantic_scholar",
            title="Paper One",
            year=2024,
        ),
        Paper(
            source_id="arxiv-002",
            source="arxiv",
            title="Paper Two",
            year=2023,
        ),
    ]
    for p in papers:
        db_session.add(p)
    db_session.commit()

    idea = Idea(
        title="Test Idea",
        problem_statement="Problem",
        proposed_method="Method",
        expected_contributions="Contrib",
        pipeline_run_id=run.id,
    )
    db_session.add(idea)
    db_session.commit()

    return {"run": run, "papers": papers, "idea": idea}


class TestIdeaPaperLinkModel:
    def test_table_exists(self, db_session):
        """The idea_paper_links table is created by metadata."""
        from sqlalchemy import inspect
        inspector = inspect(db_session.bind)
        assert inspector.has_table("idea_paper_links")

    def test_create_link(self, db_session, run_and_papers):
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link = IdeaPaperLink(
            idea_id=idea.id,
            paper_id=paper.id,
            role="supporting",
        )
        db_session.add(link)
        db_session.commit()

        assert link.id is not None
        assert link.role == "supporting"

    def test_unique_constraint_includes_role(self, db_session, run_and_papers):
        """Same (idea_id, paper_id) with different roles should be allowed."""
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link1 = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="supporting")
        link2 = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="cited")
        db_session.add_all([link1, link2])
        db_session.commit()

        links = db_session.execute(
            select(IdeaPaperLink).where(IdeaPaperLink.idea_id == idea.id)
        ).scalars().all()
        assert len(links) == 2

    def test_duplicate_link_rejected(self, db_session, run_and_papers):
        """Same (idea_id, paper_id, role) should be rejected."""
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link1 = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="supporting")
        db_session.add(link1)
        db_session.commit()

        link2 = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="supporting")
        db_session.add(link2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_cascade_delete_with_idea(self, db_session, run_and_papers):
        """Deleting an idea should cascade-delete its paper links."""
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="supporting")
        db_session.add(link)
        db_session.commit()
        link_id = link.id

        db_session.delete(idea)
        db_session.commit()

        # Link should be gone
        result = db_session.get(IdeaPaperLink, link_id)
        assert result is None

    def test_relationship_back_populates(self, db_session, run_and_papers):
        """idea.paper_links should return the linked papers."""
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id, role="supporting")
        db_session.add(link)
        db_session.commit()

        # Refresh the idea to load the relationship
        db_session.refresh(idea)
        assert len(idea.paper_links) == 1
        assert idea.paper_links[0].paper_id == paper.id

    def test_multiple_papers_per_idea(self, db_session, run_and_papers):
        """An idea can link to multiple papers."""
        idea = run_and_papers["idea"]
        papers = run_and_papers["papers"]

        for p in papers:
            db_session.add(IdeaPaperLink(
                idea_id=idea.id,
                paper_id=p.id,
                role="supporting",
            ))
        db_session.commit()

        db_session.refresh(idea)
        assert len(idea.paper_links) == len(papers)

    def test_default_role_is_supporting(self, db_session, run_and_papers):
        """The role column should default to 'supporting'."""
        from sqlalchemy import text
        idea = run_and_papers["idea"]
        paper = run_and_papers["papers"][0]

        link = IdeaPaperLink(idea_id=idea.id, paper_id=paper.id)
        db_session.add(link)
        db_session.commit()

        assert link.role == "supporting"
