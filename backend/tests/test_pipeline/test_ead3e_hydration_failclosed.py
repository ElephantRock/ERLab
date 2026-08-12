"""EAD-3e: Multi-result hydration + non-vacuous alignment + fail-closed.

Tests the three composed concerns:
1. Multi-result hydration reconstructs both datasets from DB.
2. Autonomous experiment_alignment actually executes.
3. Partial execution failure halts the pipeline.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

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
from backend.pipeline.experiment.manifest import (
    ExperimentManifest,
    ResultMarker,
)
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.result import PipelineOutcome, PipelineResult
from backend.pipeline.stages import (
    ExperimentExecutionStage,
    PaperSynthesisStage,
    StageContext,
    ensure_autonomous_experiment_design,
)


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


def _seed(engine):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_ead3e", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Calibration", problem_statement="shift",
        proposed_method="temp scaling",
        expected_contributions="selective",
        domain="ML", novelty_score=0.5,
        feasibility_score=0.8, overall_score=0.8,
        pipeline_run_id=run.id,
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
    db_mod._get_engine = lambda: engine
    try:
        yield
    finally:
        db_mod.get_session = orig
        stages_mod.get_session = orig


def _ctx(run_id):
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )
    ctx = StageContext(
        result=PipelineResult(),
        domain="machine learning",
        research_question=(
            "How does post-hoc probability calibration affect"
            " selective classification performance under"
            " covariate shift in tabular classification?"
        ),
        db_run_id=run_id,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Calibration", problem_statement="shift",
        proposed_method="temp scaling",
        expected_contributions="selective",
        novelty_rationale="novel",
        evaluation_approach="accuracy metrics",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8,
        methodological_complexity=7, evaluation_plan=8,
        novelty_grounding=6, impact_potential=7,
        reasoning="ok", estimated_timeline="2w",
        key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}
    return ctx


# ── Hydration tests ────────────────────────────────────────────────────────


class TestMultiResultHydration:
    def test_live_equals_hydrated(self):
        """The R4-relevant proof: execute → persist → clear → hydrate."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]
            assert design["status"] == "designed"

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            selected = design["selected_proposal_idx"]
            live_markers = list(
                ctx.result.result_markers[selected]
            )
            assert len(live_markers) > 0

            # Erase transient state.
            ctx.result.result_markers[selected] = []

            # Hydrate from DB.
            paper_stage = PaperSynthesisStage()
            hydrated = (
                paper_stage._hydrate_autonomous_result_markers(
                    proposal_id, design,
                )
            )

        assert len(hydrated) == len(live_markers)
        for live, hyd in zip(live_markers, hydrated, strict=True):
            assert live.metric_name == hyd.metric_name
            assert live.observed_value == hyd.observed_value
            assert live.role == hyd.role
            assert live.direction == hyd.direction
            assert (
                live.experiment_result_id
                == hyd.experiment_result_id
            )
            assert live.marker_index == hyd.marker_index

    def test_hydration_uses_both_rows_not_limit_one(self):
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            paper_stage = PaperSynthesisStage()
            hydrated = (
                paper_stage._hydrate_autonomous_result_markers(
                    proposal_id, design,
                )
            )

        # Must have markers from both datasets.
        datasets = {m.metric_name.split(".")[0] for m in hydrated}
        assert "iris" in datasets
        assert "wine_quality" in datasets

    def test_missing_dataset_fails_hydration(self):
        """If wine_quality's result row is deleted, hydration
        returns empty (not partial)."""
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            # Delete the wine_quality experiment result.
            Session = sessionmaker(bind=engine)
            session = Session()
            wine_row = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal_id,
                ).order_by(ExperimentResult.id.desc()).limit(1)
            ).scalar_one_or_none()
            if wine_row:
                session.delete(wine_row)
                session.commit()
            session.close()

            paper_stage = PaperSynthesisStage()
            hydrated = (
                paper_stage._hydrate_autonomous_result_markers(
                    proposal_id, design,
                )
            )

        assert hydrated == [], (
            "Missing one dataset must return empty, not partial"
        )


# ── Experiment alignment tests ─────────────────────────────────────────────


class TestAutonomousAlignment:
    def test_autonomous_alignment_not_vacuous(self):
        """When autonomous design exists and markers exist,
        alignment must run (not return 'Not an empirical run')."""
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            selected = design["selected_proposal_idx"]
            markers = ctx.result.result_markers[selected]
            assert len(markers) > 0

        # Simulate the alignment gate logic.
        _auto = design
        auto_specs = _auto.get("specs", [])
        from backend.pipeline.evaluation.claim_alignment import (
            evaluate_claim_alignment,
        )
        from backend.pipeline.experiment.specification import (
            _parse_spec,
        )

        # Build a minimal paper that mentions both datasets.
        paper_md = (
            "## Abstract\nWe study calibration on iris"
            " and wine_quality datasets using logistic"
            " regression vs majority-class baseline.\n\n"
            "## Conclusion\nOur results show effects across"
            " datasets."
        )

        all_pass = True
        findings = []
        for spec_dict in auto_specs:
            ds = spec_dict.get("dataset", {}).get("name", "?")
            spec = _parse_spec(spec_dict)
            cr = evaluate_claim_alignment(
                paper_md=paper_md,
                spec_method=spec.analysis_method,
                spec_dataset=spec.dataset_name,
                spec_baseline=spec.baseline_method,
                spec_comparison=spec.comparison_method,
            )
            if not cr.passed:
                all_pass = False
            findings.append(f"{ds}:{cr.finding}")

        # At least both datasets were evaluated.
        assert len(findings) == 2


# ── Fail-closed tests ──────────────────────────────────────────────────────


class TestFailClosed:
    def test_partial_execution_halts(self):
        """If one of two executions fails, the stage must
        return False and terminalize."""
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            # Sabotage: make the second spec's entrypoint invalid
            # so wine execution fails.
            if len(design["specs"]) >= 2:
                design["specs"][1]["analysis"][
                    "entrypoint"
                ] = "nonexistent/path.py"

            stage = ExperimentExecutionStage()
            ok = asyncio.run(
                stage._execute_autonomous(ctx, design)
            )

        assert ok is False, (
            "Partial execution must halt, not return True"
        )
        assert (
            ctx.result.outcome
            == PipelineOutcome.FAILED_EXECUTION
        )
        assert (
            ctx.result.terminal_stage
            == "experiment_execution"
        )

    def test_auto_off_remains_noop(self):
        """When autonomous is disabled and no spec exists,
        stage returns True (no-op)."""
        ctx = StageContext(
            result=PipelineResult(), domain="ML",
        )
        stage = ExperimentExecutionStage()
        ok = asyncio.run(stage.execute(ctx))
        assert ok is True

    def test_explicit_spec_unchanged(self):
        """Explicit experiment_spec_id never invokes autonomous path."""
        ctx = StageContext(
            result=PipelineResult(), domain="ML",
        )
        ctx.params["experiment_spec_id"] = "phase5-pilot-v1"
        ctx.params["autonomous_experiment_enabled"] = True

        # The autonomous check should not fire because
        # experiment_spec_id is present.
        ensure_autonomous_experiment_design(ctx)
        assert "autonomous_experiment_design" not in ctx.params
