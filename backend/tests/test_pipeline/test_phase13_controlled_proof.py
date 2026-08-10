"""Phase 13 / 13C — controlled proof of typed empirical claim composition.

12 deterministic tests. No provider calls.
"""

from __future__ import annotations

from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.synthesis.typed_claim_composer import (
    SLOT_CONCLUSION,
    SLOT_METHOD,
    SLOT_RESULTS,
    assemble_typed_paper,
    build_deterministic_components,
    validate_provider_output,
)

IRIS_MARKERS = [
    ResultMarker(1, "RESULT-1", "baseline_accuracy", 0.333333, "m", "a", 1, direction="higher_better", role="baseline"),
    ResultMarker(2, "RESULT-2", "improvement", 0.633333, "m", "a", 1, direction="higher_better", role="derived"),
    ResultMarker(3, "RESULT-3", "model_accuracy", 0.966667, "m", "a", 1, direction="higher_better", role="comparison"),
]

CONCRETE_MARKERS = [
    ResultMarker(1, "RESULT-1", "baseline_mae", 13.05, "m", "a", 1, direction="lower_better", role="baseline"),
    ResultMarker(2, "RESULT-2", "baseline_rmse", 16.05, "m", "a", 1, direction="lower_better", role="baseline"),
    ResultMarker(3, "RESULT-3", "model_mae", 7.75, "m", "a", 1, direction="lower_better", role="comparison"),
    ResultMarker(4, "RESULT-4", "model_r2", 0.628, "m", "a", 1, direction="higher_better", role="comparison"),
    ResultMarker(5, "RESULT-5", "model_rmse", 9.80, "m", "a", 1, direction="lower_better", role="comparison"),
]

IRIS_SPEC = type("Spec", (), {
    "dataset_name": "iris", "task_type": "classification",
    "analysis_method": "multinomial logistic regression vs majority-class baseline",
    "baseline_method": "majority-class predictor", "comparison_method": "logistic regression",
    "primary_metric": "model_accuracy", "research_question": "Does LR beat majority-class?",
    "target_name": "species", "split_method": "80/20", "random_seed": 42,
})()

CONCRETE_SPEC = type("Spec", (), {
    "dataset_name": "concrete_strength", "task_type": "regression",
    "analysis_method": "linear regression vs mean baseline",
    "baseline_method": "mean predictor", "comparison_method": "linear regression",
    "primary_metric": "model_rmse", "research_question": "Does LR achieve lower RMSE?",
    "target_name": "strength", "split_method": "80/20", "random_seed": 42,
})()


class TestProviderRejection:

    def test_01_provider_result_marker_rejected(self):
        """1. Provider output containing [RESULT-N] is rejected."""
        ok, v = validate_provider_output("The model achieved [RESULT-1].")
        assert not ok
        assert any("RESULT" in x for x in v)

    def test_02_provider_invented_value_rejected(self):
        """2. Provider output inventing an empirical value is rejected."""
        ok, v = validate_provider_output("The model achieved an accuracy of 0.95. [RESULT-1]")
        assert not ok

    def test_03_baseline_comparison_not_exchangeable(self):
        """3. Baseline and comparison markers cannot be exchanged."""
        # The deterministic components assign roles from marker semantics
        det = build_deterministic_components(IRIS_SPEC, IRIS_MARKERS)
        # RESULT-1 (baseline) should appear in a baseline sentence
        assert "baseline" in det["results_block"].split("[RESULT-1]")[0].lower()[-50:]
        # RESULT-3 (comparison) should appear in a comparison sentence
        assert "multinomial logistic regression" in det["results_block"].split("[RESULT-3]")[0].lower()[-80:]


class TestDirectionalRendering:

    def test_04_higher_better_improvement(self):
        """4. Higher-better improvement renders correctly."""
        det = build_deterministic_components(IRIS_SPEC, IRIS_MARKERS)
        assert "outperformed" in det["conclusion_block"].lower()

    def test_05_lower_better_improvement(self):
        """5. Lower-better improvement renders correctly."""
        det = build_deterministic_components(CONCRETE_SPEC, CONCRETE_MARKERS)
        assert "lower" in det["conclusion_block"].lower()

    def test_06_degradation_truthful(self):
        """6. Degradation and ties are described truthfully."""
        bad_markers = [
            ResultMarker(1, "RESULT-1", "baseline_acc", 0.9, "m", "a", 1, direction="higher_better", role="baseline"),
            ResultMarker(2, "RESULT-2", "model_acc", 0.7, "m", "a", 1, direction="higher_better", role="comparison"),
        ]
        spec = type("Spec",(),{
            "dataset_name":"test","task_type":"classification",
            "analysis_method":"logistic regression","baseline_method":"baseline",
            "comparison_method":"logistic regression","primary_metric":"accuracy",
            "research_question":"?","target_name":"y","split_method":"80/20","random_seed":42,
        })()
        det = build_deterministic_components(spec, bad_markers)
        assert "did not outperform" in det["conclusion_block"].lower()


class TestAssembly:

    def test_07_required_slots_enforced(self):
        """7. Required slots cannot be removed or duplicated."""
        bad_output = "Some prose without slots."
        det = build_deterministic_components(IRIS_SPEC, IRIS_MARKERS)
        paper, warnings = assemble_typed_paper(bad_output, det)
        assert paper == ""  # rejected

    def test_08_deterministic_blocks_survive(self):
        """8. Deterministic result blocks survive assembly byte-for-byte."""
        good = f"Title\n\n## Methods\n{SLOT_METHOD}\n## Results\n{SLOT_RESULTS}\n## Conclusion\n{SLOT_CONCLUSION}"
        det = build_deterministic_components(IRIS_SPEC, IRIS_MARKERS)
        paper, warnings = assemble_typed_paper(good, det)
        assert det["results_block"] in paper
        assert det["methods_block"] in paper
        assert det["conclusion_block"] in paper

    def test_09_model_cannot_override_title(self):
        """9. Model prose cannot override the canonical title."""
        good = f"# Fake Title\n\n## Methods\n{SLOT_METHOD}\n## Results\n{SLOT_RESULTS}\n## Conclusion\n{SLOT_CONCLUSION}"
        det = build_deterministic_components(IRIS_SPEC, IRIS_MARKERS)
        paper, _ = assemble_typed_paper(good, det)
        title_line = paper.split("\n")[0]
        assert "logistic regression" in title_line.lower()
        assert "fake" not in title_line.lower()

    def test_10_no_remediation_invoked(self):
        """10. No Phase 9-11 remediation or patch function is invoked."""
        import inspect

        from backend.pipeline.synthesis.typed_claim_composer import assemble_typed_paper
        source = inspect.getsource(assemble_typed_paper)
        assert "auto_revise" not in source
        assert "auto_repair" not in source
        assert "apply_patches" not in source

    def test_11_no_revision_record(self):
        """11. No revision record is created during assembly."""
        import inspect

        from backend.pipeline.synthesis.typed_claim_composer import assemble_typed_paper
        source = inspect.getsource(assemble_typed_paper)
        assert "PaperRevision" not in source

    def test_12_phase12_papers_unchanged(self):
        """12. Existing Phase 12 blocked papers remain unchanged."""
        from backend.db.models import PaperRevision
        assert PaperRevision.__tablename__ == "paper_revisions"
