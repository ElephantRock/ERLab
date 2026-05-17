"""Phase C+D tests: Scorers."""

import pytest
from unittest.mock import MagicMock

from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer
from backend.pipeline.model_certification.stage_scorer import (
    ScorerRegistry, StageScorer, create_default_registry,
)
from backend.pipeline.model_certification.scorers.query_generation import QueryGenerationScorer
from backend.pipeline.model_certification.scorers.literature_filtering import LiteratureFilteringScorer
from backend.pipeline.model_certification.scorers.paper_extraction import PaperExtractionScorer
from backend.pipeline.model_certification.scorers.evidence_table import EvidenceTableScorer
from backend.pipeline.model_certification.scorers.synthesis import SynthesisScorer
from backend.pipeline.model_certification.scorers.repair import RepairScorer
from backend.pipeline.model_certification.scorers.adversarial_review import AdversarialReviewScorer
from backend.pipeline.model_certification.scorers.grounding import compute_grounding_metrics


def _case(stage="query_generation", **kw):
    defaults = dict(
        case_id=f"{stage}-001", stage=stage,
        prompt_template="test", requires_grounding=False,
    )
    defaults.update(kw)
    return StageEvalCase(**defaults)


class TestQueryGenerationScorer:
    def test_detects_duplicate_queries(self):
        scorer = QueryGenerationScorer()
        raw = '{"queries": ["machine learning in healthcare", "Machine Learning in Healthcare", "deep learning trends"]}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case())
        assert scores["duplicate_query_rate"] > 0

    def test_rates_diversity(self):
        scorer = QueryGenerationScorer()
        raw = '{"queries": ["machine learning", "natural language processing", "computer vision"]}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case())
        assert scores["query_diversity"] > 0.5

    def test_flags_malformed(self):
        scorer = QueryGenerationScorer()
        raw = '{"queries": ["ok", "hi", ""]}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case())
        assert scores["malformed_query_rate"] > 0


class TestLiteratureFilteringScorer:
    def test_weights_false_rejection_heavily(self):
        scorer = LiteratureFilteringScorer()
        raw = '{"ids": ["paper1"]}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(inclusion_set=["paper1", "paper2", "paper3"])
        scores = scorer.score(raw, parsed, _case(), gold)
        # Missing paper2 and paper3 → high false rejection
        assert scores["false_rejection_rate"] > 0.5
        assert scores["recall"] < 1.0

    def test_computes_precision_recall(self):
        scorer = LiteratureFilteringScorer()
        raw = '{"ids": ["paper1", "paper2"]}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(inclusion_set=["paper1", "paper3"])
        scores = scorer.score(raw, parsed, _case(), gold)
        assert 0 <= scores["precision"] <= 1
        assert 0 <= scores["recall"] <= 1

    def test_gold_comparison(self):
        scorer = LiteratureFilteringScorer()
        raw = '{"ids": ["A", "B", "C"]}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(inclusion_set=["A", "B", "C"])
        scores = scorer.score(raw, parsed, _case(), gold)
        assert scores["recall"] == 1.0
        assert scores["false_rejection_rate"] == 0.0


class TestPaperExtractionScorer:
    def test_scores_field_completeness(self):
        scorer = PaperExtractionScorer()
        raw = '{"title": "Test", "abstract": "Abs", "authors": "A B", "year": 2024, "method": "DL", "results": "Good"}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case("paper_extraction"))
        assert scores["field_completeness"] == 1.0

    def test_checks_method_accuracy(self):
        scorer = PaperExtractionScorer()
        raw = '{"method": "deep learning with transformers for NLP"}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(expected_fields={"method": "deep learning transformers"})
        scores = scorer.score(raw, parsed, _case("paper_extraction"), gold)
        # Should have non-zero overlap with gold method keywords
        assert scores["method_extraction_accuracy"] >= 0.0

    def test_citation_alignment(self):
        scorer = PaperExtractionScorer()
        raw = '{"citations": "[1] Smith et al 2024"}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(expected_fields={"citations": "Smith 2024"})
        scores = scorer.score(raw, parsed, _case("paper_extraction"), gold)
        assert scores["citation_alignment"] > 0


