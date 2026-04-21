"""Tests for mechanical quality heuristics on IdeaCandidate."""

from backend.pipeline.generation.mechanical_checks import mechanical_quality_check
from backend.pipeline.generation.models import IdeaCandidate


def _idea(**overrides) -> IdeaCandidate:
    defaults = dict(
        title="Cross-lingual transfer learning for low-resource sentiment analysis",
        problem_statement="Existing sentiment models perform poorly on languages with limited training data, requiring expensive annotation efforts for each new language.",
        proposed_method="We propose a adapter-based transfer framework that learns language-invariant representations via contrastive learning on parallel corpora, then fine-tunes task-specific adapters using only 100 target-language examples.",
        expected_contributions="90% accuracy with 10x less labeled data",
        novelty_rationale="First application of contrastive adapter fusion to sentiment transfer.",
        evaluation_approach="Evaluate on 5 low-resource languages using F1 score against native-language baselines.",
    )
    defaults.update(overrides)
    return IdeaCandidate(**defaults)


class TestMechanicalQualityCheck:
    def test_strong_idea_passes_all(self):
        report = mechanical_quality_check(_idea())
        assert report.composite_score == 1.0
        assert report.flagged_issues == []

    def test_short_title_flagged(self):
        report = mechanical_quality_check(_idea(title="New method"))
        assert not any(r.passed for r in report.heuristic_results if r.name == "title_specificity")
        assert any("title" in f.lower() for f in report.flagged_issues)

    def test_generic_title_flagged(self):
        report = mechanical_quality_check(_idea(title="A novel improved effective approach"))
        assert not any(r.passed for r in report.heuristic_results if r.name == "title_specificity")

    def test_short_method_flagged(self):
        report = mechanical_quality_check(_idea(proposed_method="Use transformers."))
        assert not any(r.passed for r in report.heuristic_results if r.name == "method_specificity")

    def test_missing_evaluation_flagged(self):
        report = mechanical_quality_check(_idea(evaluation_approach=""))
        assert not any(r.passed for r in report.heuristic_results if r.name == "evaluation_present")

    def test_circular_reasoning_flagged(self):
        text = "entity linking biomedical texts methods requires better improving addressing"
        report = mechanical_quality_check(_idea(problem_statement=text, proposed_method=text))
        assert not any(r.passed for r in report.heuristic_results if r.name == "non_circular")

    def test_quantitative_claims_without_metrics_flagged(self):
        report = mechanical_quality_check(
            _idea(
                expected_contributions="Achieves 95% accuracy and 3x speedup",
                evaluation_approach="We will compare outputs qualitatively.",
            )
        )
        assert not any(
            r.passed for r in report.heuristic_results if r.name == "quantitative_backed"
        )

    def test_quantitative_claims_with_metrics_passes(self):
        report = mechanical_quality_check(
            _idea(
                expected_contributions="Achieves 95% accuracy and 3x speedup",
                evaluation_approach="Measure F1 score and BLEU on 3 benchmark datasets.",
            )
        )
        assert any(r.passed for r in report.heuristic_results if r.name == "quantitative_backed")

    def test_composite_score_fraction(self):
        report = mechanical_quality_check(_idea(title="Short"))  # fails title
        assert report.composite_score == 0.8  # 4/5 pass
