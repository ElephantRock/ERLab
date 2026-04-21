"""Tests for the configurable quality gate."""

from backend.pipeline.evaluation.quality_gate import (
    QualityGate,
    QualityGateConfig,
    QualityThreshold,
)
from backend.pipeline.evaluation.scorer import EvaluationReport, ScoreDimension, ScoreResult


def _make_report(**dim_scores: float) -> EvaluationReport:
    scores = [
        ScoreResult(dimension=dim, score=s)
        for dim, s in dim_scores.items()
    ]
    overall = sum(s.score for s in scores) / len(scores) if scores else 0.0
    return EvaluationReport(target_id="test", scores=scores, overall_score=overall)


class TestQualityGateDefault:
    def test_default_config_loads(self):
        config = QualityGateConfig.default()
        assert len(config.thresholds) == 4
        assert config.composite_threshold == 0.4

    def test_pass_above_threshold(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.3, weight=1.0),
            ],
            composite_threshold=0.3,
        )
        gate = QualityGate(config)
        report = _make_report(**{ScoreDimension.NOVELTY: 0.5})
        result = gate.evaluate(report)
        assert result.passed
        assert result.recommendation == "proceed"

    def test_fail_below_threshold(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.5, weight=1.0),
            ],
            composite_threshold=0.5,
        )
        gate = QualityGate(config)
        report = _make_report(**{ScoreDimension.NOVELTY: 0.2})
        result = gate.evaluate(report)
        assert not result.passed
        assert len(result.failures) == 1

    def test_required_dimension_hard_fail(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(
                    dimension=ScoreDimension.SOUNDNESS, min_score=0.5,
                    weight=1.0, required=True,
                ),
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.3, weight=1.0),
            ],
            composite_threshold=0.3,
        )
        gate = QualityGate(config)
        report = _make_report(
            **{ScoreDimension.SOUNDNESS: 0.1, ScoreDimension.NOVELTY: 0.9}
        )
        result = gate.evaluate(report)
        assert not result.passed

    def test_all_mode(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.5, weight=1.0),
                QualityThreshold(dimension=ScoreDimension.FEASIBILITY, min_score=0.5, weight=1.0),
            ],
            composite_threshold=0.0,
            mode="all",
        )
        gate = QualityGate(config)
        report = _make_report(
            **{ScoreDimension.NOVELTY: 0.9, ScoreDimension.FEASIBILITY: 0.3}
        )
        result = gate.evaluate(report)
        assert not result.passed  # feasibility failed

    def test_retry_recommendation(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.5, weight=1.0),
            ],
            composite_threshold=0.5,
        )
        gate = QualityGate(config)
        report = _make_report(**{ScoreDimension.NOVELTY: 0.3})
        result = gate.evaluate(report)
        assert result.recommendation == "retry_with_feedback"

    def test_discard_recommendation(self):
        config = QualityGateConfig(
            thresholds=[
                QualityThreshold(dimension=ScoreDimension.NOVELTY, min_score=0.8, weight=1.0),
                QualityThreshold(dimension=ScoreDimension.FEASIBILITY, min_score=0.8, weight=1.0),
                QualityThreshold(dimension=ScoreDimension.IMPACT, min_score=0.8, weight=1.0),
            ],
            composite_threshold=0.8,
        )
        gate = QualityGate(config)
        report = _make_report(
            **{ScoreDimension.NOVELTY: 0.1, ScoreDimension.FEASIBILITY: 0.1,
               ScoreDimension.IMPACT: 0.1}
        )
        result = gate.evaluate(report)
        assert result.recommendation == "discard"
