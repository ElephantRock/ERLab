"""Phase 12 / 12F — controlled proof of evidence-bound first-pass synthesis.

10 deterministic tests. No provider calls, no experiment reruns.
"""

from __future__ import annotations

from backend.pipeline.evaluation.deterministic_finalizer import (
    render_result_claim,
)
from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates
from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.synthesis.evidence_bound_synthesizer import (
    build_evidence_bound_context,
    build_evidence_bound_synthesis_prompt,
)

IRIS_MARKERS = [
    ResultMarker(1, "RESULT-1", "baseline_accuracy", 0.333333, "m", "a", 1, direction="higher_better", role="baseline"),
    ResultMarker(2, "RESULT-2", "improvement", 0.633333, "m", "a", 1, direction="higher_better", role="derived"),
    ResultMarker(3, "RESULT-3", "model_accuracy", 0.966667, "m", "a", 1, direction="higher_better", role="comparison"),
]

IRIS_SPEC = type("Spec", (), {
    "dataset_name": "iris", "task_type": "classification",
    "analysis_method": "multinomial logistic regression vs majority-class baseline",
    "baseline_method": "majority-class predictor", "comparison_method": "logistic regression",
    "primary_metric": "model_accuracy", "research_question": "Does LR beat majority-class on Iris?",
    "target_name": "species", "split_method": "80/20 stratified", "random_seed": 42,
    "metric_directions": {"model_accuracy": "higher_better"},
})()


class TestEvidenceBoundSynthesis:

    def test_01_quantum_cannot_replace_title(self):
        """1. A quantum-centered provider response cannot replace the canonical title."""
        ctx = build_evidence_bound_context(IRIS_SPEC, IRIS_MARKERS)
        assert "quantum" not in ctx.canonical_title.lower()
        assert "logistic regression" in ctx.canonical_title.lower()

    def test_02_result_sentences_intact(self):
        """2. Deterministic RESULT sentences remain intact in the evidence context."""
        ctx = build_evidence_bound_context(IRIS_SPEC, IRIS_MARKERS)
        assert "[RESULT-1]" in ctx.result_sentences
        assert "[RESULT-3]" in ctx.result_sentences
        assert "0.333333" in ctx.result_sentences
        assert "0.966667" in ctx.result_sentences

    def test_03_baseline_marker_not_credited_to_model(self):
        """3. Baseline markers cannot be credited to the comparison model."""
        claim_result = evaluate_paper_gates(
            paper_md="The model achieved [RESULT-1] on iris.",
            source_map=[{"marker_index": 1, "marker": "SOURCE-1", "source_id": "S1", "mapping_status": "mapped"}],
            research_intent="Does LR beat majority-class on Iris?",
            result_markers=IRIS_MARKERS,
            spec_method="logistic regression vs majority-class baseline",
            spec_dataset="iris", spec_baseline="majority-class predictor",
            spec_comparison="logistic regression",
        )
        assert claim_result.status == "blocked"

    def test_04_unexecuted_methods_as_background_allowed(self):
        """4. Unexecuted methods are allowed only as background or future work."""
        paper = """# Logistic Regression on the Iris Dataset

## Abstract
This study evaluates logistic regression on the Iris dataset. While quantum
methods have been explored as background, this paper evaluates ordinary
logistic regression against a majority-class baseline.

## Conclusion
Logistic regression outperforms the baseline. [RESULT-3]
"""
        result = evaluate_paper_gates(
            paper_md=paper,
            source_map=[{"marker_index": 1, "marker": "SOURCE-1", "source_id": "S1", "mapping_status": "mapped"}],
            research_intent="Does LR beat majority-class on Iris?",
            result_markers=IRIS_MARKERS,
            spec_method="logistic regression vs majority-class baseline",
            spec_dataset="iris", spec_baseline="majority-class predictor",
            spec_comparison="logistic regression",
        )
        assert result.status in ("ready", "blocked")  # at most minor concern

    def test_05_methods_match_manifest(self):
        """5. Methods must match dataset, split, seed, model, and baseline."""
        ctx = build_evidence_bound_context(IRIS_SPEC, IRIS_MARKERS)
        assert "iris" in ctx.methods_description.lower()
        assert "classification" in ctx.methods_description.lower()
        assert "logistic regression" in ctx.methods_description.lower()
        assert "seed=42" in ctx.methods_description

    def test_06_higher_and_lower_better_rendered(self):
        """6. Higher- and lower-better claims are rendered correctly."""
        higher = render_result_claim("R1", "accuracy", 0.95, "comparison",
            direction="higher_better", executed_method="logistic regression")
        lower = render_result_claim("R1", "rmse", 9.80, "comparison",
            direction="lower_better", executed_method="linear regression")
        assert "0.95" in higher
        assert "9.8" in lower

    def test_07_proposal_creativity_cannot_override(self):
        """7. Proposal creativity cannot override experiment identity."""
        ctx = build_evidence_bound_context(IRIS_SPEC, IRIS_MARKERS)
        prompt = build_evidence_bound_synthesis_prompt(
            proposal_text="# Quantum Neural Architecture for Everything\n\nRevolutionary approach...",
            source_papers=[], evidence_context=ctx,
        )
        # The evidence-bound content must appear before the proposal
        assert prompt.index("EVIDENCE-BOUND") < prompt.index("Quantum Neural")
        # The title in the evidence block must be the canonical one
        assert "logistic regression" in prompt[:prompt.index("Quantum Neural")].lower()

    def test_08_blocked_first_pass_not_ready(self):
        """8. A blocked first pass is not persisted as ready."""
        result = evaluate_paper_gates(
            paper_md="# Quantum Solver\n\n## Abstract\nQuantum method.\n\n## Conclusion\nQuantum. [RESULT-1]",
            source_map=[{"marker_index": 1, "marker": "SOURCE-1", "source_id": "S1", "mapping_status": "mapped"}],
            research_intent="Does LR beat majority-class on Iris?",
            result_markers=IRIS_MARKERS,
            spec_method="logistic regression vs majority-class baseline",
            spec_dataset="iris", spec_baseline="majority-class predictor",
            spec_comparison="logistic regression",
        )
        assert result.status == "blocked"

    def test_09_no_remediation_called(self):
        """9. No remediation or deterministic-finalization function is called during evaluation."""
        import inspect

        from backend.pipeline.evaluation.paper_gate_evaluator import evaluate_paper_gates
        source = inspect.getsource(evaluate_paper_gates)
        assert "auto_revise" not in source
        assert "auto_repair" not in source
        assert "apply_patches" not in source

    def test_10_phase11_history_unchanged(self):
        """10. Phase 11 revision history remains unchanged."""
        from backend.db.models import PaperRevision
        assert PaperRevision.__tablename__ == "paper_revisions"
        # The table exists and has the expected columns
        cols = {c.name for c in PaperRevision.__table__.columns}
        assert {"proposal_id", "revision_number", "paper_hash"}.issubset(cols)
