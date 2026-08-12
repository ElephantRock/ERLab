"""EAD-3c: Per-execution marker persistence tests.

Verifies the durable identity chain:
  ExperimentResult A (iris) → only iris markers
  ExperimentResult B (wine) → only wine markers

Uses a real in-memory SQLite DB with seeded Idea + Proposal rows
so the persistence path can resolve real identity.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod
import backend.pipeline.stages as stages_mod
from backend.db.database import Base
from backend.db.models import (
    ExperimentResult,
    Idea,
    PipelineRun,
    Proposal,
)
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    ExperimentExecutionStage,
    StageContext,
    ensure_autonomous_experiment_design,
)

ADAPTIVE_PARAMS = {"autonomous_experiment_enabled": True}


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def _seed_run(engine) -> tuple[int, int, int]:
    """Seed PipelineRun + Idea + Proposal. Return (run_id, idea_id, proposal_id)."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_ead3c", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()

    idea = Idea(
        title="Calibration Study",
        problem_statement="Calibration under shift",
        proposed_method="Temperature scaling",
        expected_contributions="Better selective classification",
        domain="ML", novelty_score=0.5, feasibility_score=0.8,
        overall_score=0.8, pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()

    proposal = Proposal(idea_id=idea.id, content_md="test")
    session.add(proposal)
    session.commit()

    ids = (run.id, idea.id, proposal.id)
    session.close()
    return ids


@contextmanager
def _patched_session(engine):
    """Bind get_session to the test engine."""
    test_sf = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched():
        session = test_sf()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    orig = db_mod.get_session
    db_mod.get_session = patched
    stages_mod.get_session = patched
    # Patch _get_engine so ExperimentExecutionStage uses the test engine
    orig_engine = getattr(db_mod, "_get_engine", None)
    db_mod._get_engine = lambda: engine
    try:
        yield
    finally:
        db_mod.get_session = orig
        stages_mod.get_session = orig
        if orig_engine:
            db_mod._get_engine = orig_engine


def _ctx(engine, run_id: int) -> StageContext:
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )
    from types import SimpleNamespace

    result = PipelineResult()
    ctx = StageContext(
        result=result,
        domain="machine learning",
        research_question=(
            "How does post-hoc probability calibration affect"
            " selective classification performance under"
            " covariate shift in tabular classification?"
        ),
        db_run_id=run_id,
    )
    ctx.params.update(ADAPTIVE_PARAMS)

    idea = ResearchIdea(
        title="Calibration Study",
        problem_statement="Calibration under shift",
        proposed_method="Temperature scaling",
        expected_contributions="Better selective classification",
        novelty_rationale="Novel", evaluation_approach="accuracy metrics",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )
    ctx.result.ideas = [idea]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8,
        methodological_complexity=7, evaluation_plan=8,
        novelty_grounding=6, impact_potential=7,
        reasoning="Good", estimated_timeline="2w",
        key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="Test", to_markdown=lambda: "test",
    )}
    return ctx


# ── Persistence tests ──────────────────────────────────────────────────────


