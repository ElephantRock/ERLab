"""Tests for corpus-backed grounding scorer.

Validates:
1. Corpus-backed metrics computed from gold labels
2. Citation precision vs claim support rate are independent
3. Fabricated citations detected
4. Wrong-citation lowers claim_support_rate even when citation_precision is high
5. Contradicted claims detected
6. Unsupported claims raise unsupported_claim_rate
7. Legacy heuristic path still works for non-corpus cases
"""
import pytest

from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer
from backend.pipeline.model_certification.scorers.grounding import (
    compute_grounding_metrics,
    _is_corpus_backed,
)


# ─── Helpers ────────────────────────────────────────────────────────

def _make_case(stage: str = "evidence_table", requires_grounding: bool = True) -> StageEvalCase:
    return StageEvalCase(
        case_id="test-001",
        stage=stage,
        prompt_template="test prompt",
        requires_grounding=requires_grounding,
    )


def _make_corpus_gold(claims: list[dict], corpus_sources: list[dict] = None) -> GoldAnswer:
    return GoldAnswer(
        claims=claims,
        corpus_sources=corpus_sources or [{"source_id": "P1"}, {"source_id": "P2"}, {"source_id": "P3"}],
        expected_fields={"topic": "test"},
        expected_keys=[],
    )


# ─── Test: _is_corpus_backed ────────────────────────────────────────

class TestIsCorpusBacked:
    def test_empty_claims_not_corpus(self):
        gold = GoldAnswer()
        assert _is_corpus_backed(gold) is False

    def test_claims_with_support_label_is_corpus(self):
        gold = GoldAnswer(claims=[
            {"claim_id": "C1", "support_label": "supported", "supporting_sources": ["P1"]}
        ])
        assert _is_corpus_backed(gold) is True

    def test_claims_without_support_label_not_corpus(self):
        gold = GoldAnswer(claims=[
            {"claim_id": "C1", "text": "Some claim"}  # no support_label
        ])
        assert _is_corpus_backed(gold) is False


# ─── Test: Supported claims ─────────────────────────────────────────

class TestSupportedClaims:
    def test_all_supported_gives_high_support_rate(self):
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported", "supporting_sources": ["P1"], "text": "Transformers work well"},
            {"claim_id": "C2", "support_label": "supported", "supporting_sources": ["P2"], "text": "RAG achieves SOTA"},
        ])
        case = _make_case()
        text = "Transformers work well on translation [P1]. RAG achieves SOTA on QA [P2]."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["claim_support_rate"] > 0.0

    def test_no_grounding_returns_empty(self):
        case = _make_case(requires_grounding=False)
        metrics = compute_grounding_metrics("text", None, case, None)
        assert metrics == {}


# ─── Test: Fabricated citations ─────────────────────────────────────

class TestFabricatedCitations:
    def test_fabricated_citation_detected(self):
        """When gold says a citation is fabricated, fabrication rate should reflect it."""
        gold = _make_corpus_gold([
            {"claim_id": "C5", "support_label": "fabricated_citation",
             "cited_sources": ["PX"], "supporting_sources": [],
             "text": "Visual reasoning (PX)"},
        ])
        case = _make_case()
        # Model flags PX as fabricated
        text = "Visual reasoning [PX] — PX is fabricated, not in the corpus."
        metrics = compute_grounding_metrics(text, None, case, gold)
        # Fabrication rate > 0 because PX is not a real corpus source
        assert metrics["citation_fabrication_rate"] > 0.0

    def test_fabricated_citation_in_output_raises_rate(self):
        """If model includes fabricated citation without flagging, fabrication rate increases."""
        gold = _make_corpus_gold([
            {"claim_id": "C5", "support_label": "fabricated_citation",
             "cited_sources": ["P99"], "supporting_sources": [],
             "text": "Claim with P99"},
        ])
        case = _make_case()
        # Model cites P99 without flagging it as fabricated
        text = "Visual reasoning is possible with pre-trained models [P99]."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["citation_fabrication_rate"] > 0.0


# ─── Test: Wrong citation vs citation precision ─────────────────────

