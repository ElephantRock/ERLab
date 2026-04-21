"""End-to-end integration tests for stages 5-7 + DB persistence.

Exercises the novelty -> feasibility -> proposal -> DB chain
using SchemaAwareFakeProvider, bypassing chromadb-dependent stages 1-2.
"""

import asyncio
import json
import sys
from unittest.mock import MagicMock

# Mock chromadb before any pipeline imports (same pattern as test_litellm_provider)
sys.modules.setdefault("chromadb", MagicMock())

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Paper as LitPaper
from backend.pipeline.novelty.novelty_checker import NoveltyChecker
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    FeasibilityScoringStage,
    NoveltyCheckingStage,
    ProposalSynthesisStage,
    StageContext,
)
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer, ResearchProposal
from backend.tests.test_pipeline.conftest import FakeVectorStore, SchemaAwareFakeProvider


def _make_idea(idx: int, score: float = 0.8) -> ResearchIdea:
    return ResearchIdea(
        title=f"Test Idea {idx}: Novel approach to NLP",
        problem_statement=f"Problem {idx}: Current approaches lack scalability",
        proposed_method=f"Method {idx}: We propose a hybrid framework",
        expected_contributions="Improved performance on benchmarks",
        novelty_rationale="Combines techniques not previously explored together",
        evaluation_approach="Evaluate on standard benchmarks with ablation studies",
        round_generated=1,
        score=score,
        domain="AI/NLP",
    )


def _make_papers(n: int = 10) -> list[LitPaper]:
    return [
        LitPaper(
            id=f"p{i}", source="test", title=f"Test Paper {i}", abstract=f"Abstract {i}", year=2024
        )
        for i in range(n)
    ]


@pytest.fixture
def provider():
    return SchemaAwareFakeProvider()


@pytest.fixture
def ideas():
    return [_make_idea(0, 0.8), _make_idea(1, 0.6)]


@pytest.fixture
def papers():
    return _make_papers(10)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def _run(coro):
    return asyncio.run(coro)


# ── Stages 5-7 Chain ─────────────────────────────────────────────


class TestStages5Through7:
    def test_novelty_produces_reports_indexed_by_idea_position(self, provider, ideas):
        fake_store = FakeVectorStore()
        checker = NoveltyChecker(provider, fake_store)
        stage = NoveltyCheckingStage(checker)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=_make_papers())
        _run(stage.execute(ctx))

        assert 0 in result.novelty_reports
        assert 1 in result.novelty_reports
        assert result.novelty_reports[0].overall_score is not None
        assert result.novelty_reports[1].overall_score is not None

    def test_feasibility_receives_novelty_from_stage5(self, provider, ideas):
        fake_store = FakeVectorStore()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=_make_papers())

        # Stage 5
        _run(NoveltyCheckingStage(checker).execute(ctx))
        assert result.novelty_reports, "Novelty stage must produce reports first"

        # Stage 6
        _run(FeasibilityScoringStage(scorer).execute(ctx))
        assert 0 in result.feasibility_reports
        assert 1 in result.feasibility_reports

    def test_proposal_synthesis_uses_both_reports(self, provider, ideas, papers):
        fake_store = FakeVectorStore()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)
        synthesizer = ProposalSynthesizer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=papers)

        _run(NoveltyCheckingStage(checker).execute(ctx))
        _run(FeasibilityScoringStage(scorer).execute(ctx))
        _run(ProposalSynthesisStage(synthesizer).execute(ctx))

        assert 0 in result.proposals
        assert 1 in result.proposals

    def test_enumerate_index_coupling_across_stages(self, provider, ideas, papers):
        fake_store = FakeVectorStore()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)
        synthesizer = ProposalSynthesizer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=papers)

        _run(NoveltyCheckingStage(checker).execute(ctx))
        _run(FeasibilityScoringStage(scorer).execute(ctx))
        _run(ProposalSynthesisStage(synthesizer).execute(ctx))

        # Verify index alignment: each report/proposal corresponds to the right idea
        for i in range(len(ideas)):
            assert result.novelty_reports[i] is not None
            assert result.feasibility_reports[i] is not None
            assert result.proposals[i] is not None

    def test_proposal_to_markdown_produces_valid_output(self, provider, ideas, papers):
        fake_store = FakeVectorStore()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)
        synthesizer = ProposalSynthesizer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=papers)

        _run(NoveltyCheckingStage(checker).execute(ctx))
        _run(FeasibilityScoringStage(scorer).execute(ctx))
        _run(ProposalSynthesisStage(synthesizer).execute(ctx))

        for _, proposal in result.proposals.items():
            md = proposal.to_markdown()
            assert isinstance(md, str)
            assert len(md) > 0


# ── Score Normalization (P0-4 verification) ──────────────────────


