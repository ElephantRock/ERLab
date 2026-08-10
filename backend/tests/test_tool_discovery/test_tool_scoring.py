"""Tests for post-retrieval tool scoring."""

from datetime import datetime, timedelta

from backend.pipeline.tools.registry import ToolDefinition
from backend.pipeline.tools.tool_index import ToolSearchResult
from backend.pipeline.tools.tool_scoring import ToolScore, ToolScorer


def _make_tool(name: str, trust_level: str = "trusted") -> ToolDefinition:
    async def handler(**kwargs):
        return "ok"

    return ToolDefinition(
        name=name,
        description=f"Tool: {name}",
        parameters={},
        handler=handler,
        trust_level=trust_level,
    )


class TestToolScorer:
    def test_basic_scoring(self):
        scorer = ToolScorer()
        results = [ToolSearchResult(tool_name="tool_a", score=0.8, source="semantic")]
        tools = {"tool_a": _make_tool("tool_a")}
        scores = scorer.score(results, tools)
        assert len(scores) == 1
        assert scores[0].composite > 0

    def test_trusted_tool_no_penalty(self):
        scorer = ToolScorer(trust_penalty=0.2)
        results = [ToolSearchResult(tool_name="safe", score=0.9, source="semantic")]
        tools = {"safe": _make_tool("safe", trust_level="trusted")}
        scores = scorer.score(results, tools)
        assert scores[0].trust_penalty == 0.0

    def test_untrusted_tool_gets_penalty(self):
        scorer = ToolScorer(trust_penalty=0.3)
        results = [ToolSearchResult(tool_name="risky", score=0.9, source="semantic")]
        tools = {"risky": _make_tool("risky", trust_level="untrusted")}
        scores = scorer.score(results, tools)
        assert scores[0].trust_penalty == 0.3

    def test_recency_bonus_for_recently_used(self):
        scorer = ToolScorer(recency_weight=0.1)
        results = [ToolSearchResult(tool_name="recent", score=0.5, source="semantic")]
        tools = {"recent": _make_tool("recent")}
        history = {"recent": datetime.now() - timedelta(days=1)}
        scores = scorer.score(results, tools, usage_history=history)
        assert scores[0].recency_bonus > 0

    def test_no_recency_bonus_for_old_usage(self):
        scorer = ToolScorer(recency_weight=0.1)
        results = [ToolSearchResult(tool_name="old", score=0.5, source="semantic")]
        tools = {"old": _make_tool("old")}
        history = {"old": datetime.now() - timedelta(days=60)}
        scores = scorer.score(results, tools, usage_history=history)
        assert scores[0].recency_bonus == 0.0

    def test_no_recency_bonus_without_history(self):
        scorer = ToolScorer(recency_weight=0.1)
        results = [ToolSearchResult(tool_name="never", score=0.5, source="semantic")]
        tools = {"never": _make_tool("never")}
        scores = scorer.score(results, tools)
        assert scores[0].recency_bonus == 0.0

    def test_composite_capped_at_zero(self):
        scorer = ToolScorer(trust_penalty=1.0, relevance_weight=0.1, recency_weight=0.0)
        results = [ToolSearchResult(tool_name="bad", score=0.01, source="semantic")]
        tools = {"bad": _make_tool("bad", trust_level="untrusted")}
        scores = scorer.score(results, tools)
        assert scores[0].composite >= 0.0

    def test_scores_sorted_by_composite(self):
        scorer = ToolScorer(trust_penalty=0.5)
        results = [
            ToolSearchResult(tool_name="high", score=0.9, source="semantic"),
            ToolSearchResult(tool_name="low", score=0.1, source="semantic"),
        ]
        tools = {
            "high": _make_tool("high", trust_level="trusted"),
            "low": _make_tool("low", trust_level="untrusted"),
        }
        scores = scorer.score(results, tools)
        assert scores[0].composite >= scores[1].composite

    def test_custom_weights(self):
        scorer = ToolScorer(relevance_weight=0.5, recency_weight=0.5, trust_penalty=0.0)
        assert scorer._relevance_weight == 0.5
        assert scorer._recency_weight == 0.5

    def test_skips_unknown_tools(self):
        scorer = ToolScorer()
        results = [ToolSearchResult(tool_name="ghost", score=0.9, source="semantic")]
        scores = scorer.score(results, {})
        assert scores == []

    def test_tool_score_model_fields(self):
        score = ToolScore(tool_name="t", relevance=0.8, trust_penalty=0.1, recency_bonus=0.2, composite=0.7)
        assert score.tool_name == "t"
        assert score.composite == 0.7
