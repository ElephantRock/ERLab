"""EAD-4A: Controlled composed lifecycle proof.

Chains the real EAD components through the full path without a live
model run. Uses real registered datasets, real entrypoint, real SQLite
persistence, real SpecDesigner, and real R4 assurance machinery.

Paper generation is replaced by a deterministic test paper that embeds
the authoritative result markers verbatim.

Proves the success path AND the failure branch.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

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
        run_id_str="run_ead4a", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Calibration under shift",
        problem_statement="calibration selective classification",
        proposed_method="temperature scaling logistic regression",
        expected_contributions="better selective classification",
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
            "How does post-hoc probability calibration"
            " affect selective classification performance"
            " under covariate shift in tabular"
            " classification?"
        ),
        db_run_id=run_id,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Calibration under shift",
        problem_statement="calibration selective classification",
        proposed_method="temperature scaling logistic regression",
        expected_contributions="better selective classification",
        novelty_rationale="novel combination",
        evaluation_approach="accuracy calibration metrics",
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


def _build_test_paper(markers, design_state):
    """Build a deterministic paper that embeds result markers."""
    lines = [
        "# Calibration Effects on Selective Classification",
        "",
        "## Abstract",
        "",
        "We study post-hoc probability calibration effects"
        " on selective classification under covariate shift.",
        "Using logistic regression with temperature scaling"
        " vs majority-class baseline on iris and wine_quality",
        "datasets, we report accuracy, ECE, and AURC across",
        "four shift severities.",
        "",
        "## Method",
        "",
        "Logistic regression (one-vs-rest) with post-hoc"
        " calibration (sigmoid/isotonic) vs majority-class",
        "baseline. Fixed covariate-shift severities:",
        "0.0, 0.25, 0.5, 0.75.",
        "",
        "## Observed Results",
        "",
    ]
    for m in markers:
        lines.append(
            f"{m.observed_value} [{m.marker}]"
        )
    lines.extend([
        "",
        "## Conclusion",
        "",
        "Our results show calibration effects across"
        " datasets and shift severities.",
    ])
    return "\n".join(lines)


# ── Success path ──────────────────────────────────────────────────────────


class TestComposedSuccessLifecycle:
    def test_full_lifecycle_success(self):
        """End-to-end: design → execute → persist → context →
        evaluate → hydrate → re-evaluate."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)

            # 1. Autonomous design (before proposal synthesis).
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]
            assert design["status"] == "designed"
            assert len(design["specs"]) == 2

            # 2. Real execution.
            stage = ExperimentExecutionStage()
            ok = asyncio.run(
                stage._execute_autonomous(ctx, design)
            )
            assert ok is True

            selected = design["selected_proposal_idx"]
            runs = ctx.result.experiment_runs[selected]
            assert len(runs) == 2
            assert all(r.status == "succeeded" for r in runs)

            # 3. Durable evidence check.
            Session = sessionmaker(bind=engine)
            session = Session()
            db_results = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal_id
                )
            ).scalars().all()
            assert len(db_results) == 2
            for row in db_results:
                assert row.idea_id == idea_id
                assert row.proposal_id == proposal_id
                assert row.success is True
            session.close()

            # 4. Markers are dataset-qualified.
            live_markers = ctx.result.result_markers[selected]
            assert len(live_markers) > 0
            datasets = {
                m.metric_name.split(".")[0]
                for m in live_markers
            }
            assert datasets == {"iris", "wine_quality"}

            # 5. Paper context contains both datasets.
            paper_stage = PaperSynthesisStage()
            contexts = (
                paper_stage._build_autonomous_paper_context(
                    ctx, design
                )
            )
            context = contexts[selected]
            assert "iris" in context.lower()
            assert "wine_quality" in context.lower()

            # 6. Build deterministic paper from markers.
            paper_md = _build_test_paper(
                live_markers, design
            )

            # 7. First evaluation.
            metadata = {"full_paper": {"paper_markdown": paper_md}}
            proposal_obj = SimpleNamespace(
                paper_md=paper_md,
                metadata=metadata,
            )
            ctx.result.proposals[selected] = proposal_obj

            # Mock the provider and dimension evaluator: a real provider
            # needs EROCK_OPENAI_API_KEY, which CI does not have. The
            # gates still run for real against the markers and design
            # state — only the LLM dimension scores are stubbed.
            from unittest.mock import AsyncMock as _AsyncMock
            from unittest.mock import MagicMock as _MagicMock
            from unittest.mock import patch as _patch

            fake_evaluator = _MagicMock()
            fake_evaluator.evaluate = _AsyncMock(
                return_value=_MagicMock(
                    to_dict=lambda: {},
                ),
            )
            eval_stage = PaperSynthesisStage(
                provider=_MagicMock(),
            )
            eval_ctx = StageContext(
                result=ctx.result,
                domain=ctx.domain,
                db_run_id=run_id,
                params=ctx.params,
                run_id="run_ead4a",
            )
            with _patch(
                "backend.pipeline.evaluation."
                "proposal_evaluator.ProposalEvaluator",
                return_value=fake_evaluator,
            ):
                asyncio.run(eval_stage._evaluate_paper(
                    eval_ctx, proposal_obj, metadata, selected,
                ))

            eval_result = metadata.get(
                "paper_evaluation", {}
            )
            assert eval_result.get("status") in (
                "ready", "blocked",
            )
            gates = {
                g["gate"]: g
                for g in eval_result.get("gates", [])
            }

            # experiment_alignment must be non-vacuous.
            if "experiment_alignment" in gates:
                reason = gates["experiment_alignment"].get(
                    "reason", ""
                )
                assert reason != "Not an empirical run", (
                    "Alignment must not be vacuous"
                )

            # numeric_fidelity must receive markers.
            if "numeric_fidelity" in gates:
                fid_reason = gates[
                    "numeric_fidelity"
                ].get("reason", "")
                assert "validated" in fid_reason or (
                    "No RESULT" not in fid_reason
                ), (
                    "numeric_fidelity should have markers"
                )

            # 8. Hydration equivalence.
            ctx.result.result_markers[selected] = []
            hydrated = (
                paper_stage
                ._hydrate_autonomous_result_markers(
                    proposal_id, design,
                )
            )
            assert len(hydrated) == len(live_markers)
            for live, hyd in zip(
                live_markers, hydrated, strict=True
            ):
                assert (
                    live.metric_name == hyd.metric_name
                )
                assert (
                    live.observed_value
                    == hyd.observed_value
                )
                assert live.role == hyd.role
                assert live.marker_index == hyd.marker_index

    def test_live_equals_hydrated_exact(self):
        """Stronger: field-by-field equality."""
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]
            stage = ExperimentExecutionStage()
            asyncio.run(stage._execute_autonomous(ctx, design))

            selected = design["selected_proposal_idx"]
            live = list(ctx.result.result_markers[selected])

            ctx.result.result_markers[selected] = []

            paper_stage = PaperSynthesisStage()
            hydrated = (
                paper_stage
                ._hydrate_autonomous_result_markers(
                    proposal_id, design,
                )
            )

        assert len(live) == len(hydrated)
        for i, (lm, hm) in enumerate(
            zip(live, hydrated, strict=True)
        ):
            assert lm.marker == hm.marker, (
                f"idx {i}: {lm.marker} != {hm.marker}"
            )
            assert lm.metric_name == hm.metric_name
            assert lm.observed_value == hm.observed_value
            assert lm.role == hm.role
            assert lm.direction == hm.direction
            assert (
                lm.experiment_result_id
                == hm.experiment_result_id
            )


