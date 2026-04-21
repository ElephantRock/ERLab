"""Compaction middleware — prepares optimized context for each pipeline stage."""

from __future__ import annotations

import copy
import logging

from backend.pipeline.compaction.budget_manager import (
    CompactionRecommendation,
    ContextBudgetManager,
)
from backend.pipeline.compaction.paper_selector import PaperSelector
from backend.pipeline.compaction.summarizer import ContextSummarizer
from backend.providers.base import LLMProvider
from backend.providers.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class CompactionMiddleware:
    """Prepares compacted context views for each pipeline stage.

    Sits between the orchestrator's stage loop and individual stages.
    Before a stage runs, ``prepare_context()`` creates a compacted view.
    After a stage runs, ``record_usage()`` snapshots token consumption.

    When disabled, all methods are pass-through — zero overhead.

    The context parameter is typed as ``object`` to avoid importing the
    heavy ``StageContext`` -> ``PipelineResult`` -> chromadb chain at module
    level. The orchestrator always passes a real ``StageContext``.
    """

    def __init__(
        self,
        provider: LLMProvider,
        token_counter: TokenCounter,
        *,
        enabled: bool = False,
        smart_truncation: bool = True,
        summarization: bool = True,
        budget_management: bool = True,
        global_token_limit: int = 500000,
    ) -> None:
        self._enabled = enabled
        self._token_counter = token_counter
        self._paper_selector = PaperSelector()
        self._summarizer = ContextSummarizer(provider) if summarization else None
        self._budget_manager = (
            ContextBudgetManager(global_token_limit=global_token_limit)
            if budget_management
            else None
        )
        self._gap_summary: str | None = None
        self._report_summaries: dict[int, str] = {}

    async def prepare_context(self, ctx: object, stage_name: str) -> object:
        """Return a (possibly compacted) context for the stage.

        Creates a shallow copy so ``result`` is shared (stages write there)
        but ``all_papers`` can be filtered independently.
        """
        if not self._enabled:
            return ctx

        if stage_name in ("literature_search", "ingestion", "export"):
            return ctx

        rec = self._get_recommendation(ctx, stage_name)
        compacted = copy.copy(ctx)

        if stage_name == "gap_analysis":
            compacted.all_papers = self._paper_selector.select_papers(  # type: ignore[attr-defined]
                ctx.all_papers,  # type: ignore[attr-defined]
                query=f"{ctx.domain} research gaps",  # type: ignore[attr-defined]
                max_papers=rec.max_papers or 30,
                abstract_budget=rec.max_abstract_chars or 200,
            )

        elif stage_name == "idea_generation":
            gaps = ctx.result.gaps  # type: ignore[attr-defined]
            domain = ctx.domain  # type: ignore[attr-defined]
            query = "; ".join(g.title for g in gaps[:5]) if gaps else domain
            compacted.all_papers = self._paper_selector.select_papers(  # type: ignore[attr-defined]
                ctx.all_papers,  # type: ignore[attr-defined]
                query=query,
                max_papers=rec.max_papers or 20,
                abstract_budget=rec.max_abstract_chars or 150,
            )
            if rec.summarize_gaps and self._summarizer and gaps:
                self._gap_summary = await self._summarizer.summarize_gaps(
                    gaps, ctx.result.cluster_report  # type: ignore[attr-defined]
                )

        elif stage_name == "proposal_synthesis":
            ideas = ctx.result.ideas  # type: ignore[attr-defined]
            if ideas:
                query = f"{ideas[0].title} {ideas[0].proposed_method}"
            else:
                query = ctx.domain  # type: ignore[attr-defined]
            compacted.all_papers = self._paper_selector.select_papers(  # type: ignore[attr-defined]
                ctx.all_papers,  # type: ignore[attr-defined]
                query=query,
                max_papers=rec.max_papers or 10,
                abstract_budget=rec.max_abstract_chars or 100,
            )
            if rec.summarize_reports and self._summarizer:
                for i, idea in enumerate(ideas):
                    novelty = ctx.result.novelty_reports.get(i)  # type: ignore[attr-defined]
                    feasibility = ctx.result.feasibility_reports.get(i)  # type: ignore[attr-defined]
                    if novelty and feasibility and i not in self._report_summaries:
                        self._report_summaries[i] = await self._summarizer.summarize_reports(
                            novelty, feasibility
                        )

        return compacted

    def record_usage(self, stage_name: str) -> None:
        """Record token usage after stage execution."""
        if not self._enabled:
            return
        snapshot = self._token_counter.snapshot()
        if self._budget_manager:
            self._budget_manager.record_consumption(stage_name, snapshot.total_tokens)
        self._token_counter.reset()

    def get_gap_summary(self) -> str | None:
        return self._gap_summary

    def get_report_summary(self, idea_index: int) -> str | None:
        return self._report_summaries.get(idea_index)

    def _get_recommendation(self, ctx: object, stage_name: str) -> CompactionRecommendation:
        if self._budget_manager:
            return self._budget_manager.recommend_compaction(ctx, stage_name)
        return CompactionRecommendation()

    def reset(self) -> None:
        """Clear cached summaries between pipeline runs."""
        self._gap_summary = None
        self._report_summaries.clear()
        if self._budget_manager:
            self._budget_manager._total_consumed = 0