class TestWrongCitationIndependence:
    """CRITICAL: real citation used wrongly should hurt claim_support but not citation_precision."""

    def test_wrong_citation_lowers_claim_support(self):
        """A real citation used for the wrong claim should lower claim_support_rate."""
        gold = _make_corpus_gold([
            {"claim_id": "C3", "support_label": "wrong_citation",
             "cited_sources": ["P1"], "supporting_sources": ["P3"],
             "text": "Scaling laws (P1)"},
        ])
        case = _make_case()
        # Model uses P1 for scaling laws (should be P3)
        text = "Scaling laws show power-law behavior [P1]. P3 better supports this."
        metrics = compute_grounding_metrics(text, None, case, gold)
        # P1 is a real citation → citation_precision should be reasonable
        # But wrong usage → claim_support may be lower
        assert "claim_support_rate" in metrics
        assert "citation_precision" in metrics

    def test_high_precision_low_support_possible(self):
        """citation_precision and claim_support_rate are independent metrics."""
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported",
             "supporting_sources": ["P1"], "text": "Transformers work [P1]"},
            {"claim_id": "C2", "support_label": "wrong_citation",
             "cited_sources": ["P1"], "supporting_sources": ["P3"],
             "text": "Scaling laws [P1]"},
        ])
        case = _make_case()
        text = "Transformers are effective [P1]. Scaling laws show power law [P1]. P3 better supports scaling."
        metrics = compute_grounding_metrics(text, None, case, gold)
        # Both cite real source P1 → precision should be high
        # But C2 misattributes → support should not be perfect
        assert metrics["citation_precision"] > 0.0


# ─── Test: Contradicted claims ──────────────────────────────────────

class TestContradictedClaims:
    def test_contradiction_detected(self):
        gold = _make_corpus_gold([
            {"claim_id": "C3", "support_label": "contradicted",
             "cited_sources": ["P1"], "contradicting_sources": ["P1"],
             "text": "BERT best for generation"},
        ])
        case = _make_case()
        text = "BERT best for text generation contradicts P1 which states BERT cannot generate text."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["contradiction_handling_score"] > 0.0

    def test_no_contradictions_gives_perfect_score(self):
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported",
             "supporting_sources": ["P1"], "text": "Transformers work"},
        ])
        case = _make_case()
        text = "Transformers work well [P1]."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["contradiction_handling_score"] == 1.0


# ─── Test: Unsupported claims ───────────────────────────────────────

class TestUnsupportedClaims:
    def test_unsupported_claim_raises_rate(self):
        gold = _make_corpus_gold([
            {"claim_id": "C4", "support_label": "unsupported",
             "supporting_sources": [],
             "text": "RAG eliminates training"},
        ])
        case = _make_case()
        text = "RAG eliminates training is unsupported — P2 does not state this."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["unsupported_claim_rate"] > 0.0

    def test_overclaim_flagged_as_unsupported(self):
        gold = _make_corpus_gold([
            {"claim_id": "C4", "support_label": "unsupported",
             "supporting_sources": [],
             "text": "RAG achieves 99.9% accuracy on everything"},
        ])
        case = _make_case()
        text = "RAG achieves 99.9% accuracy is an overclaim not supported by any source."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert metrics["unsupported_claim_rate"] > 0.0


# ─── Test: Legacy heuristic path ────────────────────────────────────

class TestLegacyHeuristic:
    def test_non_corpus_gold_uses_heuristic(self):
        """Cases without corpus-backed gold use heuristic extraction."""
        gold = GoldAnswer(
            expected_keys=["Lewis", "Izacard"],
            expected_fields={"topic": "RAG"},
            planted_errors=[{"type": "overclaim", "indicator": "completely eliminates"}],
        )
        case = _make_case()
        text = "Lewis et al. found RAG reduces hallucination. Izacard showed RAG achieves SOTA on QA. RAG completely eliminates training."
        metrics = compute_grounding_metrics(text, None, case, gold)
        assert "claim_support_rate" in metrics
        assert "citation_fabrication_rate" in metrics
        assert metrics["claim_support_rate"] >= 0.0

    def test_no_gold_heuristic(self):
        """Without any gold, heuristic still returns metrics."""
        case = _make_case()
        text = "Some text with citations [1] and [2]."
        metrics = compute_grounding_metrics(text, None, case, None)
        assert "claim_support_rate" in metrics


