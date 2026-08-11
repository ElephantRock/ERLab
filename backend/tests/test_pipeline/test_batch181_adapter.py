"""Tests for BATCH-181: Trimmer + Adapter + DAG API endpoint."""

import asyncio

import pytest

# ── TASK-01: Trimmer Stage ────────────────────────────────────────────


class TestTrimmerStage:
    """TEST-181-01-01 through TEST-181-01-06."""

    def _make_ctx(self, papers=None, domain="AI/NLP"):
        """Create a mock old-style StageContext with papers."""
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import StageContext
        result = PipelineResult()
        ctx = StageContext(result=result, domain=domain, run_id="test")
        ctx.all_papers = papers or []
        return ctx

    def test_01_trimmer_keeps_top_k(self):
        """TEST-181-01-01: Trimmer keeps only top_k papers."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": f"Paper {i}", "abstract": "x" * 100} for i in range(30)]
        ctx = self._make_ctx(papers)
        stage = TrimmerStage(top_k=10, max_abstract_chars=1000)
        result = asyncio.run(stage.execute(ctx))
        assert result is True
        assert len(ctx.all_papers) == 10

    def test_02_trimmer_truncates_abstracts(self):
        """TEST-181-01-02: Trimmer truncates abstracts to max_abstract_chars."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": "Paper", "abstract": "A" * 2000}]
        ctx = self._make_ctx(papers)
        stage = TrimmerStage(top_k=10, max_abstract_chars=500)
        asyncio.run(stage.execute(ctx))
        assert len(ctx.all_papers[0]["abstract"]) == 500

    def test_03_trimmer_no_op_when_under_limit(self):
        """TEST-181-01-03: Trimmer does nothing when papers < top_k."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [{"title": f"Paper {i}", "abstract": "short"} for i in range(5)]
        ctx = self._make_ctx(papers)
        stage = TrimmerStage(top_k=20, max_abstract_chars=10000)
        asyncio.run(stage.execute(ctx))
        assert len(ctx.all_papers) == 5
        assert ctx.all_papers[0]["abstract"] == "short"

    def test_04_trimmer_empty_papers(self):
        """TEST-181-01-04: Trimmer handles empty paper list gracefully."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        ctx = self._make_ctx([])
        stage = TrimmerStage()
        result = asyncio.run(stage.execute(ctx))
        assert result is True
        assert len(ctx.all_papers) == 0

    def test_05_trimmer_reranks_by_domain(self):
        """TEST-181-01-05: Trimmer reranks papers by domain relevance."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        papers = [
            {"title": "Cooking Recipes", "abstract": "How to bake bread"},
            {"title": "Transformer Architecture", "abstract": "Self-attention mechanism in neural networks"},
            {"title": "Gardening Tips", "abstract": "Growing tomatoes in your garden"},
        ]
        ctx = self._make_ctx(papers, domain="Transformer Neural Networks")
        stage = TrimmerStage(top_k=3, max_abstract_chars=1000)
        asyncio.run(stage.execute(ctx))
        assert "Transformer" in ctx.all_papers[0]["title"]

    def test_06_trimmer_name_property(self):
        """TEST-181-01-06: Trimmer stage name is 'trimmer'."""
        from backend.pipeline.dag.trimmer import TrimmerStage
        stage = TrimmerStage()
        assert stage.name == "trimmer"


# ── TASK-02: DAGStageAdapter (context mapping only — stage build is integration test) ──


class TestContextMapping:
    """TEST-181-02-05 and TEST-181-02-06: Context mapping functions."""

    def test_01_dag_endpoint_exists_in_routes(self):
        """TEST-181-03-01: /run/dag route is registered."""
        from backend.api.routes.pipeline import router
        routes = [r.path for r in router.routes]
        assert "/run/dag" in routes, f"Routes: {routes}"

    def test_02_dag_endpoint_has_post_method(self):
        """TEST-181-03-02: /run/dag accepts POST."""
        from backend.api.routes.pipeline import router
        for route in router.routes:
            if route.path == "/run/dag":
                assert "POST" in route.methods
                break
        else:
            pytest.fail("/run/dag route not found")

    def test_03_dag_handler_signature(self):
        """TEST-181-03-03: DAG handler accepts PipelineRunRequest."""
        import inspect

        from backend.api.routes.pipeline import trigger_dag_run
        sig = inspect.signature(trigger_dag_run)
        params = list(sig.parameters.keys())
        assert "request" in params
