"""Tests for BATCH-156 — Multi-Dimensional Proposal Evaluation.

Covers:
  TASK-01: EvaluationStage, orchestrator registration, preset config
  TASK-03: Preset evaluation flags for deep_research / fast_scan

Uses asyncio.run() directly. pytest.ini has -p no:asyncio.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Lightweight stubs — avoid importing the full pipeline dependency tree
# ---------------------------------------------------------------------------


def _make_proposal(title: str = "Test Proposal", metadata_val: Any = None):
    """Create a minimal proposal object that behaves like ResearchProposal."""

    class FakeProposal:
        def __init__(self, t=title, m=metadata_val):
            self.title = t
            self.metadata = m
            self.sections = {}

        def to_markdown(self) -> str:
            return f"# {self.title}\n\nSome proposal text for evaluation."

    return FakeProposal()


def _make_ctx(*, proposals=None, params=None):
    """Create a minimal StageContext-like object."""

    class FakeResult:
        def __init__(self):
            self.proposals = proposals or {}
            self.ideas = []

    class FakeCtx:
        def __init__(self):
            self.result = FakeResult()
            self.params = params or {}
            self.all_papers = []

    return FakeCtx()


# ---------------------------------------------------------------------------
# TASK-01 Tests
# ---------------------------------------------------------------------------


class TestEvaluationStageInStageOrder:
    """TEST-156-01-01: evaluation in _STAGE_ORDER."""

    def test_evaluation_in_stage_order(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator

        assert "evaluation" in PipelineOrchestrator._STAGE_ORDER, (
            "evaluation must appear in _STAGE_ORDER"
        )

    def test_evaluation_after_adversarial_review(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator

        order = PipelineOrchestrator._STAGE_ORDER
        eval_idx = order.index("evaluation")
        ar_idx = order.index("adversarial_review")
        assert eval_idx > ar_idx, (
            f"evaluation (idx {eval_idx}) must come after adversarial_review (idx {ar_idx})"
        )

    def test_evaluation_before_paper_synthesis(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator

        order = PipelineOrchestrator._STAGE_ORDER
        eval_idx = order.index("evaluation")
        ps_idx = order.index("paper_synthesis")
        assert eval_idx < ps_idx, (
            f"evaluation (idx {eval_idx}) must come before paper_synthesis (idx {ps_idx})"
        )


class TestEvaluationMetadata:
    """TEST-156-01-03: Evaluation stored in metadata."""

    def test_evaluation_stored_in_metadata(self):
        from backend.pipeline.evaluation.proposal_evaluator import (
            DimensionScore,
            ProposalEvaluation,
        )
        from backend.pipeline.stages import EvaluationStage

        proposal = _make_proposal()
        ctx = _make_ctx(proposals={0: proposal})

        mock_evaluator = MagicMock()
        expected = ProposalEvaluation(
            novelty=DimensionScore(score=0.8, justification="High novelty"),
            feasibility=DimensionScore(score=0.7, justification="Reasonable"),
            completeness=DimensionScore(score=0.6, justification="Partial"),
            rigor=DimensionScore(score=0.9, justification="Strong"),
            clarity=DimensionScore(score=0.75, justification="Clear"),
            overall=0.75,
        )
        mock_evaluator.evaluate = AsyncMock(return_value=expected)

        stage = EvaluationStage(evaluator=mock_evaluator)
        result = asyncio.run(stage.execute(ctx))

        assert result is True
        metadata = stage._get_metadata(proposal)
        assert "evaluation" in metadata, "evaluation key must be in metadata"

        ev = metadata["evaluation"]
        assert ev["novelty"]["score"] == 0.8
        assert ev["feasibility"]["score"] == 0.7
        assert ev["completeness"]["score"] == 0.6
        assert ev["rigor"]["score"] == 0.9
        assert ev["clarity"]["score"] == 0.75
        assert ev["overall"] == 0.75

    def test_fallback_on_llm_failure(self):
        from backend.pipeline.stages import EvaluationStage

        proposal = _make_proposal()
        ctx = _make_ctx(proposals={0: proposal})

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        stage = EvaluationStage(evaluator=mock_evaluator)
        result = asyncio.run(stage.execute(ctx))

        assert result is True, "Stage must not crash on LLM failure"
        metadata = stage._get_metadata(proposal)
        assert "evaluation" in metadata, "Default evaluation must be stored"

        ev = metadata["evaluation"]
        for dim in ("novelty", "feasibility", "completeness", "rigor", "clarity"):
            assert ev[dim]["score"] == 0.0, (
                f"Default score for {dim} must be 0.0 on failure"
            )
        assert ev["overall"] == 0.0


class TestEvaluationSkippedWhenDisabled:
    """TEST-156-01-05: Stage skipped when flag disabled."""

    def test_skipped_when_strategy_disables(self):
        from backend.pipeline.stages import EvaluationStage
        from backend.pipeline.strategies import PipelineStrategy
        from backend.pipeline.strategies.models import StageConfig, StrategyConfig

        proposal = _make_proposal()
        strategy_config = StrategyConfig(
            name=PipelineStrategy.FAST_SCAN,
            stages={"evaluation": StageConfig(enabled=False)},
        )
        ctx = _make_ctx(
            proposals={0: proposal},
            params={"strategy_config": strategy_config},
        )

        mock_evaluator = MagicMock()
        mock_evaluator.evaluate = AsyncMock()

        stage = EvaluationStage(evaluator=mock_evaluator)
        result = asyncio.run(stage.execute(ctx))

        assert result is True
        mock_evaluator.evaluate.assert_not_called(), (
            "Evaluator must not be called when stage is disabled"
        )


# ---------------------------------------------------------------------------
# TASK-03 Tests (backend presets)
# ---------------------------------------------------------------------------


class TestPresetsEvaluationConfig:
    """TEST-156-03-03: deep_research enables evaluation."""

    def test_deep_research_enables_evaluation(self):
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get("deep_research")
        eval_stage = config.stages.get("evaluation")
        assert eval_stage is not None, "evaluation stage must exist in deep_research"
        assert eval_stage.enabled is True, "evaluation must be enabled in deep_research"

    def test_fast_scan_disables_evaluation(self):
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get("fast_scan")
        eval_stage = config.stages.get("evaluation")
        assert eval_stage is not None, "evaluation stage must exist in fast_scan"
        assert eval_stage.enabled is False, "evaluation must be disabled in fast_scan"

    def test_academic_proposal_enables_evaluation(self):
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get("academic_proposal")
        eval_stage = config.stages.get("evaluation")
        assert eval_stage is not None, "evaluation stage must exist in academic_proposal"
        assert eval_stage.enabled is True, "evaluation must be enabled in academic_proposal"

    def test_literature_review_disables_evaluation(self):
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get("literature_review")
        eval_stage = config.stages.get("evaluation")
        assert eval_stage is not None, "evaluation stage must exist in literature_review"
        assert eval_stage.enabled is False, "evaluation must be disabled in literature_review"
