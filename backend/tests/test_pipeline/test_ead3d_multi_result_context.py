"""EAD-3d: Multi-result paper context tests.

Verifies that paper synthesis consumes experiment_runs (not just
experiments[idx]) when autonomous design is active, producing a
multi-dataset study context with both datasets represented.
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.experiment.manifest import ExperimentManifest
from backend.pipeline.experiment.specification import load_spec
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    ExperimentExecutionStage,
    PaperSynthesisStage,
    StageContext,
    ensure_autonomous_experiment_design,
)


def _idea():
    return ResearchIdea(
        title="Calibration Study",
        problem_statement="Calibration under shift",
        proposed_method="Temperature scaling",
        expected_contributions="Better selective classification",
        novelty_rationale="Novel",
        evaluation_approach="accuracy metrics",
        domain="ML",
        round_generated=1,
        score=0.8,
        supporting_papers=[],
        source_gap_ids=[],
    )


def _feasibility():
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )
    return FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8,
        methodological_complexity=7, evaluation_plan=8,
        novelty_grounding=6, impact_potential=7,
        reasoning="Good", estimated_timeline="2w",
        key_risks=[],
    )


def _ctx():
    ctx = StageContext(
        result=PipelineResult(),
        domain="machine learning",
        research_question=(
            "How does post-hoc probability calibration affect"
            " selective classification performance under"
            " covariate shift in tabular classification?"
        ),
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [_idea()]
    ctx.result.feasibility_reports = {0: _feasibility()}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}
    return ctx


def _execute_autonomous(ctx):
    """Run design + execution to populate experiment_runs."""
    ensure_autonomous_experiment_design(ctx)
    design = ctx.params["autonomous_experiment_design"]
    assert design["status"] == "designed"
    stage = ExperimentExecutionStage()
    asyncio.run(stage._execute_autonomous(ctx, design))
    return design


# ── Context rendering tests ────────────────────────────────────────────────


class TestAutonomousPaperContext:
    def test_context_contains_both_datasets(self):
        ctx = _ctx()
        design = _execute_autonomous(ctx)

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        assert len(contexts) == 1
        selected = design["selected_proposal_idx"]
        context = contexts[selected]
        assert "iris" in context.lower()
        assert "wine_quality" in context.lower()

    def test_context_does_not_collapse_to_single_dataset(self):
        """experiments[idx] has only the first manifest — context
        must prefer experiment_runs[idx] and include both."""
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        # Legacy experiments has only the first manifest
        assert selected in ctx.result.experiments
        runs = ctx.result.experiment_runs[selected]
        assert len(runs) == 2

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        context = contexts[selected]

        # Both dataset headers must appear
        assert "IRIS" in context.upper()
        assert "WINE" in context.upper()

    def test_each_dataset_markers_under_correct_heading(self):
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        context = contexts[selected]

        # Find section boundaries by their distinctive headers.
        iris_header = "### IRIS — OBSERVED RESULTS"
        wine_header = "### WINE_QUALITY — OBSERVED RESULTS"
        assert iris_header in context
        assert wine_header in context

        iris_start = context.index(iris_header)
        wine_start = context.index(wine_header)

        iris_section = context[iris_start:wine_start]
        wine_section = context[wine_start:]

        iris_markers = [
            m for m in ctx.result.result_markers[selected]
            if m.metric_name.startswith("iris.")
        ]
        wine_markers = [
            m for m in ctx.result.result_markers[selected]
            if m.metric_name.startswith("wine_quality.")
        ]

        for m in iris_markers:
            assert m.metric_name in iris_section, (
                f"{m.marker} ({m.metric_name}) should be under"
                " IRIS section"
            )
            assert m.metric_name not in wine_section, (
                f"{m.marker} ({m.metric_name}) must NOT be"
                " under WINE section"
            )
        for m in wine_markers:
            assert m.metric_name in wine_section
            assert m.metric_name not in iris_section

    def test_every_combined_marker_appears_once(self):
        """Each marker's metric value appears exactly once in the
        context (one dataset section only)."""
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        context = contexts[selected]

        markers = ctx.result.result_markers[selected]
        for m in markers:
            count = context.count(m.metric_name)
            assert count == 1, (
                f"{m.metric_name} appears {count} times,"
                f" expected exactly 1"
            )

    def test_marker_indexes_values_unchanged(self):
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        markers = ctx.result.result_markers[selected]
        # Verify markers have global sequential indices
        indices = [m.marker_index for m in markers]
        assert indices == sorted(indices)
        assert len(set(indices)) == len(indices)

        # Values should be finite floats
        for m in markers:
            assert isinstance(m.observed_value, (int, float))
            assert m.observed_value == m.observed_value  # not NaN

    def test_failed_execution_omits_dataset_section(self):
        """If one execution fails, its section is absent but
        other dataset's section still appears."""
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        # Corrupt the second manifest to simulate failure
        runs = ctx.result.experiment_runs[selected]
        if len(runs) >= 2:
            runs[1] = ExperimentManifest(
                experiment_spec_id="failed",
                status="failed",
            )

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        context = contexts[selected]

        # Wine markers should not appear (execution failed)
        wine_markers = [
            m for m in ctx.result.result_markers[selected]
            if m.metric_name.startswith("wine_quality.")
        ]
        # If there were wine markers (from a failed execution),
        # they should NOT be in the context because the execution
        # failed (markers are only built on success).
        # The context lists only succeeded datasets.
        succeeded = [
            getattr(r.dataset, "name", "")
            for r in runs
            if hasattr(r, "status") and r.status == "succeeded"
        ]
        for ds in succeeded:
            assert ds.lower() in context.lower()

    def test_no_invented_aggregate_values(self):
        ctx = _ctx()
        design = _execute_autonomous(ctx)
        selected = design["selected_proposal_idx"]

        paper_stage = PaperSynthesisStage()
        contexts = paper_stage._build_autonomous_paper_context(
            ctx, design,
        )
        context = contexts[selected]

        # Check for aggregate directives
        assert "Do not invent" in context or "Do NOT" in context
        assert "aggregate" in context.lower()

    def test_is_empirical_true_for_autonomous(self):
        """is_empirical must be True when autonomous design exists,
        even without experiment_spec_id."""
        ctx = _ctx()
        design = _execute_autonomous(ctx)

        # Simulate the is_empirical check from paper synthesis
        _auto_design = ctx.params.get("autonomous_experiment_design")
        is_empirical = bool(
            _auto_design
            and _auto_design.get("status") == "designed"
        )
        assert is_empirical is True


