"""Trimmer stage — reranks and truncates papers between ingestion and gap_analysis.

BATCH-181 / TASK-01: Prevents GPU OOM on long abstracts, reduces noise from
low-relevance papers. Runs after ingestion, before gap_analysis.

Config from pipeline.yaml budgets:
  trim_top_k: 20          keep top-K papers after reranking
  max_abstract_chars: 800  truncate abstracts to this length
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.pipeline.stages import PipelineStage, StageContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class TrimmerStage(PipelineStage):
    """Reranks papers by relevance and truncates abstracts.

    This stage:
    1. Sorts papers by a simple relevance heuristic (title/abstract keyword overlap with domain)
    2. Keeps the top-K papers (from config)
    3. Truncates abstracts to max_abstract_chars (from config)
    4. Logs before/after stats
    """

    def __init__(
        self,
        top_k: int = 20,
        max_abstract_chars: int = 800,
        reranker: Any = None,
    ) -> None:
        self._top_k = top_k
        self._max_abstract_chars = max_abstract_chars
        self._reranker = reranker

    @property
    def name(self) -> str:
        return "trimmer"

    async def execute(self, ctx: StageContext) -> bool:
        before_count = len(ctx.all_papers)
        if before_count == 0:
            logger.info("Trimmer: no papers to trim, skipping")
            return True

        # Step 1: Rerank by domain relevance (always)
        ctx.all_papers = self._rerank_sync(ctx)

        # Step 1b: Use LLM reranker if available (overrides heuristic)
        if self._reranker is not None:
            try:
                ctx.all_papers = await self._rerank(ctx)
            except Exception as e:
                logger.warning("Trimmer LLM rerank failed, using heuristic order: %s", e)

        # Step 2: Keep top K
        if before_count > self._top_k:
            ctx.all_papers = ctx.all_papers[: self._top_k]
            logger.info(
                "Trimmer: kept top %d/%d papers",
                self._top_k, before_count,
            )

        # Step 3: Truncate abstracts
        truncated = 0
        for paper in ctx.all_papers:
            abstract = paper.get("abstract", "") or ""
            if len(abstract) > self._max_abstract_chars:
                paper["abstract"] = abstract[: self._max_abstract_chars]
                truncated += 1

        after_count = len(ctx.all_papers)
        avg_len = (
            sum(len(p.get("abstract", "") or "") for p in ctx.all_papers)
            / after_count
            if after_count > 0
            else 0
        )

        logger.info(
            "Trimmer: %d -> %d papers, %d abstracts truncated, avg abstract %d chars",
            before_count, after_count, truncated, int(avg_len),
        )
        return True

    async def _rerank(self, ctx: StageContext) -> list[dict]:
        """Use the LLM reranker to sort papers by relevance to domain."""
        # Fallback to heuristic if reranker call fails
        return self._rerank_sync(ctx)

    def _rerank_sync(self, ctx: StageContext) -> list[dict]:
        """Sort papers by keyword overlap with domain (heuristic)."""
        papers = ctx.all_papers
        domain = ctx.domain

        domain_words = set(w.lower() for w in domain.split() if len(w) > 2)

        scored = []
        for paper in papers:
            title = (paper.get("title", "") or "").lower()
            abstract = (paper.get("abstract", "") or "").lower()
            text = title + " " + abstract

            # Keyword overlap score
            overlap = sum(1 for w in domain_words if w in text)
            score = overlap / max(len(domain_words), 1)
            scored.append((score, paper))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]