# ── Failure branch ────────────────────────────────────────────────────────


class TestComposedFailureLifecycle:
    def test_partial_failure_halts_pipeline(self):
        """iris succeeds + wine fails → FAILED_EXECUTION."""
        engine = _make_engine()
        run_id, _, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]

            # Sabotage wine entrypoint.
            design["specs"][1]["analysis"][
                "entrypoint"
            ] = "experiments/nonexistent/analysis.py"

            stage = ExperimentExecutionStage()
            ok = asyncio.run(
                stage._execute_autonomous(ctx, design)
            )

        assert ok is False
        assert (
            ctx.result.outcome
            == PipelineOutcome.FAILED_EXECUTION
        )
        assert (
            ctx.result.terminal_stage
            == "experiment_execution"
        )
        assert ctx.result.terminal_reason
        assert "incomplete" in ctx.result.terminal_reason.lower()


# ── Legacy compatibility ──────────────────────────────────────────────────


class TestLegacyCompatibility:
    def test_auto_off_remains_noop(self):
        ctx = StageContext(
            result=PipelineResult(), domain="ML",
        )
        stage = ExperimentExecutionStage()
        ok = asyncio.run(stage.execute(ctx))
        assert ok is True

    def test_explicit_spec_path_unaffected(self):
        ctx = StageContext(
            result=PipelineResult(), domain="ML",
        )
        ctx.params["experiment_spec_id"] = "phase5-pilot-v1"
        ctx.params["autonomous_experiment_enabled"] = True
        ensure_autonomous_experiment_design(ctx)
        assert (
            "autonomous_experiment_design"
            not in ctx.params
        )
