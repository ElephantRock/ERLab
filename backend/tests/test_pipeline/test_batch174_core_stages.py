"""BATCH-174 TASK-01: Core Stage Functional Tests (stages 0-8).

Instantiate each stage with mocked dependencies, create a StageContext,
execute via asyncio.run(), and assert meaningful output on PipelineResult.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# ── Stub heavy imports before anything else ─────────────────────────────────
sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.gap_analysis.models import ClusterReport, ResearchGap
from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    FeasibilityScoringStage,
    GapAnalysisStage,
    IdeaGenerationStage,
    IngestionStage,
    LiteratureSearchStage,
    MechanicalMetricsStage,
    NoveltyCheckingStage,
    StageContext,
)

# ── Helpers ──────────────────────────────────────────────────────────────────

def _paper(idx: int = 0) -> Paper:
    return Paper(
        id=f"p{idx}",
        source="test",
        title=f"Test Paper {idx}: NLP advances",
        abstract=f"Abstract for paper {idx} on NLP methodology.",
        authors=[Author(name=f"Author {idx}")],
        year=2024,
    )


def _gap(title: str = "Test Gap", description: str = "A test gap") -> ResearchGap:
    return ResearchGap(
        title=title,
        description=description,
        gap_type="methodological",
        related_clusters=[1],
        potential_impact="High",
        confidence=0.8,
    )


def _idea(title: str = "Test Idea", score: float = 0.7) -> ResearchIdea:
    return ResearchIdea(
        title=title,
        problem_statement="A test problem",
        proposed_method="Do X and Y",
        expected_contributions="Better results",
        novelty_rationale="Novel combination",
        evaluation_approach="Benchmark testing",
        domain="AI/NLP",
        round_generated=1,
        score=score,
        supporting_papers=["p0"],
        source_gap_ids=["Test Gap"],
    )


def _ctx(**overrides) -> StageContext:
    defaults = dict(result=PipelineResult(), all_papers=[], domain="AI/NLP")
    defaults.update(overrides)
    return StageContext(**defaults)


# ── 1. LiteratureSearchStage ────────────────────────────────────────────────


class TestLiteratureSearchStage:
    """Stage 0: literature search via mocked search service."""

    def test_populates_all_papers(self):
        search = AsyncMock()
        # Use very distinct titles to avoid fuzzy dedup (>0.85 similarity)
        paper1 = Paper(
            id="p1", source="test",
            title="Transformer attention mechanisms for NLU",
            abstract="Abstract on attention.",
            authors=[Author(name="A")], year=2024,
        )
        paper2 = Paper(
            id="p2", source="test",
            title="Reinforcement learning for robotic manipulation",
            abstract="Abstract on RL robotics.",
            authors=[Author(name="B")], year=2024,
        )
        search.search_all = AsyncMock(return_value=[paper1, paper2])

        hooks = MagicMock()
        hooks.dispatch_sync_safe = AsyncMock()

        stage = LiteratureSearchStage(search=search, hooks=hooks)
        ctx = _ctx(search_queries=["test query"])
        ok = asyncio.run(stage.execute(ctx))

        assert ok is True
        assert ctx.result.papers_found >= 2
        assert len(ctx.all_papers) >= 2

    def test_handles_empty_results(self):
        search = AsyncMock()
        search.search_all = AsyncMock(return_value=[])

        hooks = MagicMock()
        hooks.dispatch_sync_safe = AsyncMock()

        stage = LiteratureSearchStage(search=search, hooks=hooks)
        ctx = _ctx(search_queries=["empty query"])
        ok = asyncio.run(stage.execute(ctx))

        # Stage returns False (halt) when no papers found — pipeline should not
        # continue to gap analysis without paper abstracts.
        assert ok is False
        assert ctx.result.papers_found == 0


# ── 2. IngestionStage ──────────────────────────────────────────────────────


class TestIngestionStage:
    """Stage 1: ingestion of papers into store/bm25/embedding."""

    def test_counts_papers(self):
        papers = [_paper(i) for i in range(5)]
        store = AsyncMock()
        store.add_papers = AsyncMock(return_value=5)
        bm25 = MagicMock()
        embedding = MagicMock()

        stage = IngestionStage(store=store, bm25=bm25, embedding=embedding)
        ctx = _ctx(all_papers=papers)
        ok = asyncio.run(stage.execute(ctx))

        assert ok is True
        store.add_papers.assert_awaited_once()
        assert len(ctx.all_papers) == 5  # deduplicated in-place


# ── 3. GapAnalysisStage ────────────────────────────────────────────────────


class TestGapAnalysisStage:
    """Stage 2: gap analysis via mocked gap_analyzer."""

    def test_populates_gaps(self):
        gap = _gap()
        cluster_report = ClusterReport(clusters=[], total_papers=3)

        gap_analyzer = MagicMock()
        gap_analyzer.analyze = AsyncMock(return_value=([gap], cluster_report))

        goal_manager = MagicMock()
        goal_manager.create_from_gaps = MagicMock(return_value=[])

        hooks = MagicMock()
        hooks.dispatch_sync_safe = AsyncMock()

        memory = AsyncMock()
        memory.recall = AsyncMock(return_value=None)

        stage = GapAnalysisStage(
            gap_analyzer=gap_analyzer,
            goal_manager=goal_manager,
            hooks=hooks,
            memory=memory,
        )
        ctx = _ctx(all_papers=[_paper(0)])

        # Patch asyncio.sleep so the 2-second pause doesn't slow tests
        _orig_sleep = asyncio.sleep
        asyncio.sleep = AsyncMock()
        try:
            ok = asyncio.run(stage.execute(ctx))
        finally:
            asyncio.sleep = _orig_sleep

        assert ok is True
        assert len(ctx.result.gaps) == 1
        assert ctx.result.gaps[0].title == "Test Gap"
        assert ctx.result.cluster_report is not None


# ── 4. GapReflectionStage ──────────────────────────────────────────────────


class TestGapReflectionStage:
    """Stage 2b: gap reflection via mocked reflector."""

    def test_populates_ideas(self):
        idea = _idea()
        agent = MagicMock()
        agent.run = AsyncMock(return_value=[idea])
        agent.last_critique_history = {}
        agent.last_refinement_history = {}

        hooks = MagicMock()
        hooks.dispatch_sync_safe = AsyncMock()

        stage = IdeaGenerationStage(agent=agent, hooks=hooks)
        ctx = _ctx(result=PipelineResult(gaps=[_gap()], ideas=[]))
        ok = asyncio.run(stage.execute(ctx))

        assert ok is True
        assert len(ctx.result.ideas) == 1
        assert ctx.result.ideas[0].title == "Test Idea"


# ── 6. IdeaReflectionStage ─────────────────────────────────────────────────


class TestIdeaReflectionStage:
    """Stage 3b: idea reflection via mocked reflector."""

    def test_populates_feasibility_reports(self):
        from backend.pipeline.feasibility.feasibility_scorer import FeasibilityReport

        report = FeasibilityReport(
            overall_score=7.5,
            data_availability=8.0,
            computational_requirements=7.0,
            methodological_complexity=6.0,
            evaluation_plan=8.0,
            novelty_grounding=7.0,
            impact_potential=8.0,
            reasoning="Strong",
            estimated_timeline="6 months",
            key_risks=["Data quality"],
        )
        scorer = MagicMock()
        scorer.score_feasibility = AsyncMock(return_value=report)
        scorer.run_counterfactual = AsyncMock(return_value=report)  # also mock counterfactual

        # Monkey-patch get_settings to return a config with counterfactual_enabled=False
        import backend.config as _cfg
        mock_settings = MagicMock()
        mock_settings.counterfactual_enabled = False

        stage = FeasibilityScoringStage(feasibility_scorer=scorer)
        ctx = _ctx(result=PipelineResult(ideas=[_idea()]))

        # Patch get_settings used inside _execute_feasibility
        orig = getattr(_cfg, "get_settings", None)
        _cfg.get_settings = lambda: mock_settings
        try:
            ok = asyncio.run(stage.execute(ctx))
        finally:
            if orig:
                _cfg.get_settings = orig

        assert ok is True
        assert 0 in ctx.result.feasibility_reports
        assert ctx.result.feasibility_reports[0].overall_score == 7.5


# ── 9. MechanicalMetricsStage ──────────────────────────────────────────────


class TestMechanicalMetricsStage:
    """Stage 6: mechanical metrics computation."""

    def test_populates_metrics(self):
        stage = MechanicalMetricsStage()
        idea = _idea()
        ctx = _ctx(
            result=PipelineResult(
                ideas=[idea],
                gaps=[_gap()],
            ),
            all_papers=[_paper(i) for i in range(5)],
        )
        ok = asyncio.run(stage.execute(ctx))

        assert ok is True
        assert 0 in ctx.result.mechanical_metrics
        metrics = ctx.result.mechanical_metrics[0]
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
        # All metric values should be between 0 and 1
        for v in metrics.values():
            assert 0.0 <= v <= 1.0
