"""EAD-3b: Autonomous design + multi-spec execution tests.

Verifies the three execution paths (legacy, no-op, autonomous) and
the autonomous multi-spec execution contract.

These tests construct a real PipelineResult with proposals, feasibility
reports, and ideas, then invoke the autonomous design + execution path
without network or DB.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    ExperimentExecutionStage,
    StageContext,
    ensure_autonomous_experiment_design,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _idea(score: float = 0.8, idx: int = 0) -> ResearchIdea:
    return ResearchIdea(
        title=f"Test Idea {idx}",
        problem_statement="Calibration under distribution shift",
        proposed_method="Logistic regression with temperature scaling",
        expected_contributions="Better selective classification",
        novelty_rationale="Novel combination",
        evaluation_approach="accuracy and calibration metrics",
        domain="machine learning",
        round_generated=1,
        score=score,
        supporting_papers=["p0"],
        source_gap_ids=["gap1"],
    )


def _feasibility(score: float = 0.8):
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )
    return FeasibilityReport(
        overall_score=score,
        data_availability=7,
        computational_requirements=8,
        methodological_complexity=7,
        evaluation_plan=8,
        novelty_grounding=6,
        impact_potential=7,
        reasoning="Good feasibility",
        estimated_timeline="2 weeks",
        key_risks=[],
    )


def _ctx_with_state(**kw) -> StageContext:
    result = PipelineResult()
    ctx = StageContext(
        result=result,
        domain="machine learning",
        research_question=(
            "How does post-hoc probability calibration affect"
            " selective classification performance under"
            " covariate shift in tabular classification?"
        ),
    )
    ctx.params.update(kw)
    return ctx


def _ctx_with_proposals(**kw):
    ctx = _ctx_with_state(**kw)
    ctx.result.ideas = [_idea()]
    ctx.result.feasibility_reports = {0: _feasibility()}
    # Minimal proposal stub
    from types import SimpleNamespace
    ctx.result.proposals = {
        0: SimpleNamespace(
            title="Test Proposal",
            to_markdown=lambda: "test",
            _idea_id=0,
        ),
    }
    return ctx


# ── Legacy path tests ──────────────────────────────────────────────────────


class TestLegacyPaths:
    def test_explicit_spec_id_does_not_invoke_designer(self):
        """When experiment_spec_id is present, autonomous design is
        never called."""
        ctx = _ctx_with_proposals(
            experiment_spec_id="phase5-pilot-v1",
            autonomous_experiment_enabled=True,
        )
        ensure_autonomous_experiment_design(ctx)
        assert "autonomous_experiment_design" not in ctx.params

    def test_no_spec_no_auto_remains_noop(self):
        """No spec + auto disabled → no design state."""
        ctx = _ctx_with_proposals()
        ensure_autonomous_experiment_design(ctx)
        assert "autonomous_experiment_design" not in ctx.params

    def test_explicit_spec_id_noop_in_stage(self):
        """Stage with explicit spec_id calls legacy path, not autonomous."""
        ctx = _ctx_with_proposals(experiment_spec_id="phase5-pilot-v1")
        stage = ExperimentExecutionStage()
        # Should not raise — it will try to execute the real spec,
        # which may fail in test env, but the dispatch is correct.
        # We just verify it doesn't enter autonomous path.
        with patch.object(
            stage, "_persist_experiment", new_callable=AsyncMock,
        ):
            # The legacy path will call execute_experiment — mock it.
            with patch(
                "backend.pipeline.experiment.empirical_runner"
                ".execute_experiment",
                new_callable=AsyncMock,
                return_value=(
                    MagicMock(status="succeeded", results={},
                              result_artifacts=[]),
                    "", "", 0, 0.1,
                ),
            ):
                ok = asyncio.run(stage.execute(ctx))
        assert ok is True


# ── Autonomous design tests ────────────────────────────────────────────────


class TestAutonomousDesign:
    def test_design_yields_two_specs(self):
        """Auto enabled → design produces iris + wine_quality specs."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params.get("autonomous_experiment_design")
        assert design is not None
        assert design["status"] == "designed"
        assert len(design["specs"]) == 2
        datasets = {
            s["dataset"]["name"] for s in design["specs"]
        }
        assert datasets == {"iris", "wine_quality"}

    def test_design_is_idempotent(self):
        """Second call does not re-run the designer."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        first = ctx.params["autonomous_experiment_design"]
        ensure_autonomous_experiment_design(ctx)
        second = ctx.params["autonomous_experiment_design"]
        assert first is second  # Same object — no re-design

    def test_design_selects_feasibility_winner(self):
        """Selected proposal matches highest feasibility score."""
        ctx = _ctx_with_state(autonomous_experiment_enabled=True)
        ctx.result.ideas = [_idea(0.7, 0), _idea(0.9, 1)]
        ctx.result.feasibility_reports = {
            0: _feasibility(0.7), 1: _feasibility(0.9),
        }
        from types import SimpleNamespace
        ctx.result.proposals = {
            0: SimpleNamespace(title="A", to_markdown=lambda: "a"),
            1: SimpleNamespace(title="B", to_markdown=lambda: "b"),
        }
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["selected_proposal_idx"] == 1

    def test_design_uses_research_question(self):
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert "calibration" in design["research_question"].lower()

    def test_design_diagnostics_exclude_regression(self):
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        concrete_diag = [
            d for d in design["diagnostics"]
            if "concrete" in d.lower()
        ]
        assert len(concrete_diag) >= 1


# ── Autonomous execution tests ─────────────────────────────────────────────


class TestAutonomousExecution:
    def test_multi_spec_execution_produces_runs_and_markers(self):
        """Auto enabled + stage execute → both datasets run."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["status"] == "designed"

        stage = ExperimentExecutionStage()
        ok = asyncio.run(stage._execute_autonomous(ctx, design))
        assert ok is True

        selected = design["selected_proposal_idx"]
        runs = ctx.result.experiment_runs.get(selected, [])
        assert len(runs) == 2, f"Expected 2 runs, got {len(runs)}"

        # Both should be succeeded (real execution on real data).
        statuses = [r.status for r in runs]
        assert all(s == "succeeded" for s in statuses), (
            f"Expected all succeeded, got {statuses}"
        )

        # Markers exist with global numbering.
        markers = ctx.result.result_markers.get(selected, [])
        assert len(markers) > 0

        # Marker indices are globally unique and sequential.
        indices = [m.marker_index for m in markers]
        assert indices == sorted(indices), (
            "Marker indices must be sorted"
        )
        assert len(set(indices)) == len(indices), (
            "Marker indices must be unique"
        )

    def test_markers_are_dataset_qualified(self):
        """Each marker's metric_name includes the dataset prefix."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        stage = ExperimentExecutionStage()
        asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        markers = ctx.result.result_markers.get(selected, [])
        datasets_in_markers = {m.metric_name.split(".")[0] for m in markers}
        assert "iris" in datasets_in_markers
        assert "wine_quality" in datasets_in_markers

    def test_legacy_experiments_populated(self):
        """First manifest is stored in legacy experiments[idx]."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        stage = ExperimentExecutionStage()
        asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        assert selected in ctx.result.experiments
        assert ctx.result.experiments[selected] is not None

    def test_no_db_writes(self):
        """EAD-3b must not write to DB — no persistence."""
        ctx = _ctx_with_proposals(
            autonomous_experiment_enabled=True,
        )
        ctx.db_run_id = None  # No DB run context
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        stage = ExperimentExecutionStage()
        asyncio.run(stage._execute_autonomous(ctx, design))
        # If we got here without DB errors, persistence was not invoked.

    def test_concrete_not_executed(self):
        """Concrete strength must never appear in experiment_runs."""
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        stage = ExperimentExecutionStage()
        asyncio.run(stage._execute_autonomous(ctx, design))

        selected = design["selected_proposal_idx"]
        runs = ctx.result.experiment_runs.get(selected, [])
        for run in runs:
            # Each run's dataset should be iris or wine_quality
            dataset = getattr(run.dataset, "name", "")
            assert dataset != "concrete_strength", (
                "Concrete must never be executed"
            )


# ── Proposal anchor tests ──────────────────────────────────────────────────


class TestProposalAnchor:
    def test_autonomous_anchor_renders(self):
        """The autonomous anchor describes both datasets."""
        from backend.pipeline.stages import (
            _build_autonomous_experiment_anchor,
        )
        ctx = _ctx_with_proposals(autonomous_experiment_enabled=True)
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        anchor = _build_autonomous_experiment_anchor(design)
        assert "iris" in anchor
        assert "wine_quality" in anchor
        assert "logistic" in anchor.lower()

    def test_anchor_empty_on_failure(self):
        from backend.pipeline.stages import (
            _build_autonomous_experiment_anchor,
        )
        anchor = _build_autonomous_experiment_anchor(
            {"status": "insufficient_compatible_datasets"}
        )
        assert anchor == ""
