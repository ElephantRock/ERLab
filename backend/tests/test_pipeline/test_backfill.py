"""Tests for provenance backfill — IdeaPaperLink citation population."""

import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.database import Base
from backend.db.models import Idea, Paper, Proposal, IdeaPaperLink, PipelineRun
from backend.pipeline.provenance.backfill import (
    backfill_cited_links_for_idea,
    backfill_cited_links_for_all_ideas,
)


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
def sample_run_and_idea(db_session):
    """Create a minimal run + idea + proposal with references."""
    run = PipelineRun(status="completed", domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
    db_session.add(run)
    db_session.flush()

    # Create papers that will be matched
    papers = [
        Paper(
            source_id="W111",
            title="Attention Is All You Need",
            year=2017,
            doi="10.5555/3295222.3295349",
            source="openalex",
        ),
        Paper(
            source_id="W222",
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            year=2019,
            doi="10.18653/v1/N19-1423",
            source="openalex",
        ),
        Paper(
            source_id="W333",
            title="Chain-of-Thought Prompting",
            year=2022,
            source="openalex",
        ),
    ]
    for p in papers:
        db_session.add(p)
    db_session.flush()

    idea = Idea(
        title="Test Idea for Backfill",
        domain="AI/NLP",
        problem_statement="Test problem",
        proposed_method="Test method",
        pipeline_run_id=run.id,
    )
    db_session.add(idea)
    db_session.flush()

    # Create proposal with references that will match the papers
    refs = (
        "[1] Vaswani et al. (2017). Attention Is All You Need. NeurIPS. "
        "DOI: 10.5555/3295222.3295349.  \n"
        "[2] Devlin et al. (2019). BERT: Pre-training of Deep Bidirectional Transformers. "
        "NAACL. DOI: 10.18653/v1/N19-1423.  \n"
        "[3] Wei et al. (2022). Chain-of-Thought Prompting. arXiv."
    )
    proposal = Proposal(
        idea_id=idea.id,
        content_md="# Proposal",
        references_json=refs,
    )
    db_session.add(proposal)
    db_session.commit()

    return {"run_id": run.id, "idea_id": idea.id, "paper_ids": [p.id for p in papers]}


def test_backfill_creates_cited_links(db_session, sample_run_and_idea):
    """Backfill should create IdeaPaperLink rows with role='cited'."""
    idea_id = sample_run_and_idea["idea_id"]

    result = backfill_cited_links_for_idea(db_session, idea_id)

    assert result.idea_id == idea_id
    assert result.total_refs >= 2
    assert result.resolved >= 2
    assert result.new_links >= 2
    assert result.unresolved <= 1

    # Verify links exist in DB
    links = db_session.query(IdeaPaperLink).filter_by(
        idea_id=idea_id, role="cited"
    ).all()
    assert len(links) >= 2


def test_backfill_is_idempotent(db_session, sample_run_and_idea):
    """Running backfill twice should not create duplicates."""
    idea_id = sample_run_and_idea["idea_id"]

    # First run
    result1 = backfill_cited_links_for_idea(db_session, idea_id)
    assert result1.new_links >= 2

    # Second run — all should be skipped
    result2 = backfill_cited_links_for_idea(db_session, idea_id)
    assert result2.new_links == 0
    assert result2.skipped_existing >= 2


def test_backfill_handles_no_proposal(db_session):
    """Backfill on idea without proposal should return zeros."""
    run = PipelineRun(status="completed", domain="AI/NLP", provenance_version="pre_provenance", legacy_provenance_reason="pre_gating_run")
    db_session.add(run)
    db_session.flush()

    idea = Idea(
        title="Idea Without Proposal",
        domain="AI/NLP",
        problem_statement="Test",
        proposed_method="Test",
        pipeline_run_id=run.id,
    )
    db_session.add(idea)
    db_session.commit()

    result = backfill_cited_links_for_idea(db_session, idea.id)

    assert result.idea_id == idea.id
    assert result.total_refs == 0
    assert result.resolved == 0
    assert result.new_links == 0


def test_backfill_all_ideas(db_session, sample_run_and_idea):
    """Backfill for all ideas should process every idea with a proposal."""
    results = backfill_cited_links_for_all_ideas(db_session)

    assert len(results) >= 1
    # At least one idea should have resolved links
    assert any(r.new_links > 0 for r in results)


def test_backfill_preserves_existing_supporting_links(db_session, sample_run_and_idea):
    """Backfill should not touch existing 'supporting' links."""
    idea_id = sample_run_and_idea["idea_id"]
    paper_ids = sample_run_and_idea["paper_ids"]

    # Add a supporting link manually
    db_session.add(IdeaPaperLink(
        idea_id=idea_id,
        paper_id=paper_ids[0],
        role="supporting",
    ))
    db_session.commit()

    # Backfill cited links
    result = backfill_cited_links_for_idea(db_session, idea_id)
    assert result.new_links >= 2  # Should still create cited links

    # Supporting link should still exist
    supporting = db_session.query(IdeaPaperLink).filter_by(
        idea_id=idea_id, role="supporting"
    ).all()
    assert len(supporting) == 1

    # Cited links should exist too
    cited = db_session.query(IdeaPaperLink).filter_by(
        idea_id=idea_id, role="cited"
    ).all()
    assert len(cited) >= 2
