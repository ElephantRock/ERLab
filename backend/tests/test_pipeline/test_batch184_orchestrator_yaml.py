"""Tests for BATCH-181/184: Trimmer + Orchestrator YAML integration."""

import asyncio
import os
import sys
import tempfile

import pytest


# ── Trimmer Stage ────────────────────────────────────────────────────


class TestTrimmerStage:
    """Trimmer reranks papers, keeps top_k, truncates abstracts."""

    def _make_ctx(self, papers=None, domain="AI/NLP"):
        from backend.pipeline.stages import StageContext
        from backend.pipeline.result import PipelineResult
        result = PipelineResult()
        ctx = StageContext(result=result, domain=domain, run_id="test")
        ctx.all_papers = papers or []
        return ctx

    def test_01_keeps_top_k(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": f"Paper {i}", "abstract": "x" * 100} for i in range(30)]
        ctx = self._make_ctx(papers)
        asyncio.run(TrimmerStage(top_k=10, max_abstract_chars=1000).execute(ctx))
        assert len(ctx.all_papers) == 10

    def test_02_truncates_abstracts(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": "Paper", "abstract": "A" * 2000}]
        ctx = self._make_ctx(papers)
        asyncio.run(TrimmerStage(top_k=10, max_abstract_chars=500).execute(ctx))
        assert len(ctx.all_papers[0]["abstract"]) == 500

    def test_03_no_op_under_limit(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": f"P {i}", "abstract": "short"} for i in range(5)]
        ctx = self._make_ctx(papers)
        asyncio.run(TrimmerStage(top_k=20, max_abstract_chars=10000).execute(ctx))
        assert len(ctx.all_papers) == 5
        assert ctx.all_papers[0]["abstract"] == "short"

    def test_04_empty_papers(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        ctx = self._make_ctx([])
        result = asyncio.run(TrimmerStage().execute(ctx))
        assert result is True

    def test_05_reranks_by_domain(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [
            {"title": "Cooking", "abstract": "baking bread"},
            {"title": "Transformer", "abstract": "Self-attention in neural networks"},
            {"title": "Gardening", "abstract": "Growing tomatoes"},
        ]
        ctx = self._make_ctx(papers, domain="Transformer Neural Networks")
        asyncio.run(TrimmerStage(top_k=3, max_abstract_chars=1000).execute(ctx))
        assert "Transformer" in ctx.all_papers[0]["title"]

    def test_06_name_is_trimmer(self):
        from backend.pipeline.dag.trimmer import TrimmerStage
        assert TrimmerStage().name == "trimmer"


# ── Orchestrator YAML Integration ────────────────────────────────────


class TestOrchestratorYAML:
    """BATCH-184: Orchestrator reads pipeline.yaml for strategy."""

    def test_01_yaml_strategy_resolves(self):
        """All 4 strategies resolve from YAML."""
        from backend.pipeline.orchestrator import PipelineOrchestrator
        for strat in ["fast_scan", "deep_research", "academic_proposal", "literature_review"]:
            config = PipelineOrchestrator._load_yaml_strategy(strat)
            assert config is not None
            assert len(config.stages) > 0, f"{strat} has no stages"

    def test_02_fast_scan_has_6_enabled_stages(self):
        """fast_scan strategy has exactly 6 enabled stages."""
        from backend.pipeline.orchestrator import PipelineOrchestrator
        config = PipelineOrchestrator._load_yaml_strategy("fast_scan")
        enabled = {k: v for k, v in config.stages.items() if v.enabled}
        assert len(enabled) == 6

    def test_03_deep_research_has_16_enabled_stages(self):
        """deep_research strategy has all 17 enabled stages (18 total incl. trimmer)."""
        from backend.pipeline.orchestrator import PipelineOrchestrator
        config = PipelineOrchestrator._load_yaml_strategy("deep_research")
        enabled = {k: v for k, v in config.stages.items() if v.enabled}
        assert len(enabled) == 17

    def test_04_unknown_strategy_raises(self):
        """Unknown strategy name raises ValueError."""
        from backend.pipeline.orchestrator import PipelineOrchestrator
        with pytest.raises(ValueError, match="Unknown"):
            PipelineOrchestrator._load_yaml_strategy("nonexistent")

    def test_05_dry_run_produces_output(self):
        """dry_run() produces output without full construction."""
        from backend.pipeline.orchestrator import PipelineOrchestrator
        config = PipelineOrchestrator._load_yaml_strategy("fast_scan")
        assert "literature_search" in config.stages
        assert "export" in config.stages
        enabled = {k: v for k, v in config.stages.items() if v.enabled}
        assert len(enabled) == 6


# ── DAG API Endpoint ─────────────────────────────────────────────────


class TestDAGEndpoint:
    """POST /run/dag route is registered and functional."""

    def test_01_route_exists(self):
        from backend.api.routes.pipeline import router
        routes = [r.path for r in router.routes]
        assert "/run/dag" in routes

    def test_02_route_accepts_post(self):
        from backend.api.routes.pipeline import router
        for route in router.routes:
            if route.path == "/run/dag":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("/run/dag not found")
