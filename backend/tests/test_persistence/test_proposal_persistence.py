"""Regression tests for proposal DB persistence.

Verifies that completed pipeline runs persist proposals to the database,
including sections_json with ensemble review data.
"""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.result import PipelineResult


@pytest.fixture
def mock_result_with_proposal():
    """Create a PipelineResult with ideas and proposals."""
    result = PipelineResult()
    
    # Add an idea
    from backend.pipeline.generation.models import ResearchIdea
    idea = ResearchIdea(
        title="Test Idea for Persistence",
        problem_statement="Test problem",
        proposed_method="Test method",
        expected_contributions="Test contributions",
        novelty_rationale="Test novelty",
        evaluation_approach="Test eval",
    )
    result.ideas = [idea]
    
    # Add a proposal
    from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
    proposal = ResearchProposal(
        idea_id=None,
        title="Test Proposal",
        abstract="This is a test abstract with enough words to pass basic checks.",
        proposed_method="This is a test proposed method section with adequate word count for testing.",
        ensemble_review={
            "overall_score": 0.82,
            "summary": "Strong proposal",
            "consensus_strengths": ["Good methodology"],
            "critical_weaknesses": ["Limited evaluation"],
            "actionable_suggestions": ["Add baselines"],
        },
    )
    result.proposals = {0: proposal}
    
    return result


@pytest.fixture
def temp_db():
    """Create a temporary in-memory database for testing."""
    from backend.db.models import Base
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    
    # Insert a pipeline run and idea to match against
    with Session() as session:
        from backend.db.models import PipelineRun, Idea
        run = PipelineRun(
            run_id_str="test_run_001",
            status="running",
            domain="AI/NLP",
            config_json="{}",
            # P0.2 made provenance_version NOT NULL; this is a historical
            # legacy fixture, so declare the pre-gating posture honestly.
            provenance_version="pre_provenance",
        )
        session.add(run)
        session.commit()
        run_id = run.id
        
        idea = Idea(
            title="Test Idea for Persistence",
            pipeline_run_id=run_id,
            problem_statement="Test",
            proposed_method="Test",
            expected_contributions="Test",
        )
        session.add(idea)
        session.commit()
        idea_id = idea.id
    
    yield {"engine": engine, "run_id": run_id, "idea_id": idea_id}
    engine.dispose()


class TestProposalPersistence:
    """Proposal persistence regression tests."""

    def test_persist_proposals_creates_db_row(self, mock_result_with_proposal, temp_db):
        """persist_proposals creates a Proposal row when db_run_id is provided."""
        # Patch get_session to use our temp DB
        with patch("backend.db.database.get_session") as mock_get_session:
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=temp_db["engine"])
            mock_get_session.side_effect = lambda: Session()
            
            persistence = PipelinePersistence()
            persistence.persist_proposals(mock_result_with_proposal, temp_db["run_id"])
        
        # Verify proposal was persisted
        with Session() as session:
            from backend.db.models import Proposal
            from sqlalchemy import select
            proposal = session.execute(
                select(Proposal).where(Proposal.idea_id == temp_db["idea_id"])
            ).scalar_one_or_none()
            
            assert proposal is not None, "Proposal should be persisted to DB"
            assert "Test Proposal" in proposal.content_md
            assert proposal.sections_json is not None
            
            sections = json.loads(proposal.sections_json)
            assert "ensemble_review" in sections
            assert sections["ensemble_review"]["overall_score"] == 0.82

    def test_persist_proposals_skipped_when_none(self, mock_result_with_proposal):
        """persist_proposals does nothing when db_run_id is None."""
        persistence = PipelinePersistence()
        # Should not raise even with None db_run_id
        persistence.persist_proposals(mock_result_with_proposal, None)
        # No assertion needed — just verifying no crash

    def test_persist_proposals_upsert_idempotent(self, mock_result_with_proposal, temp_db):
        """persist_proposals is idempotent — calling twice updates, doesn't duplicate."""
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=temp_db["engine"])
        
        with patch("backend.db.database.get_session") as mock_get_session:
            mock_get_session.side_effect = lambda: Session()
            
            persistence = PipelinePersistence()
            # First call creates
            persistence.persist_proposals(mock_result_with_proposal, temp_db["run_id"])
            # Second call updates (simulating finalize re-persist)
            persistence.persist_proposals(mock_result_with_proposal, temp_db["run_id"])
        
        # Verify only one proposal row
        with Session() as session:
            from backend.db.models import Proposal
            from sqlalchemy import select, func
            count = session.execute(
                select(func.count()).select_from(Proposal).where(
                    Proposal.idea_id == temp_db["idea_id"]
                )
            ).scalar()
            assert count == 1, f"Should have 1 proposal, found {count}"

    def test_persist_proposals_with_no_matching_idea(self, mock_result_with_proposal, temp_db):
        """persist_proposals gracefully handles ideas not found in DB."""
        from backend.pipeline.generation.models import ResearchIdea
        result = PipelineResult()
        result.ideas = [ResearchIdea(
            title="Nonexistent Idea",
            problem_statement="x",
            proposed_method="x",
            expected_contributions="x",
            novelty_rationale="x",
            evaluation_approach="x",
        )]
        from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal
        result.proposals = {0: ResearchProposal(title="Orphan")}
        
        with patch("backend.db.database.get_session") as mock_get_session:
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=temp_db["engine"])
            mock_get_session.side_effect = lambda: Session()
            
            persistence = PipelinePersistence()
            # Should not raise
            persistence.persist_proposals(result, temp_db["run_id"])
        
        # Verify no proposal was created
        with Session() as session:
            from backend.db.models import Proposal
            from sqlalchemy import select, func
            count = session.execute(select(func.count()).select_from(Proposal)).scalar()
            assert count == 0