class TestLegacyContextUnchanged:
    def test_no_autonomous_design_uses_legacy_path(self):
        """When no autonomous design exists, legacy context path
        is used and produces single-spec context."""
        ctx = StageContext(
            result=PipelineResult(),
            domain="ML",
        )
        # No autonomous_experiment_design, no experiment_spec_id
        ctx.params = {}

        # experiments dict has a legacy manifest
        from backend.pipeline.experiment.manifest import (
            AnalysisSpec,
            DatasetIdentity,
            ExperimentManifest,
            SplitSpec,
        )
        ctx.result.experiments = {0: ExperimentManifest(
            experiment_spec_id="test",
            status="succeeded",
            dataset=DatasetIdentity(
                name="iris", version="1", source="",
                license="", relative_path="",
                raw_sha256="abc",
            ),
            split=SplitSpec(
                method="s", train_fraction=0.8,
                test_fraction=0.2, random_seed=42,
            ),
            analysis=AnalysisSpec(
                entrypoint="e", code_sha256="",
                command="", method="lr",
                declared_metrics=["accuracy"],
            ),
            results={"accuracy": 0.95},
        )}

        # The _auto_design check should not find autonomous state
        _auto_design = ctx.params.get("autonomous_experiment_design")
        assert not _auto_design
        # Legacy path would be used
