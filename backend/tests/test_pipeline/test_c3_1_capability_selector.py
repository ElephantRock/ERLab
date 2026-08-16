"""C3-1 regression proofs: the generic capability-selection seam leaves
Case-1 behavior intact.

The seam replaces the hardcoded TABULAR_CALIBRATION_SELECTIVE_V1 in
ensure_autonomous_experiment_design() with deterministic, fail-closed
selection from the registered capability set. These tests prove, on the
frozen Case-1 input, that the produced design is equivalent to the
pre-seam behavior, and that selection fails closed on unsupported and
ambiguous inputs.
"""
from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.experiment.spec_designer import (
    TABULAR_CALIBRATION_SELECTIVE_V1,
    CapabilitySelectionError,
    SupportedCapability,
    list_supported_capabilities,
    select_capability,
)
from backend.pipeline.stages import (
    StageContext,
    ensure_autonomous_experiment_design,
)

CASE1_DOMAIN = (
    "Robust and reliable machine learning under distribution shift"
)
CASE1_QUESTION = (
    "How does post-hoc probability calibration affect selective"
    " classification performance under covariate shift in tabular"
    " classification, and are the effects consistent across datasets"
    " and shift severities?"
)


def _fake_capability(cap_id: str, signals: tuple[str, ...]) -> SupportedCapability:
    return SupportedCapability(
        task_type="classification",
        supported_metrics={"baseline_accuracy": "higher_better"},
        baseline_method="majority_class",
        comparison_method="logistic_regression",
        analysis_entrypoint="experiments/test_fixtures/exit_zero.py",
        analysis_method_description="fake capability for routing tests",
        model_family="logistic_regression",
        capability_id=cap_id,
        selection_signals=signals,
        baseline_anchor_metric="baseline_accuracy",
        family_signals=signals,
    )


class TestSelectorUnit:
    def test_frozen_case1_input_selects_calibration(self):
        cap = select_capability(f"{CASE1_QUESTION} {CASE1_DOMAIN}")
        assert cap.capability_id == "tabular_calibration_selective_v1"

    def test_unsupported_input_fails_closed(self):
        with pytest.raises(CapabilitySelectionError) as ei:
            select_capability("Protein folding structure prediction")
        assert ei.value.code == "unsupported_capability"

    def test_ambiguous_input_halts(self):
        caps = [
            _fake_capability("cap_a", ("protein",)),
            _fake_capability("cap_b", ("folding",)),
        ]
        with pytest.raises(CapabilitySelectionError) as ei:
            select_capability("Protein folding prediction", capabilities=caps)
        assert ei.value.code == "ambiguous_capability"
        assert "cap_a" in str(ei.value) and "cap_b" in str(ei.value)

    def test_registry_contains_calibration_with_seam_fields(self):
        caps = list_supported_capabilities()
        assert [c.capability_id for c in caps] == [
            "tabular_calibration_selective_v1",
        ]
        cal = caps[0]
        assert cal.selection_signals
        assert cal.baseline_anchor_metric == "baseline_accuracy"


class TestSeamEquivalenceOnCase1Input:
    def test_design_equivalent_to_pre_seam_behavior(self):
        """The frozen Case-1 input must produce the same design the
        hardcoded path produced at G0: calibration capability, iris +
        wine_quality specs, baseline anchor first, method_facts
        carried."""
        ctx = _ctx_for_case1()
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        assert design["status"] == "designed"
        assert design["capability_id"] == "tabular_calibration_selective_v1"
        spec_ids = [s["experiment_spec_id"] for s in design["specs"]]
        assert spec_ids == [
            "auto-classification-iris",
            "auto-classification-wine_quality",
        ]
        assert design["method_facts"] == dict(
            TABULAR_CALIBRATION_SELECTIVE_V1.method_facts
        )
        for spec in design["specs"]:
            assert spec["analysis"]["declared_metrics"][0] == (
                "baseline_accuracy"
            )
            assert spec["analysis"]["entrypoint"] == (
                "experiments/tabular_calibration_selective_v1/analysis.py"
            )


class TestExistingBypassesUnchanged:
    def test_explicit_spec_id_skips_autonomous_design(self):
        ctx = _ctx_for_case1()
        ctx.params["experiment_spec_id"] = "phase5-pilot-v1"
        ensure_autonomous_experiment_design(ctx)
        assert "autonomous_experiment_design" not in ctx.params

    def test_disabled_flag_is_noop(self):
        ctx = _ctx_for_case1()
        ctx.params.pop("autonomous_experiment_enabled")
        ensure_autonomous_experiment_design(ctx)
        assert "autonomous_experiment_design" not in ctx.params

    def test_idempotent_when_design_exists(self):
        ctx = _ctx_for_case1()
        ctx.params["autonomous_experiment_design"] = {"status": "designed"}
        ensure_autonomous_experiment_design(ctx)
        assert ctx.params["autonomous_experiment_design"] == {
            "status": "designed",
        }