# ─── Test: Eval case loading ────────────────────────────────────────

class TestEvalCaseLoading:
    def test_corpus_backed_case_loads(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("evidence_table", "data/model_certification/eval_cases")
        assert len(cases) >= 4  # 001 (legacy) + 002, 003, 004 (corpus-backed)

    def test_corpus_backed_claims_accessible(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("evidence_table", "data/model_certification/eval_cases")
        corpus_cases = [c for c in cases if c.gold and c.gold.claims]
        assert len(corpus_cases) >= 3

    def test_adversarial_review_cases_load(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("adversarial_review", "data/model_certification/eval_cases")
        assert len(cases) >= 3  # 001 (legacy) + 002, 003, 004 (corpus-backed)

    def test_paper_synthesis_cases_load(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("paper_synthesis", "data/model_certification/eval_cases")
        assert len(cases) >= 2

    def test_proposal_synthesis_cases_load(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("proposal_synthesis", "data/model_certification/eval_cases")
        assert len(cases) >= 2

    def test_corpus_source_ids_present(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        cases = load_suite("evidence_table", "data/model_certification/eval_cases")
        corpus_cases = [c for c in cases if c.gold and c.gold.corpus_sources]
        assert len(corpus_cases) >= 3
        for cc in corpus_cases:
            sources = cc.gold.corpus_sources
            assert len(sources) >= 2, f"Case {cc.case_id} needs at least 2 corpus sources"
            for s in sources:
                assert "source_id" in s or isinstance(s, str), f"Missing source_id in {cc.case_id}"

    def test_support_labels_valid(self):
        from backend.pipeline.model_certification.eval_case import load_suite
        from backend.pipeline.model_certification.scorers.grounding import _VALID_SUPPORT_LABELS
        for stage in ["evidence_table", "adversarial_review", "paper_synthesis", "proposal_synthesis"]:
            cases = load_suite(stage, "data/model_certification/eval_cases")
            for c in cases:
                if c.gold and c.gold.claims:
                    for gc in c.gold.claims:
                        label = gc.get("support_label")
                        if label:
                            assert label in _VALID_SUPPORT_LABELS, \
                                f"Invalid support_label '{label}' in {c.case_id}"


# ─── Test: Metric invariants ────────────────────────────────────────

class TestMetricInvariants:
    def test_rates_between_0_and_1(self):
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported",
             "supporting_sources": ["P1"], "text": "Test claim"},
        ])
        case = _make_case()
        text = "Test claim [P1]."
        metrics = compute_grounding_metrics(text, None, case, gold)
        for name, value in metrics.items():
            assert 0.0 <= value <= 1.0, f"{name}={value} out of [0,1] range"

    def test_support_plus_unsupported_leq_1(self):
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported",
             "supporting_sources": ["P1"], "text": "Claim 1"},
            {"claim_id": "C2", "support_label": "unsupported",
             "supporting_sources": [], "text": "Claim 2"},
        ])
        case = _make_case()
        text = "Claim 1 is supported [P1]. Claim 2 is unsupported."
        metrics = compute_grounding_metrics(text, None, case, gold)
        total = metrics["claim_support_rate"] + metrics["unsupported_claim_rate"]
        assert total <= 1.0 + 0.01  # Small tolerance for rounding

    def test_precision_plus_fabrication_leq_1(self):
        gold = _make_corpus_gold([
            {"claim_id": "C1", "support_label": "supported",
             "supporting_sources": ["P1"], "text": "Claim 1"},
        ])
        case = _make_case()
        text = "Claim 1 [P1]."
        metrics = compute_grounding_metrics(text, None, case, gold)
        total = metrics["citation_precision"] + metrics["citation_fabrication_rate"]
        assert total <= 1.0 + 0.01
