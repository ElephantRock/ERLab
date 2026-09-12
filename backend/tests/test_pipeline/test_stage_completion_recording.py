"""Commissioning remediation: honest stage recording on the run row.

``advance_stage`` historically appended every stage ENTERED to
``stages_completed`` — including stages that failed and were absorbed and
the terminal "completed"/"failed" markers. Now: entry records
``current_stage`` only; success appends via ``complete_stage``; absorbed
failures land in ``stages_failed``.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.db.database as db_database
from backend.db.models import Base, Idea, PipelineRun
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.result import PipelineResult


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def override_get_session(monkeypatch, session_factory):
    import contextlib

    @contextlib.contextmanager
    def _fake_get_session():
        yield session_factory()

    monkeypatch.setattr(db_database, "get_session", _fake_get_session)
    return session_factory


def _make_run(session_factory, *, domain: str = "AI/NLP") -> int:
    with session_factory() as session:
        run = PipelineRun(
            status="running",
            domain=domain,
            provenance_version="provenance_v1",
        )
        session.add(run)
        session.commit()
        return run.id


class TestHonestStageRecording:
    def test_entry_records_current_stage_only(self, override_get_session):
        run_id = _make_run(override_get_session)
        persistence = PipelinePersistence()

        persistence.set_current_stage(run_id, "novelty_checking")

        with override_get_session() as session:
            run = session.get(PipelineRun, run_id)
            assert run.current_stage == "novelty_checking"
            assert run.stages_completed == "[]"

    def test_complete_stage_appends_on_success(self, override_get_session):
        run_id = _make_run(override_get_session)
        persistence = PipelinePersistence()

        persistence.set_current_stage(run_id, "gap_analysis")
        persistence.complete_stage(run_id, "gap_analysis")

        with override_get_session() as session:
            run = session.get(PipelineRun, run_id)
            assert run.stages_completed == '["gap_analysis"]'

    def test_fail_stage_records_error_not_completion(self, override_get_session):
        run_id = _make_run(override_get_session)
        persistence = PipelinePersistence()

        persistence.set_current_stage(run_id, "novelty_checking")
        persistence.fail_stage(run_id, "novelty_checking", "governed runtime unavailable")

        with override_get_session() as session:
            run = session.get(PipelineRun, run_id)
            assert run.stages_completed == "[]"
            failed = __import__("json").loads(run.stages_failed)
            assert failed == [
                {"stage": "novelty_checking", "error": "governed runtime unavailable"}
            ]

    def test_advance_alias_no_longer_pollutes_completed(self, override_get_session):
        run_id = _make_run(override_get_session)
        persistence = PipelinePersistence()

        persistence.advance_stage(run_id, "paper_synthesis")

        with override_get_session() as session:
            run = session.get(PipelineRun, run_id)
            assert run.current_stage == "paper_synthesis"
            assert run.stages_completed == "[]"


class TestIdeaDomainInheritance:
    def test_tree_conversion_stamps_run_domain(self):
        """Idea creation stamps the run's domain (authoritative provenance)."""
        from types import SimpleNamespace

        from backend.pipeline.stages import TreeSearchStage

        candidates = [
            SimpleNamespace(
                title="Cognitive Linearizability",
                problem_statement="p",
                proposed_method="m",
                overall_score=5.0,
            )
        ]
        ideas = TreeSearchStage._convert_to_research_ideas(
            candidates, domain="LLM memory systems, databases"
        )
        assert ideas[0].domain == "LLM memory systems, databases"

    def test_persistence_preserves_explicit_idea_domain(self, override_get_session):
        run_id = _make_run(override_get_session, domain="AI/NLP")
        persistence = PipelinePersistence()

        result = PipelineResult()
        result.ideas = [
            ResearchIdea(
                title="AgentLog",
                problem_statement="p",
                proposed_method="m",
                expected_contributions="c",
                novelty_rationale="n",
                evaluation_approach="e",
                domain="storage systems",
            )
        ]
        persistence.persist_ideas(result, run_id)

        with override_get_session() as session:
            idea = session.query(Idea).filter(Idea.pipeline_run_id == run_id).one()
            assert idea.domain == "storage systems"
