"""Tests for MetacognitiveManager."""

import pytest

from backend.pipeline.evaluation.quality_gate import QualityGateResult
from backend.pipeline.evaluation.scorer import ScoreDimension, ScoreResult
from backend.pipeline.metacognitive.manager import MetacognitiveManager
from backend.pipeline.metacognitive.plateau_detector import PlateauDetector


def make_report(
    overall: float = 0.6,
    novelty: float = 0.5,
    feasibility: float = 0.6,
    impact: float = 0.7,
    gate_passed: bool = True,
):
    """Build a minimal UnifiedEvaluationReport-like object."""
    from backend.pipeline.evaluation.pipeline_evaluator import UnifiedEvaluationReport

    dims = {
        "novelty": ScoreResult(dimension=ScoreDimension.NOVELTY, score=novelty),
        "feasibility": ScoreResult(dimension=ScoreDimension.FEASIBILITY, score=feasibility),
        "impact": ScoreResult(dimension=ScoreDimension.IMPACT, score=impact),
    }
    gate = QualityGateResult(
        passed=gate_passed,
        composite_score=overall,
        dimension_results={},
        failures=[],
        recommendation="proceed",
    )
    return UnifiedEvaluationReport(
        idea_id="test-1",
        idea_title="Test Idea",
        dimension_scores=dims,
        overall_score=overall,
        quality_gate_result=gate,
    )


class TestRecordStage:
    def test_records_metrics(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("idea_generation", {"avg_score": 0.5, "novelty": 0.4})
        assert len(mgr.ledger._entries) == 2
        assert mgr.ledger.latest("avg_score").value == 0.5
        assert mgr.ledger.latest("novelty").value == 0.4

    def test_records_with_round_num(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("gen", {"score": 0.6}, round_num=3)
        entry = mgr.ledger.latest("score")
        assert entry.round_num == 3

    def test_records_passed_flag(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("gen", {"score": 0.1}, passed=False)
        entry = mgr.ledger.latest("score")
        assert entry.passed is False


class TestRecordEvaluation:
    def test_extracts_overall_score(self):
        mgr = MetacognitiveManager()
        report = make_report(overall=0.75)
        mgr.record_evaluation(report)
        entry = mgr.ledger.latest("overall_score")
        assert entry is not None
        assert entry.value == 0.75

    def test_extracts_dimension_scores(self):
        mgr = MetacognitiveManager()
        report = make_report(novelty=0.8, feasibility=0.6)
        mgr.record_evaluation(report)
        traj = mgr.ledger.trajectory("novelty")
        assert traj == [0.8]
        traj = mgr.ledger.trajectory("feasibility")
        assert traj == [0.6]

    def test_extracts_quality_gate(self):
        mgr = MetacognitiveManager()
        report = make_report(gate_passed=True)
        mgr.record_evaluation(report)
        entry = mgr.ledger.latest("quality_gate")
        assert entry is not None
        assert entry.value == 1.0
        assert entry.passed is True

    def test_quality_gate_failed(self):
        mgr = MetacognitiveManager()
        report = make_report(gate_passed=False)
        mgr.record_evaluation(report)
        entry = mgr.ledger.latest("quality_gate")
        assert entry.value == 0.0
        assert entry.passed is False


class TestCheckPlateau:
    def test_no_plateau_when_improving(self):
        mgr = MetacognitiveManager()
        for score in [0.3, 0.5, 0.7, 0.9]:
            mgr.record_stage("eval", {"overall_score": score})
        result = mgr.check_plateau("overall_score")
        assert result.is_plateau is False

    def test_plateau_when_stuck(self):
        det = PlateauDetector(window_size=3, threshold=0.02)
        mgr = MetacognitiveManager(plateau_detector=det)
        for _ in range(4):
            mgr.record_stage("eval", {"overall_score": 0.5})
        result = mgr.check_plateau("overall_score")
        assert result.is_plateau is True


class TestRecommendAction:
    def test_proceed_when_no_plateau(self):
        mgr = MetacognitiveManager()
        det = PlateauDetector(window_size=3, threshold=0.02)
        mgr._detector = det
        from backend.pipeline.metacognitive.plateau_detector import PlateauResult
        result = PlateauResult(is_plateau=False, reason="fine")
        assert mgr.recommend_action(result) == "proceed"

    def test_abort_on_abort_suggestion(self):
        mgr = MetacognitiveManager()
        from backend.pipeline.metacognitive.plateau_detector import PlateauResult
        result = PlateauResult(
            is_plateau=True,
            reason="stuck",
            suggestions=["abort", "retry"],
        )
        assert mgr.recommend_action(result) == "abort"

    def test_change_strategy(self):
        mgr = MetacognitiveManager()
        from backend.pipeline.metacognitive.plateau_detector import PlateauResult
        result = PlateauResult(
            is_plateau=True,
            reason="stuck",
            suggestions=["change_strategy"],
        )
        assert mgr.recommend_action(result) == "change_strategy"

    def test_strategy_callback_called(self):
        calls = []
        mgr = MetacognitiveManager(
            strategy_change_callback=lambda reason: calls.append(reason),
        )
        from backend.pipeline.metacognitive.plateau_detector import PlateauResult
        result = PlateauResult(
            is_plateau=True,
            reason="stagnation",
            suggestions=["change_strategy"],
        )
        mgr.recommend_action(result)
        assert calls == ["stagnation"]

    def test_retry_stage(self):
        mgr = MetacognitiveManager()
        from backend.pipeline.metacognitive.plateau_detector import PlateauResult
        result = PlateauResult(
            is_plateau=True,
            reason="stuck",
            suggestions=["retry"],
        )
        assert mgr.recommend_action(result) == "retry_stage"


class TestShouldEarlyStop:
    def test_normal_operation_no_stop(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("eval", {"quality_gate": 1.0}, passed=True)
        mgr.record_stage("eval", {"overall_score": 0.6}, passed=True)
        assert mgr.should_early_stop() is False

    def test_stop_on_catastrophic_quality(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("eval", {"quality_gate": 0.0}, passed=False)
        mgr.record_stage("eval", {"overall_score": 0.05}, passed=False)
        assert mgr.should_early_stop() is True

    def test_stop_only_once(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("eval", {"quality_gate": 0.0}, passed=False)
        mgr.record_stage("eval", {"overall_score": 0.05}, passed=False)
        assert mgr.should_early_stop() is True
        assert mgr.should_early_stop() is True  # stays aborted
        assert mgr._aborted is True

    def test_no_stop_when_gate_passed(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("eval", {"quality_gate": 1.0}, passed=True)
        mgr.record_stage("eval", {"overall_score": 0.05}, passed=False)
        assert mgr.should_early_stop() is False

    def test_no_stop_when_score_above_threshold(self):
        mgr = MetacognitiveManager()
        mgr.record_stage("eval", {"quality_gate": 0.0}, passed=False)
        mgr.record_stage("eval", {"overall_score": 0.2}, passed=False)
        assert mgr.should_early_stop() is False
