"""Tests for the CompactionMiddleware."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.compaction.middleware import CompactionMiddleware
from backend.pipeline.literature.models import Paper
from backend.providers.token_counter import TokenCounter


def _make_paper(pid: str, title: str, abstract: str = "Abstract text") -> Paper:
    return Paper(id=pid, source="test", title=title, abstract=abstract)


@dataclass
class _FakeResult:
    """Minimal stand-in for PipelineResult to avoid heavy import chain."""
    ideas: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    novelty_reports: dict = field(default_factory=dict)
    feasibility_reports: dict = field(default_factory=dict)
    cluster_report: Any = None


@dataclass
class _FakeCtx:
    """Minimal stand-in for StageContext."""
    result: _FakeResult
    all_papers: list = field(default_factory=list)
    db_run_id: int | None = None
    params: dict = field(default_factory=dict)
    domain: str = "AI/NLP"
    run_id: str = ""
    search_queries: list[str] | None = None
    max_gaps: int = 5
    rounds: int = 2
    ideas_per: int = 3
    export_format: str | None = "markdown"


def _make_ctx(papers=None):
    return _FakeCtx(result=_FakeResult(), all_papers=papers or [])


class TestCompactionMiddleware:
    def test_disabled_returns_original_context(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=False
        )
        ctx = _make_ctx()
        result = asyncio.run(middleware.prepare_context(ctx, "gap_analysis"))
        assert result is ctx

    def test_passthrough_for_non_compactable_stages(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        ctx = _make_ctx()
        for stage in ("literature_search", "ingestion", "export"):
            result = asyncio.run(middleware.prepare_context(ctx, stage))
            assert result is ctx

    def test_compacted_gap_analysis_filters_papers(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(50)]
        ctx = _make_ctx(papers=papers)

        result = asyncio.run(middleware.prepare_context(ctx, "gap_analysis"))
        assert len(result.all_papers) <= 30
        assert result is not ctx

    def test_compacted_idea_generation(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(50)]
        ctx = _make_ctx(papers=papers)

        result = asyncio.run(middleware.prepare_context(ctx, "idea_generation"))
        assert len(result.all_papers) <= 20

    def test_compacted_proposal_synthesis(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(50)]
        ctx = _make_ctx(papers=papers)

        result = asyncio.run(middleware.prepare_context(ctx, "proposal_synthesis"))
        assert len(result.all_papers) <= 15

    def test_record_usage_snapshots_tokens(self, fake_provider):
        counter = TokenCounter()
        counter.record(input_tokens=500, output_tokens=200)
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        middleware.record_usage("gap_analysis")
        snap = counter.snapshot()
        assert snap.total_tokens == 0

    def test_record_usage_disabled_is_noop(self, fake_provider):
        counter = TokenCounter()
        counter.record(input_tokens=500, output_tokens=200)
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=False
        )
        middleware.record_usage("gap_analysis")
        snap = counter.snapshot()
        assert snap.total_tokens == 700

    def test_original_context_not_modified(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        papers = [_make_paper(f"p{i}", f"Paper {i}") for i in range(50)]
        ctx = _make_ctx(papers=papers)
        original_len = len(ctx.all_papers)

        asyncio.run(middleware.prepare_context(ctx, "gap_analysis"))
        assert len(ctx.all_papers) == original_len

    def test_reset_clears_caches(self, fake_provider):
        counter = TokenCounter()
        middleware = CompactionMiddleware(
            provider=fake_provider, token_counter=counter, enabled=True
        )
        middleware._gap_summary = "some summary"
        middleware._report_summaries[0] = "report summary"
        middleware.reset()
        assert middleware.get_gap_summary() is None
        assert middleware.get_report_summary(0) is None
