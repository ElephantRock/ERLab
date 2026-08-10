"""Phase 4 / WP-4D/4E/4F tests — provenance-aware evaluation gating.

The Phase 3 false-confidence defect: the paper evaluator reported status='ready'
on all 6 papers despite zero bibliography, missing provenance, scope drift, and
conclusion overreach. These tests pin the remediation:

  4D — missing/unmapped provenance blocks a positive paper-evaluation result.
       Artifact generation remains accessible (paper.status='ready' is separate).
  4E — a materially off-scope paper cannot be evaluated as quality-ready.
  4F — an overstated conclusion cannot be evaluated as quality-ready.

The gate lives in _evaluate_paper (the thin adapter), reusing the existing
ProposalEvaluator. paper.status (artifact generation) and paper_evaluation
(quality state) remain distinct.
"""


from backend.pipeline.stages import PaperSynthesisStage


class TestProvenanceGate:
    """4D — the provenance precondition that blocks false 'ready'."""

    def test_paper_with_markers_but_no_map_is_not_ready(self):
        """A paper citing [SOURCE-N] with no persisted map fails the precondition."""
        gate = PaperSynthesisStage.provenance_precondition(
            paper_markdown="Body citing [SOURCE-1] and [SOURCE-2].",
            source_map=[],  # no map persisted
        )
        assert gate.passed is False
        assert "provenance" in gate.reason.lower() or "marker" in gate.reason.lower()

    def test_paper_with_all_unmapped_markers_fails(self):
        """All markers unmapped means no recoverable provenance."""
        gate = PaperSynthesisStage.provenance_precondition(
            paper_markdown="[SOURCE-1] [SOURCE-2]",
            source_map=[
                {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "unmapped"},
                {"marker_index": 2, "marker": "SOURCE-2", "mapping_status": "unmapped"},
            ],
        )
        assert gate.passed is False

    def test_paper_with_mapped_markers_passes(self):
        """A paper whose markers are all mapped satisfies the precondition."""
        gate = PaperSynthesisStage.provenance_precondition(
            paper_markdown="[SOURCE-1] and [SOURCE-2]",
            source_map=[
                {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "mapped"},
                {"marker_index": 2, "marker": "SOURCE-2", "mapping_status": "mapped"},
            ],
        )
        assert gate.passed is True

    def test_paper_with_no_markers_passes(self):
        """A paper with no citation markers has no provenance requirement."""
        gate = PaperSynthesisStage.provenance_precondition(
            paper_markdown="A paper with no citations at all.",
            source_map=[],
        )
        assert gate.passed is True

    def test_paper_with_partial_unmapped_passes_with_flag(self):
        """Some mapped + some unmapped: passes but records the unmapped count.

        The precondition is satisfied (provenance exists), but the unmapped
        markers are surfaced so the evaluation can note them."""
        gate = PaperSynthesisStage.provenance_precondition(
            paper_markdown="[SOURCE-1] [SOURCE-2] [SOURCE-99]",
            source_map=[
                {"marker_index": 1, "marker": "SOURCE-1", "mapping_status": "mapped"},
                {"marker_index": 2, "marker": "SOURCE-2", "mapping_status": "mapped"},
                {"marker_index": 99, "marker": "SOURCE-99", "mapping_status": "unmapped"},
            ],
        )
        assert gate.passed is True
        assert gate.unmapped_count == 1


class TestScopeAlignmentGate:
    """4E — scope-drift detection via the existing evaluator architecture."""

    def test_off_scope_paper_blocks_positive_evaluation(self):
        """A materially off-scope paper is classified off_scope."""
        from backend.pipeline.evaluation.scope_checker import classify_scope_alignment

        result = classify_scope_alignment(
            research_intent="neuro-symbolic verifiability for safety-critical systems",
            paper_title="Quantization-Aware Training for Efficient Inference",
            paper_abstract=(
                "We propose a quantization method that compresses neural networks "
                "for faster inference on edge devices, reducing memory footprint."
            ),
        )
        assert result.classification == "off_scope"
        assert result.reason

    def test_on_scope_paper_classified_on_scope(self):
        """An on-topic paper is classified on_scope."""
        from backend.pipeline.evaluation.scope_checker import classify_scope_alignment

        result = classify_scope_alignment(
            research_intent="graph-based reasoning for LLMs",
            paper_title="Graph of Thoughts: Reasoning with LLMs",
            paper_abstract=(
                "We propose Graph of Thoughts, a framework that models LLM reasoning "
                "as a graph structure to enable neuro-symbolic verifiable reasoning."
            ),
        )
        assert result.classification == "on_scope"

    def test_missing_research_intent_is_unavailable(self):
        """No persisted research intent → unavailable, not an inferred result."""
        from backend.pipeline.evaluation.scope_checker import classify_scope_alignment

        result = classify_scope_alignment(
            research_intent="",
            paper_title="Anything",
            paper_abstract="Anything",
        )
        assert result.classification == "unavailable"


class TestConclusionSupportGate:
    """4F — conclusion-overreach detection via the existing evaluator."""

    def test_overstated_conclusion_detected(self):
        """'demonstrates' without empirical results is overstated."""
        from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support

        result = classify_conclusion_support(
            abstract="We propose a novel architecture for reasoning.",
            conclusion=(
                "Our method demonstrates significant improvements over baselines "
                "and proves that graph-based approaches are superior."
            ),
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_supported_conclusion_passes(self):
        """A conclusion grounded in reported empirical results is supported."""
        from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support

        result = classify_conclusion_support(
            abstract="We evaluate our method on three benchmarks.",
            conclusion=(
                "Our method achieves 92% accuracy on benchmark X, an improvement "
                "of 5 points over the strongest baseline."
            ),
            has_empirical_results=True,
        )
        assert result.classification in ("supported_by_paper", "supported")

    def test_proposal_only_paper_conclusion_is_overstated(self):
        """A design+projection paper claiming validation is overstated
        (the Phase 3 pattern: 3/6 papers claimed demonstration without results)."""
        from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support

        result = classify_conclusion_support(
            abstract="We propose a conceptual framework for verifiable reasoning.",
            conclusion="We validate our approach and show it significantly improves verifiability.",
            has_empirical_results=False,
        )
        assert result.classification == "overstated"