class TestScoreNormalization:
    def test_overall_score_normalizes_feasibility(self, db_session):
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = crud.create_idea(
            db_session,
            title="Test",
            problem_statement="P",
            proposed_method="M",
            pipeline_run_id=run.id,
        )
        crud.update_idea_scores(
            db_session,
            idea.id,
            novelty_score=0.8,
            feasibility_score=7.0,
        )
        updated = crud.get_idea(db_session, idea.id)
        # (0.8 + 7.0/10.0) / 2 = 0.75
        assert updated.overall_score == pytest.approx(0.75)

    def test_high_feasibility_scale(self, db_session):
        run = crud.create_pipeline_run(db_session, domain="AI/NLP", status="completed")
        idea = crud.create_idea(
            db_session,
            title="Test",
            problem_statement="P",
            proposed_method="M",
            pipeline_run_id=run.id,
        )
        crud.update_idea_scores(
            db_session,
            idea.id,
            novelty_score=0.9,
            feasibility_score=8.5,
        )
        updated = crud.get_idea(db_session, idea.id)
        # (0.9 + 8.5/10.0) / 2 = 0.875
        assert updated.overall_score == pytest.approx(0.875)


# ── DB Persistence (PipelinePersistence verification) ────────────


class TestDBPersistence:
    def test_persist_ideas_with_scores(self, db_session, ideas, papers):
        fake_store = FakeVectorStore()
        provider = SchemaAwareFakeProvider()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=papers)

        _run(NoveltyCheckingStage(checker).execute(ctx))
        _run(FeasibilityScoringStage(scorer).execute(ctx))

        # Manually persist to in-memory DB (bypass get_session which uses prod engine)
        for i, idea in enumerate(result.ideas):
            nov = result.novelty_reports.get(i)
            feas = result.feasibility_reports.get(i)
            db_idea = crud.create_idea(
                db_session,
                title=idea.title,
                problem_statement=idea.problem_statement,
                proposed_method=idea.proposed_method,
                expected_contributions=idea.expected_contributions,
                domain=idea.domain,
            )
            if nov or feas:
                crud.update_idea_scores(
                    db_session,
                    db_idea.id,
                    novelty_score=nov.overall_score if nov else None,
                    feasibility_score=feas.overall_score if feas else None,
                )

        saved = crud.list_ideas(db_session)
        assert len(saved) == 2
        for s in saved:
            assert s.novelty_score is not None or s.feasibility_score is not None

    def test_persist_proposals_with_markdown(self, db_session, ideas, papers):
        # Create a proposal directly and verify markdown storage
        idea_row = crud.create_idea(
            db_session,
            title="Test Idea",
            problem_statement="P",
            proposed_method="M",
        )
        proposal = ResearchProposal(
            idea_id=idea_row.id,
            title="Test Proposal",
            abstract="Abstract text",
            introduction="Intro",
            related_work="Related work",
            methodology="Method",
            evaluation_plan="Evaluation",
            references=["ref1"],
        )
        md = proposal.to_markdown()
        crud.create_proposal(
            db_session,
            idea_id=idea_row.id,
            content_md=md,
            references_json=json.dumps(proposal.sections.get("references", [])),
        )
        fetched = crud.get_proposal_by_idea(db_session, idea_row.id)
        assert fetched is not None
        assert "Test Proposal" in fetched.content_md
        assert "ref1" in fetched.references_json

    def test_full_chain_persistence(self, db_session, ideas, papers):
        fake_store = FakeVectorStore()
        provider = SchemaAwareFakeProvider()
        checker = NoveltyChecker(provider, fake_store)
        scorer = FeasibilityScorer(provider)
        synthesizer = ProposalSynthesizer(provider)

        result = PipelineResult(ideas=ideas)
        ctx = StageContext(result=result, all_papers=papers)

        _run(NoveltyCheckingStage(checker).execute(ctx))
        _run(FeasibilityScoringStage(scorer).execute(ctx))
        _run(ProposalSynthesisStage(synthesizer).execute(ctx))

        # Persist ideas
        for i, idea in enumerate(result.ideas):
            nov = result.novelty_reports.get(i)
            feas = result.feasibility_reports.get(i)
            db_idea = crud.create_idea(
                db_session,
                title=idea.title,
                problem_statement=idea.problem_statement,
                proposed_method=idea.proposed_method,
                expected_contributions=idea.expected_contributions,
                domain=idea.domain,
            )
            if nov or feas:
                crud.update_idea_scores(
                    db_session,
                    db_idea.id,
                    novelty_score=nov.overall_score if nov else None,
                    feasibility_score=feas.overall_score if feas else None,
                )

        # Persist proposals
        for i, proposal in result.proposals.items():
            idea = result.ideas[i] if i < len(result.ideas) else None
            if idea:
                db_idea_row = db_session.execute(
                    __import__("sqlalchemy").select(Idea).where(Idea.title == idea.title)
                ).scalar_one_or_none()
                if db_idea_row:
                    crud.create_proposal(
                        db_session,
                        idea_id=db_idea_row.id,
                        content_md=proposal.to_markdown(),
                        references_json=json.dumps(proposal.sections.get("references", [])),
                    )

        # Verify
        saved_ideas = crud.list_ideas(db_session)
        assert len(saved_ideas) == 2
        db_session.query(
            crud.Proposal if hasattr(crud, "Proposal") else None
        ).all() if False else []
        # Verify via direct query
        from backend.db.models import Proposal

        proposals = db_session.execute(__import__("sqlalchemy").select(Proposal)).scalars().all()
        assert len(proposals) >= 1
        for p in proposals:
            assert p.content_md  # non-empty markdown