class TestPerExecutionPersistence:
    def test_two_experiment_rows_created(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed_run(engine)

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]
            assert design["status"] == "designed"

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            Session = sessionmaker(bind=engine)
            session = Session()
            results = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal_id,
                )
            ).scalars().all()
            session.close()

        assert len(results) == 2, (
            f"Expected 2 ExperimentResult rows, got {len(results)}"
        )

    def test_both_rows_share_proposal_and_idea(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed_run(engine)

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            Session = sessionmaker(bind=engine)
            session = Session()
            results = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal_id,
                )
            ).scalars().all()

        for row in results:
            assert row.proposal_id == proposal_id
            assert row.idea_id == idea_id

    def test_marker_ids_match_correct_experiment(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed_run(engine)

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        markers = ctx.result.result_markers.get(selected, [])

        for m in markers:
            assert m.experiment_result_id != 0, (
                f"Marker {m.marker} has experiment_result_id=0"
            )

        by_exp = {}
        for m in markers:
            by_exp.setdefault(
                m.experiment_result_id, []
            ).append(m)

        assert len(by_exp) == 2, (
            f"Expected 2 distinct experiment IDs,"
            f" got {len(by_exp)}"
        )

        for exp_id, group in by_exp.items():
            datasets = {
                m.metric_name.split(".")[0] for m in group
            }
            assert len(datasets) == 1, (
                f"Experiment {exp_id} has markers from"
                f" multiple datasets: {datasets}"
            )

    def test_inserting_wine_does_not_mutate_iris_markers(self):
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed_run(engine)

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        markers = ctx.result.result_markers.get(selected, [])

        iris_markers = [
            m for m in markers
            if m.metric_name.startswith("iris.")
        ]
        wine_markers = [
            m for m in markers
            if m.metric_name.startswith("wine_quality.")
        ]

        assert len(iris_markers) > 0
        assert len(wine_markers) > 0

        iris_exp_ids = {
            m.experiment_result_id for m in iris_markers
        }
        wine_exp_ids = {
            m.experiment_result_id for m in wine_markers
        }

        assert iris_exp_ids != wine_exp_ids, (
            "Iris and wine markers must point to different"
            " experiment result IDs"
        )
        assert len(iris_exp_ids) == 1
        assert len(wine_exp_ids) == 1

    def test_artifact_paths_are_dataset_scoped(self):
        engine = _make_engine()
        run_id, _, _ = _seed_run(engine)

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        markers = ctx.result.result_markers.get(selected, [])

        artifact_paths = {m.artifact_path for m in markers}
        assert "metrics.json" not in artifact_paths, (
            "Autonomous markers must use dataset-scoped paths"
        )
        assert any("iris/" in p for p in artifact_paths)
        assert any(
            "wine_quality/" in p for p in artifact_paths
        )

    def test_no_db_writes_without_db_run_id(self):
        """When db_run_id is absent, no persistence occurs."""
        ctx = StageContext(
            result=PipelineResult(),
            domain="ML",
            research_question="test",
        )
        ctx.params.update(ADAPTIVE_PARAMS)

        from backend.pipeline.synthesis.proposal_synthesizer import (
            FeasibilityReport,
        )
        from types import SimpleNamespace

        ctx.result.ideas = [ResearchIdea(
            title="T", problem_statement="P",
            proposed_method="M",
            expected_contributions="C",
            novelty_rationale="N",
            evaluation_approach="accuracy",
            domain="ML", round_generated=1, score=0.8,
            supporting_papers=[], source_gap_ids=[],
        )]
        ctx.result.feasibility_reports = {0: FeasibilityReport(
            overall_score=0.8, data_availability=7,
            computational_requirements=8,
            methodological_complexity=7, evaluation_plan=8,
            novelty_grounding=6, impact_potential=7,
            reasoning="ok", estimated_timeline="1w",
            key_risks=[],
        )}
        ctx.result.proposals = {0: SimpleNamespace(
            title="T", to_markdown=lambda: "t",
        )}

        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["status"] == "designed"

        stage = ExperimentExecutionStage()
        asyncio.run(stage._execute_autonomous(ctx, design))

        # Markers exist but all have experiment_result_id=0
        markers = ctx.result.result_markers.get(0, [])
        for m in markers:
            assert m.experiment_result_id == 0

    def test_resolution_failure_raises_not_silent_zero(self):
        """If no persisted Proposal exists, persistence must raise."""
        engine = _make_engine()
        run = PipelineRun(
            run_id_str="run_noprop", domain="ML", status="running",
            config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
        )
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        session = Session()
        session.add(run)
        session.commit()
        run_id = run.id
        session.close()

        from backend.pipeline.experiment.manifest import (
            AnalysisSpec,
            ExperimentManifest,
        )

        manifest = ExperimentManifest(
            experiment_spec_id="test",
            status="succeeded",
            analysis=AnalysisSpec(
                entrypoint="experiments/test/analysis.py",
                code_sha256="",
                command="python test.py",
                method="test",
                declared_metrics=["accuracy"],
            ),
        )
        stage = ExperimentExecutionStage()

        with _patched_session(engine):
            ctx = _ctx(engine, run_id)
            with pytest.raises(
                RuntimeError,
                match="Cannot resolve persisted Proposal",
            ):
                asyncio.run(stage._persist_experiment(
                    ctx, 0, manifest, "", "", 0, 0.1,
                    markers_for_execution=[],
                ))