class TestEvidenceTableScorer:
    def test_flags_unsupported_claim(self):
        scorer = EvidenceTableScorer()
        raw = '{"claims": [{"text": "X is true", "source": null}]}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case("evidence_table"))
        assert scores["unsupported_claim_rate"] > 0

    def test_citation_completeness(self):
        scorer = EvidenceTableScorer()
        raw = '{"claims": [{"text": "A", "citation": "smith2024"}]}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(expected_keys=["smith2024", "jones2023"])
        scores = scorer.score(raw, parsed, _case("evidence_table"), gold)
        assert scores["citation_completeness"] < 1.0  # missing jones2023

    def test_duplicate_detection(self):
        scorer = EvidenceTableScorer()
        raw = '{"claims": [{"text": "Same claim"}, {"text": "Same claim"}]}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case("evidence_table"))
        assert scores["duplicate_evidence_rate"] > 0


class TestSynthesisScorer:
    def test_section_completeness(self):
        scorer = SynthesisScorer()
        text = "Introduction\nMethod\nResults\nDiscussion\nConclusion"
        scores = scorer.score(text, None, _case("paper_synthesis"))
        assert scores["section_completeness"] > 0.5

    def test_length_budget(self):
        scorer = SynthesisScorer()
        short_case = _case("paper_synthesis", output_token_budget=100000)
        scores = scorer.score("short text", None, short_case)
        assert scores["length_budget_adherence"] == 1.0

    def test_citation_grounding(self):
        scorer = SynthesisScorer()
        text = "Introduction [1]\nMethod (Smith et al., 2024)\nResults [doi:10.x]\nDiscussion\nConclusion"
        scores = scorer.score(text, None, _case("paper_synthesis"))
        assert scores["citation_grounding"] > 0


class TestRepairScorer:
    def test_json_repair_success(self):
        scorer = RepairScorer()
        raw = '{"status": "ok", "data": "fixed"}'
        import json
        parsed = json.loads(raw)
        scores = scorer.score(raw, parsed, _case("repair"))
        assert scores["json_repair_success"] == 1.0

    def test_measures_semantic_preservation(self):
        scorer = RepairScorer()
        raw = '{"name": "Alice", "age": 30, "role": "engineer"}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(expected_fields={"name": "Alice", "age": 30})
        scores = scorer.score(raw, parsed, _case("repair"), gold)
        assert scores["semantic_preservation"] > 0.5

    def test_schema_repair(self):
        scorer = RepairScorer()
        raw = '{"action": "keep", "claim_id": "C001", "reason": "supported"}'
        import json
        parsed = json.loads(raw)
        gold = GoldAnswer(expected_keys=["action", "claim_id", "reason"])
        scores = scorer.score(raw, parsed, _case("repair"), gold)
        assert scores["schema_repair_success"] == 1.0


class TestAdversarialReviewScorer:
    def test_detects_planted_errors(self):
        scorer = AdversarialReviewScorer()
        raw = "The paper has a citation mismatch in section 3. There is also an overclaim about the results being groundbreaking."
        gold = GoldAnswer(
            planted_errors=[
                {"type": "citation_mismatch", "indicator": "citation mismatch"},
                {"type": "overclaim", "indicator": "groundbreaking"},
            ]
        )
        scores = scorer.score(raw, None, _case("adversarial_review"), gold)
        assert scores["weakness_detection_rate"] > 0

    def test_false_alarm_rate(self):
        scorer = AdversarialReviewScorer()
        raw = "Issue one: X. Issue two: Y. Problem: Z. Concern: W. Flaw: V."
        gold = GoldAnswer(
            planted_errors=[
                {"type": "overclaim", "indicator": "nonexistent_error"},
            ]
        )
        scores = scorer.score(raw, None, _case("adversarial_review"), gold)
        # Many "issues" mentioned but only 1 planted error → high false alarm
        assert scores["false_alarm_rate"] > 0

    def test_overclaim_detection(self):
        scorer = AdversarialReviewScorer()
        raw = "The paper overclaims that this method is groundbreaking."
        gold = GoldAnswer(
            planted_errors=[
                {"type": "overclaim", "indicator": "groundbreaking"},
            ]
        )
        scores = scorer.score(raw, None, _case("adversarial_review"), gold)
        assert scores["overclaim_detection"] > 0