class TestSelectionFailuresFailClosed:
    def test_unsupported_input_records_failure_design_state(self):
        ctx = _ctx_for_case1()
        ctx.research_question = "Protein folding structure prediction"
        ctx.domain = "computational biology"
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["status"] == "unsupported_capability"
        assert design["diagnostics"]
        # The executor terminalizes any non-designed status; assert the
        # wiring the executor relies on.
        assert design["status"] != "designed"


# ── fixtures ────────────────────────────────────────────────────────────────


def _ctx_for_case1() -> StageContext:
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )

    ctx = StageContext(
        result=PipelineResult(),
        domain=CASE1_DOMAIN,
        research_question=CASE1_QUESTION,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Calibration Study",
        problem_statement="calibration selective classification",
        proposed_method="temperature scaling logistic regression",
        expected_contributions="better selective classification",
        novelty_rationale="novel combination",
        evaluation_approach="accuracy calibration metrics ece aurc",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8,
        methodological_complexity=7, evaluation_plan=8,
        novelty_grounding=6, impact_potential=7,
        reasoning="ok", estimated_timeline="2w", key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}
    return ctx


class TestReviewP1Fixes:
    """C3-1 review P1s: stronger selection evidence and the
    capability-generic paper directive."""

    def test_single_broad_signal_fails_closed(self):
        # "confidence intervals for protein folding" matches only the
        # corroborating "confidence" signal — must be unsupported.
        with pytest.raises(CapabilitySelectionError) as ei:
            select_capability(
                "How should confidence intervals be estimated for"
                " protein folding? computational biology"
            )
        assert ei.value.code == "unsupported_capability"

    def test_two_corroborating_signals_select(self):
        cap = select_capability(
            "calibration and ece analysis"
        )
        assert cap.capability_id == "tabular_calibration_selective_v1"

    def test_paper_directive_is_capability_generic(self):
        # The design state carries the directive from the capability
        # contract; the calibration text is byte-stable.
        ctx = _ctx_for_case1()
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["paper_directive"] == (
            "The paper must describe the actual"
            " calibration/selective-classification"
            " capability, not a speculative method from"
            " the proposal."
        )

    def test_context_builder_uses_design_directive(self):
        from backend.pipeline.stages import PaperSynthesisStage
        marker = SimpleNamespace(status="succeeded", dataset=SimpleNamespace(name="iris"))
        from backend.pipeline.experiment.manifest import ResultMarker
        m = ResultMarker(
            marker_index=1, marker="RESULT-1",
            metric_name="iris.accuracy", observed_value=0.9,
            artifact_path="iris/metrics.json", artifact_sha256="a" * 8,
            experiment_result_id=1, direction="higher_better",
            role="comparison",
        )
        ctx = SimpleNamespace(result=SimpleNamespace(
            experiment_runs={0: [marker and SimpleNamespace(status="succeeded", dataset=SimpleNamespace(name="iris"))]},
            result_markers={0: [m]},
        ))
        design = {
            "selected_proposal_idx": 0, "research_question": "q",
            "capability_id": "c", "specs": [{"analysis": {"method": "m"}, "research_intent": {}}],
            "method_facts": {}, "paper_directive": "DIRECTIVE-MARKER-XYZ",
        }
        context = PaperSynthesisStage()._build_autonomous_paper_context(ctx, design)[0]
        assert "DIRECTIVE-MARKER-XYZ" in context

    def test_context_builder_generic_fallback(self):
        from backend.pipeline.experiment.manifest import ResultMarker
        from backend.pipeline.stages import PaperSynthesisStage
        m = ResultMarker(
            marker_index=1, marker="RESULT-1",
            metric_name="iris.accuracy", observed_value=0.9,
            artifact_path="", artifact_sha256="", experiment_result_id=1,
            direction="higher_better", role="comparison",
        )
        ctx = SimpleNamespace(result=SimpleNamespace(
            experiment_runs={0: [SimpleNamespace(status="succeeded", dataset=SimpleNamespace(name="iris"))]},
            result_markers={0: [m]},
        ))
        design = {
            "selected_proposal_idx": 0, "research_question": "q",
            "capability_id": "c", "specs": [{"analysis": {"method": "m"}, "research_intent": {}}],
        }
        context = PaperSynthesisStage()._build_autonomous_paper_context(ctx, design)[0]
        assert "executed" in context and "capability" in context
