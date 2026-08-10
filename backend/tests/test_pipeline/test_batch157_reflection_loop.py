"""BATCH-157: Iterative Reflection Loop — Gap + Idea reflection stages.

TASK-01: GapReflectionStage (5 tests)
TASK-02: IdeaReflectionStage (5 tests)
TASK-03: Strategy Presets (2 tests)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

# ─── Helpers ────────────────────────────────────────────────

def _make_stage_context(gaps=None, ideas=None, domain="test domain"):
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext
    result = PipelineResult()
    if gaps is not None:
        result.gaps = gaps
    if ideas is not None:
        result.ideas = ideas
    return StageContext(result=result, all_papers=[], domain=domain, params={})


def _make_mock_provider(score=0.8):
    """Mock LLM provider that returns a reflection score."""
    provider = MagicMock()
    provider.complete = AsyncMock(return_value=(
        f"SCORE: {score}\n"
        f"PASSED: {'yes' if score >= 0.6 else 'no'}\n"
        f"JUSTIFICATION: Test justification\n"
        f"FEEDBACK: Improve the analysis quality.\n"
    ))
    return provider


# ─── TASK-01: GapReflectionStage ───────────────────────────

class TestGapReflectionStage:

    def test_01_gap_reflection_in_stage_order(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator
        assert "gap_reflection" in PipelineOrchestrator._STAGE_ORDER

    def test_02_gap_reflection_after_gap_analysis(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator
        order = PipelineOrchestrator._STAGE_ORDER
        gap_idx = order.index("gap_analysis")
        ref_idx = order.index("gap_reflection")
        assert ref_idx == gap_idx + 1, "gap_reflection should be right after gap_analysis"

    def test_04_graceful_fallback_on_failure(self):
        from backend.pipeline.reflection.reflector import ReflectionStage
        from backend.pipeline.stages import GapReflectionStage

        mock_reflector = MagicMock(spec=ReflectionStage)
        mock_reflector.reflect_gaps = AsyncMock(side_effect=Exception("LLM down"))

        gap = MagicMock()
        stage = GapReflectionStage(reflector=mock_reflector)
        ctx = _make_stage_context(gaps=[gap])

        result = asyncio.run(stage.execute(ctx))
        assert result is True  # HB-02: non-fatal

    def test_05_skipped_when_disabled(self):
        from backend.pipeline.stages import GapReflectionStage
        from backend.pipeline.strategies.models import StageConfig

        mock_reflector = MagicMock()
        stage = GapReflectionStage(reflector=mock_reflector)
        ctx = _make_stage_context(gaps=[MagicMock()])
        ctx.params = {"strategy_config": MagicMock()}
        ctx.params["strategy_config"].stages = {"gap_reflection": StageConfig(enabled=False)}

        result = asyncio.run(stage.execute(ctx))
        assert result is True
        mock_reflector.reflect_gaps.assert_not_called()


# ─── TASK-02: IdeaReflectionStage ──────────────────────────

class TestIdeaReflectionStage:

    def test_06_idea_reflection_in_stage_order(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator
        assert "idea_reflection" in PipelineOrchestrator._STAGE_ORDER

    def test_07_idea_reflection_after_idea_generation(self):
        from backend.pipeline.orchestrator import PipelineOrchestrator
        order = PipelineOrchestrator._STAGE_ORDER
        idea_gen_idx = order.index("idea_generation")
        ref_idx = order.index("idea_reflection")
        assert ref_idx == idea_gen_idx + 1

    def test_09_graceful_fallback_on_failure(self):
        from backend.pipeline.reflection.reflector import ReflectionStage
        from backend.pipeline.stages import IdeaReflectionStage

        mock_reflector = MagicMock(spec=ReflectionStage)
        mock_reflector.reflect_ideas = AsyncMock(side_effect=Exception("Timeout"))

        stage = IdeaReflectionStage(reflector=mock_reflector)
        ctx = _make_stage_context(ideas=[MagicMock()])

        result = asyncio.run(stage.execute(ctx))
        assert result is True  # HB-02

    def test_10_skipped_when_disabled(self):
        from backend.pipeline.stages import IdeaReflectionStage
        from backend.pipeline.strategies.models import StageConfig

        mock_reflector = MagicMock()
        stage = IdeaReflectionStage(reflector=mock_reflector)
        ctx = _make_stage_context(ideas=[MagicMock()])
        ctx.params = {"strategy_config": MagicMock()}
        ctx.params["strategy_config"].stages = {"idea_reflection": StageConfig(enabled=False)}

        result = asyncio.run(stage.execute(ctx))
        assert result is True
        mock_reflector.reflect_ideas.assert_not_called()


# ─── TASK-03: Strategy Presets ─────────────────────────────

class TestReflectionPresets:

    def test_11_deep_research_enables_reflection(self):
        from backend.pipeline.strategies.models import PipelineStrategy
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get(PipelineStrategy.DEEP_RESEARCH)
        assert "gap_reflection" in config.stages
        assert "idea_reflection" in config.stages

    def test_12_fast_scan_disables_reflection(self):
        from backend.pipeline.strategies.models import PipelineStrategy
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get(PipelineStrategy.FAST_SCAN)
        assert not config.stages["gap_reflection"].enabled
        assert not config.stages["idea_reflection"].enabled