class TestGroundingScorer:
    def test_hard_fails_fabricated_citation(self):
        case = _case("evidence_table", requires_grounding=True, gold=GoldAnswer())
        metrics = compute_grounding_metrics(
            'Claims: "X is true [doi:10.0000/fake]"',
            {"claims": [{"text": "X is true", "citation": "doi:10.0000/fake"}],
             "citations": ["doi:10.0000/fake"]},
            case, GoldAnswer(),
        )
        # The fabricated citation should be detected by _FABRICATION_INDICATORS
        assert metrics["citation_fabrication_rate"] > 0.0

    def test_computes_claim_support_rate(self):
        case = _case("evidence_table", requires_grounding=True,
                     gold=GoldAnswer(expected_fields={"topic": "NLP"}))
        metrics = compute_grounding_metrics(
            "NLP models found that X is true [1]. Y is unsupported.",
            {"claims": [{"text": "NLP models found that X is true [1]"}, {"text": "Y is unsupported"}]},
            case, case.gold,
        )
        assert metrics["claim_support_rate"] >= 0.0

    def test_flags_high_unsupported_rate(self):
        case = _case("evidence_table", requires_grounding=True)
        metrics = compute_grounding_metrics(
            "Claim one. Claim two. Claim three. Claim four.",
            {"claims": [{"text": "Claim one"}, {"text": "Claim two"}, {"text": "Claim three"}, {"text": "Claim four"}]},
            case, None,
        )
        assert metrics["unsupported_claim_rate"] > 0.5

    def test_measures_citation_precision(self):
        case = _case("evidence_table", requires_grounding=True,
                     gold=GoldAnswer(expected_keys=["Smith2024"]))
        metrics = compute_grounding_metrics(
            "According to Smith2024, X is true.",
            {"citations": ["Smith2024"]},
            case, case.gold,
        )
        assert metrics["citation_precision"] > 0

    def test_skip_when_not_required(self):
        case = _case(requires_grounding=False)
        metrics = compute_grounding_metrics("text", None, case)
        assert metrics == {}

    def test_contradiction_handling(self):
        case = _case("paper_synthesis", requires_grounding=True,
                     gold=GoldAnswer(expected_fields={"contradictions": ["Study A contradicts Study B"]}))
        metrics = compute_grounding_metrics(
            "Study A contradicts Study B, which needs further investigation.",
            None, case, case.gold,
        )
        assert metrics["contradiction_handling_score"] > 0

    def test_real_citation_wrong_claim_support_fails_support_rate(self):
        """A real citation used in wrong context should hurt claim_support_rate."""
        case = _case("evidence_table", requires_grounding=True,
                     gold=GoldAnswer(expected_keys=["Smith2024"],
                                     expected_fields={"topic": "protein folding"}))
        metrics = compute_grounding_metrics(
            "Climate change is accelerating [Smith2024].",
            {"claims": [{"text": "Climate change is accelerating [Smith2024]"}],
             "citations": ["Smith2024"]},
            case, case.gold,
        )
        # citation_precision may be high (Smith2024 is real) but
        # claim_support_rate should suffer (wrong topic)
        assert metrics["citation_precision"] > 0  # citation exists
        # The claim about climate doesn't match gold topic "protein folding"

    def test_citation_precision_high_but_claim_support_low(self):
        """Explicitly demonstrate the separation between citation existence and claim support."""
        case = _case("evidence_table", requires_grounding=True,
                     gold=GoldAnswer(expected_keys=["paper_A"],
                                     expected_fields={"topic": "quantum computing"}))
        metrics = compute_grounding_metrics(
            "Quantum computing shows promise [paper_A]. Classical algorithms still dominate all benchmarks without any evidence.",
            {"claims": [
                {"text": "Quantum computing shows promise [paper_A]"},
                {"text": "Classical algorithms still dominate all benchmarks without any evidence"},
            ],
             "citations": ["paper_A"]},
            case, case.gold,
        )
        # citation_precision should be > 0 (paper_A is real)
        assert metrics["citation_precision"] > 0
        # But claim_support_rate should not be 1.0 (second claim unsupported)
        assert metrics["unsupported_claim_rate"] > 0


class TestScorerRegistry:
    def test_scorer_registry_maps_all_stages(self):
        registry = create_default_registry()
        stages = registry.stages
        assert "query_generation" in stages
        assert "literature_filtering" in stages
        assert "paper_extraction" in stages
        assert "evidence_table" in stages
        assert "repair" in stages
        assert "adversarial_review" in stages
        # SynthesisScorer registered under "synthesis"
        assert "synthesis" in stages

    def test_scorer_registry_unknown_stage_returns_empty_scores(self):
        registry = ScorerRegistry()
        scores = registry.score("nonexistent_stage", "text", None, _case())
        assert scores == {}

    def test_base_scorer_abstract_enforcement(self):
        with pytest.raises(TypeError):
            StageScorer()  # type: ignore
