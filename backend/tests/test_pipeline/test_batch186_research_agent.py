"""Tests for BATCH-186: Research Sub-Agent for Literature Search.

AIV §13 Test Integrity: Tests verify behavioral outcomes
(sub-agent returns papers, respects limits, detects doom),
not code structure.
"""

import asyncio

import pytest

from backend.pipeline.literature.research_agent import (
    ResearchResult,
    ResearchSubAgent,
    run_parallel_research,
)


# ── Mock search function ─────────────────────────────────────────────

async def _mock_search(query: str, domain: str) -> list[dict]:
    """Returns fake papers for testing."""
    if "empty" in query:
        return []
    return [
        {
            "title": f"Paper about {query[:30]} in {domain}",
            "abstract": "A" * 400,
            "doi": f"10.1234/{hash(query) % 10000}",
        }
    ]


async def _mock_search_limited(query: str, domain: str) -> list[dict]:
    """Returns papers only on first call, empty after."""
    call_count = getattr(_mock_search_limited, "_calls", 0)
    call_count += 1
    _mock_search_limited._calls = call_count
    if call_count > 2:
        return []
    return [
        {"title": f"Limited paper {call_count}", "abstract": "B" * 200}
    ]


async def _mock_search_always_empty(query: str, domain: str) -> list[dict]:
    """Always returns empty — triggers doom if same query repeated."""
    return []


async def _mock_search_error(query: str, domain: str) -> list[dict]:
    """Always raises — tests error handling."""
    raise ConnectionError("Search API down")


# ── ResearchSubAgent Tests ────────────────────────────────────────────


class TestResearchSubAgent:
    """Sub-agent returns papers and respects limits."""

    def test_01_returns_papers(self):
        """Sub-agent calls search_fn and returns results."""
        async def _run():
            agent = ResearchSubAgent(
                query="transformer attention mechanisms",
                domain="NLP",
                search_fn=_mock_search,
                max_iterations=5,
            )
            result = await agent.run()
            assert isinstance(result, ResearchResult)
            assert result.query == "transformer attention mechanisms"
            assert len(result.papers) > 0
            assert result.iterations_used >= 1
        asyncio.run(_run())

    def test_02_iteration_limit_respected(self):
        """Stops after max_iterations."""
        async def _run():
            agent = ResearchSubAgent(
                query="deep learning",
                domain="AI",
                search_fn=_mock_search_limited,
                max_iterations=3,
            )
            result = await agent.run()
            assert result.iterations_used <= 3
        asyncio.run(_run())

    def test_03_context_budget_hard_stop(self):
        """Stops when context budget is exceeded."""
        async def _run():
            # Very small budget — should stop quickly
            agent = ResearchSubAgent(
                query="attention",
                domain="AI",
                search_fn=_mock_search,
                max_iterations=50,
                context_budget=200,  # very small
            )
            result = await agent.run()
            assert result.truncated is True
        asyncio.run(_run())

    def test_04_empty_query_returns_empty(self):
        """Empty query produces empty or minimal results."""
        async def _run():
            async def _empty_search(q, d):
                return [] if "empty" in q else [{"title": "Fallback", "abstract": "x"}]
            agent = ResearchSubAgent(
                query="empty results query",
                domain="AI",
                search_fn=_empty_search,
                max_iterations=3,
            )
            result = await agent.run()
            # Empty search results → agent tries refinements but gets empty
            assert isinstance(result.papers, list)
        asyncio.run(_run())

    def test_05_doom_detected(self):
        """Identical queries trigger doom detection."""
        async def _run():
            # With always-empty results and same refinement pattern,
            # the agent should detect doom
            agent = ResearchSubAgent(
                query="test",
                domain="AI",
                search_fn=_mock_search_always_empty,
                max_iterations=10,
            )
            # Force doom by making search history identical
            agent._search_history = ["test", "test", "test"]
            assert agent._check_doom() is True
        asyncio.run(_run())

    def test_06_error_handling(self):
        """Search errors don't crash the sub-agent."""
        async def _run():
            agent = ResearchSubAgent(
                query="test",
                domain="AI",
                search_fn=_mock_search_error,
                max_iterations=3,
            )
            result = await agent.run()
            assert result.papers == []
        asyncio.run(_run())


class TestRunParallelResearch:
    """Parallel research runs multiple agents concurrently."""

    def test_07_parallel_agents(self):
        """3 queries run in parallel and return results."""
        async def _run():
            results = await run_parallel_research(
                queries=["transformers", "MoE routing", "retrieval augmentation"],
                domain="AI",
                search_fn=_mock_search,
                max_iterations=3,
            )
            assert len(results) == 3
            assert all(isinstance(r, ResearchResult) for r in results)
        asyncio.run(_run())

    def test_08_parallel_with_error(self):
        """One failing agent doesn't crash the others."""
        async def _run():
            call_count = 0
            async def _flaky_search(q, d):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise RuntimeError("Flaky")
                return [{"title": f"Paper {call_count}", "abstract": "x" * 200}]

            results = await run_parallel_research(
                queries=["q1", "q2", "q3"],
                domain="AI",
                search_fn=_flaky_search,
                max_iterations=3,
            )
            assert len(results) == 3
            # At least one should have papers
            successful = [r for r in results if len(r.papers) > 0]
            assert len(successful) >= 1
        asyncio.run(_run())
