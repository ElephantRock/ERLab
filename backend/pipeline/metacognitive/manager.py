"""MetacognitiveManager — orchestrates ledger recording, plateau detection, strategy changes."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from backend.pipeline.metacognitive.ledger import LedgerEntry, ProgressLedger
from backend.pipeline.metacognitive.plateau_detector import PlateauDetector, PlateauResult

if TYPE_CHECKING:
    from backend.pipeline.evaluation.pipeline_evaluator import UnifiedEvaluationReport

logger = logging.getLogger(__name__)


class MetacognitiveManager:
    def __init__(
        self,
        ledger: ProgressLedger | None = None,
        plateau_detector: PlateauDetector | None = None,
        strategy_change_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._ledger = ledger or ProgressLedger()
        self._detector = plateau_detector or PlateauDetector()
        self._on_strategy_change = strategy_change_callback
        self._aborted = False

    @property
    def ledger(self) -> ProgressLedger:
        return self._ledger

    def record_stage(
        self,
        stage: str,
        metrics: dict[str, float],
        passed: bool = True,
        round_num: int | None = None,
    ) -> None:
        now = time.time()
        for name, value in metrics.items():
            self._ledger.record(LedgerEntry(
                stage=stage,
                round_num=round_num,
                metric_name=name,
                value=value,
                passed=passed,
                timestamp=now,
            ))

    def record_evaluation(self, report: UnifiedEvaluationReport) -> None:
        self._ledger.record(LedgerEntry(
            stage="evaluation",
            metric_name="overall_score",
            value=report.overall_score,
            passed=report.overall_score > 0.0,
        ))
        for dim_name, score_result in report.dimension_scores.items():
            self._ledger.record(LedgerEntry(
                stage="evaluation",
                metric_name=dim_name,
                value=score_result.score,
            ))
        if report.quality_gate_result is not None:
            self._ledger.record(LedgerEntry(
                stage="evaluation",
                metric_name="quality_gate",
                value=1.0 if report.quality_gate_result.passed else 0.0,
                passed=report.quality_gate_result.passed,
            ))

    def check_plateau(self, metric: str = "overall_score") -> PlateauResult:
        return self._detector.detect(self._ledger, metric)

    def recommend_action(self, plateau: PlateauResult) -> str:
        if not plateau.is_plateau:
            return "proceed"
        if "abort" in plateau.suggestions:
            return "abort"
        if "change_strategy" in plateau.suggestions:
            if self._on_strategy_change:
                self._on_strategy_change(plateau.reason)
            return "change_strategy"
        if "retry" in plateau.suggestions:
            return "retry_stage"
        return "proceed"

    def should_early_stop(self) -> bool:
        if self._aborted:
            return True
        gate = self._ledger.latest("quality_gate")
        if gate is not None and not gate.passed:
            overall = self._ledger.latest("overall_score")
            if overall is not None and overall.value < 0.1:
                self._aborted = True
                return True
        return False
