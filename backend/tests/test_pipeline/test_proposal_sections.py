"""Tests for enriched synthesis context and sections JSON persistence (P13)."""

import json
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import crud
from backend.db.database import Base
from backend.pipeline.gap_analysis.models import ResearchGap
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

# Import from conftest
from backend.tests.test_pipeline.conftest import SchemaAwareFakeProvider


class _MessageLoggingProvider(SchemaAwareFakeProvider):
    """SchemaAwareFakeProvider that also logs the messages argument."""

    def __init__(self):
        super().__init__()
        self.logged_messages: list[list[dict]] = []

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        self.logged_messages.append(messages)
        return await super().structured_output(messages, schema, temperature)


def _make_idea():
    from backend.pipeline.generation.models import ResearchIdea

    return ResearchIdea(
        title="Test Idea",
        problem_statement="A research problem to solve",
        proposed_method="A proposed method to address the problem",
        expected_contributions="Expected contributions of the work",
        novelty_rationale="Novel because reasons",
        evaluation_approach="Evaluate with benchmarks",
    )


def _get_user_prompt(provider: _MessageLoggingProvider) -> str:
    """Extract the user message content from the first logged call."""
    assert len(provider.logged_messages) >= 1, "Provider was not called"
    messages = provider.logged_messages[0]
    user_msgs = [m for m in messages if m.get("role") == "user"]
    assert len(user_msgs) >= 1, "No user message found in logged messages"
    return user_msgs[0]["content"]


# --- Tests 1-3: verify synthesis prompt contains context ---


def test_synthesize_receives_gap_descriptions():
    """Call synthesize() with gaps param, verify provider received gap text."""
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer

    provider = _MessageLoggingProvider()
    synthesizer = ProposalSynthesizer(provider)
    gaps = [
        ResearchGap(
            title="Gap in retrieval methods",
            description="No existing methods combine X and Y",
            gap_type="methodological",
            confidence=0.85,
        )
    ]

    asyncio_run(synthesizer.synthesize(_make_idea(), gaps=gaps))

    prompt_text = _get_user_prompt(provider)
    assert "Gap in retrieval methods" in prompt_text
    assert "No existing methods combine X and Y" in prompt_text


def test_synthesize_receives_closest_matches():
    """Call synthesize() with novelty report that has closest_matches, verify prompt."""
    from backend.pipeline.novelty.novelty_checker import NoveltyReport
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer

    provider = _MessageLoggingProvider()
    synthesizer = ProposalSynthesizer(provider)
    novelty = NoveltyReport(
        overall_score=0.7,
        method_novelty=0.8,
        problem_novelty=0.6,
        domain_transfer=0.5,
        combination_novelty=0.8,
        novelty_arguments="Novel combination",
        closest_matches=[
            {"title": "Prior Work on X", "distance": 0.3, "abstract": "Abstract of prior work"}
        ],
    )

    asyncio_run(synthesizer.synthesize(_make_idea(), novelty_report=novelty))

    prompt_text = _get_user_prompt(provider)
    assert "Prior Work on X" in prompt_text


def test_synthesize_receives_feasibility_reasoning():
    """Call synthesize() with feasibility report, verify prompt contains reasoning."""
    from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport
    from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer

    provider = _MessageLoggingProvider()
    synthesizer = ProposalSynthesizer(provider)
    feasibility = FeasibilityReport(
        overall_score=7.5,
        data_availability=8.0,
        computational_requirements=7.0,
        methodological_complexity=6.0,
        evaluation_plan=8.0,
        novelty_grounding=7.0,
        impact_potential=8.0,
        reasoning="Strong feasibility with available datasets and moderate compute",
        estimated_timeline="6-12 months",
        key_risks=["Data quality"],
    )

    asyncio_run(synthesizer.synthesize(_make_idea(), feasibility_report=feasibility))

    prompt_text = _get_user_prompt(provider)
    assert "Strong feasibility with available datasets" in prompt_text


# --- Test 4: sections_json persistence ---


def test_persist_proposals_stores_sections_json():
    """PipelinePersistence.persist_proposals() stores sections_json in the proposal DB record."""
    from backend.pipeline.persistence import PipelinePersistence

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    try:
        # Create a pipeline run and an idea linked to it
        db_run = crud.create_pipeline_run(session, domain="AI/NLP", status="completed")
        db_idea = crud.create_idea(
            session,
            title="Test Idea",
            problem_statement="Problem",
            proposed_method="Method",
            pipeline_run_id=db_run.id,
        )

        # Build a mock result with a proposal that has sections
        proposal = ResearchProposal(
            idea_id=db_idea.id,
            abstract="An abstract " + "word " * 60,
            introduction="An intro " + "word " * 120,
            proposed_method="A method " + "word " * 110,
            references=[{"title": "Ref 1", "doi": "10.1234/test"}],
        )

        # Mock result object
        result = MagicMock()
        result.proposals = {0: proposal}
        result.ideas = [_make_idea()]

        # Patch get_session to return our in-memory session
        with patch_session(session):
            persistence = PipelinePersistence()
            persistence.persist_proposals(result, db_run.id)

        # Verify the proposal was stored with sections_json
        db_proposal = crud.get_proposal_by_idea(session, db_idea.id)
        assert db_proposal is not None
        assert db_proposal.sections_json is not None
        sections = json.loads(db_proposal.sections_json)
        assert "abstract" in sections
        assert "proposed_method" in sections
        assert "references" in sections
    finally:
        session.close()


# --- Helpers ---


def asyncio_run(coro):
    """Helper: run an async coroutine synchronously (no @pytest.mark.asyncio)."""
    import asyncio

    return asyncio.run(coro)


def patch_session(session):
    """Return a context manager that patches get_session to yield the given session."""
    from contextlib import contextmanager
    from unittest.mock import patch

    @contextmanager
    def _fake_session():
        yield session

    return patch("backend.db.database.get_session", _fake_session)
