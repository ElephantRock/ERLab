"""Tests for the ContextBudgetManager."""

from backend.pipeline.compaction.budget_manager import (
    CompactionRecommendation,
    ContextBudgetManager,
    StageTokenBudget,
)


class TestStageTokenBudget:
    def test_current_returns_base(self):
        budget = StageTokenBudget(base=8000, min_budget=2000, max_budget=15000)
        assert budget.current() == 8000

    def test_current_respects_min(self):
        budget = StageTokenBudget(base=8000, min_budget=2000, max_budget=15000, consumed=9000)
        assert budget.current() == 2000


class TestContextBudgetManager:
    def test_record_consumption(self):
        mgr = ContextBudgetManager()
        mgr.record_consumption("gap_analysis", 1000)
        mgr.record_consumption("idea_generation", 2000)
        assert mgr._total_consumed == 3000

    def test_remaining_budget(self):
        mgr = ContextBudgetManager(global_token_limit=10000)
        mgr.record_consumption("gap_analysis", 3000)
        assert mgr.remaining_budget() == 7000

    def test_remaining_budget_floor_zero(self):
        mgr = ContextBudgetManager(global_token_limit=1000)
        mgr.record_consumption("gap_analysis", 2000)
        assert mgr.remaining_budget() == 0

    def test_recommend_compaction_default(self):
        mgr = ContextBudgetManager()
        ctx = _FakeCtx(papers=20, gaps=5, ideas=3)
        rec = mgr.recommend_compaction(ctx, "gap_analysis")
        assert isinstance(rec, CompactionRecommendation)
        assert rec.max_papers == 30  # default for gap_analysis

    def test_recommend_compaction_tight_budget(self):
        mgr = ContextBudgetManager(global_token_limit=1000)
        mgr._total_consumed = 900  # 90% used
        ctx = _FakeCtx(papers=20, gaps=5, ideas=3)
        rec = mgr.recommend_compaction(ctx, "proposal_synthesis")
        assert rec.summarize_gaps is True
        assert rec.summarize_reports is True
        assert rec.max_papers == 7  # half of default 15, min 5

    def test_estimate_context_size(self):
        mgr = ContextBudgetManager()
        ctx = _FakeCtx(papers=30, gaps=5, ideas=3)
        size = mgr.estimate_context_size(ctx, "gap_analysis")
        assert size > 0

    def test_unknown_stage_returns_default_recommendation(self):
        mgr = ContextBudgetManager()
        ctx = _FakeCtx()
        rec = mgr.recommend_compaction(ctx, "unknown_stage")
        assert rec.max_papers is None

    def test_estimate_no_context(self):
        mgr = ContextBudgetManager()
        size = mgr.estimate_context_size(None, "gap_analysis")
        assert size == 0


class _FakeCtx:
    """Minimal mock of StageContext for budget estimation tests."""

    def __init__(self, papers: int = 0, gaps: int = 0, ideas: int = 0):
        self.all_papers = [type("P", (), {"title": f"Paper {i}", "abstract": "x" * 200})() for i in range(papers)]
        self.domain = "AI/NLP"
        self.result = _FakeResult(gaps=gaps, ideas=ideas)


class _FakeResult:
    def __init__(self, gaps: int = 0, ideas: int = 0):
        from backend.pipeline.gap_analysis.models import ResearchGap
        from backend.pipeline.generation.models import ResearchIdea

        self.gaps = [
            ResearchGap(title=f"Gap {i}", description=f"Description {i}" * 20, gap_type="test", confidence=0.5)
            for i in range(gaps)
        ]
        self.ideas = [
            ResearchIdea(
                title=f"Idea {i}",
                problem_statement="x" * 200,
                proposed_method="x" * 200,
                expected_contributions="x" * 100,
                novelty_rationale="x" * 100,
                evaluation_approach="x" * 100,
            )
            for i in range(ideas)
        ]
        self.novelty_reports = {i: "report" for i in range(ideas)}
        self.feasibility_reports = {i: "report" for i in range(ideas)}
        self.critique_history = {}
        self.cluster_report = None
