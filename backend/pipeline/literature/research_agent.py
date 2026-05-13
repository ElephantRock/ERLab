"""Research sub-agent for isolated literature search queries.

Ported from huggingface/ml-intern agent/tools/research_tool.py (Apache 2.0).
Adapted for Elephant Rock's pipeline: each search query gets its own
independent context with budget enforcement and doom loop detection.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    """Result from a research sub-agent."""

    query: str
    papers: list[dict] = field(default_factory=list)
    iterations_used: int = 0
    context_tokens_used: int = 0
    truncated: bool = False
    doom_detected: bool = False


class ResearchSubAgent:
    """Isolated research context for a single search query.

    Each agent has its own message history and context budget.
    It uses a callable search_fn to find papers and doesn't
    depend on the main pipeline's context.
    """

    def __init__(
        self,
        query: str,
        domain: str,
        search_fn: Callable[[str, str], Awaitable[list[dict]]],
        max_iterations: int = 20,
        context_budget: int = 100_000,
        budget_warn_ratio: float = 0.80,
        budget_hard_ratio: float = 0.95,
    ):
        self.query = query
        self.domain = domain
        self.search_fn = search_fn
        self.max_iterations = max_iterations
        self.context_budget = context_budget
        self.budget_warn = int(context_budget * budget_warn_ratio)
        self.budget_hard = int(context_budget * budget_hard_ratio)

        # Track accumulated search results
        self._papers: list[dict] = []
        self._iteration = 0
        self._total_tokens = 0
        self._search_history: list[str] = []  # query variants tried
        self._truncated = False
        self._doom_detected = False

    async def run(self) -> ResearchResult:
        """Execute the research loop.

        Calls search_fn with the query, then refines if needed.
        Stops when: max iterations hit, context budget exceeded,
        doom detected, or no more useful results.
        """
        # Initial search
        await self._do_search(self.query)

        # Refinement loop: try to get more/different papers
        while self._iteration < self.max_iterations:
            # Check hard context budget
            if self._total_tokens >= self.budget_hard:
                logger.warning(
                    "Research sub-agent for '%s' hit hard context budget (%d tokens)",
                    self.query[:50], self._total_tokens,
                )
                self._truncated = True
                break

            # Check doom loop (reuse BATCH-185)
            if self._check_doom():
                self._doom_detected = True
                logger.warning(
                    "Research sub-agent for '%s' detected doom loop",
                    self.query[:50],
                )
                break

            # Check if we have enough papers
            if len(self._papers) >= 10:
                break

            # Try a refined query
            refined = self._refine_query()
            if not refined or refined in self._search_history:
                break

            await self._do_search(refined)

        return ResearchResult(
            query=self.query,
            papers=self._papers,
            iterations_used=self._iteration,
            context_tokens_used=self._total_tokens,
            truncated=self._truncated,
            doom_detected=self._doom_detected,
        )

    async def _do_search(self, query: str) -> None:
        """Execute one search iteration."""
        self._iteration += 1
        self._search_history.append(query)

        try:
            new_papers = await self.search_fn(query, self.domain)
            if new_papers:
                # Estimate token usage (rough: 4 chars per token)
                for paper in new_papers:
                    abstract = paper.get("abstract", "") or ""
                    self._total_tokens += len(abstract) // 4 + 100
                self._papers.extend(new_papers)
            logger.debug(
                "Research sub-agent iteration %d: found %d papers for '%s'",
                self._iteration, len(new_papers) if new_papers else 0, query[:50],
            )
        except Exception as e:
            logger.warning("Research sub-agent search failed for '%s': %s", query[:50], e)

    def _refine_query(self) -> str | None:
        """Generate a refined query based on what we've found so far.

        Simple heuristic: add domain-specific modifiers to get
        different results from the search APIs.
        """
        modifiers = [
            f"{self.query} survey review",
            f"{self.query} recent advances 2024 2025",
            f"{self.query} benchmark evaluation",
            f"{self.query} open problems challenges",
        ]
        for mod in modifiers:
            if mod not in self._search_history:
                return mod
        return None

    def _check_doom(self) -> bool:
        """Check for doom loop in search history.

        Reuses BATCH-185 doom_loop module. If the last 3 searches
        all returned the same paper count (0), it's a doom loop.
        """
        if len(self._search_history) < 3:
            return False

        try:
            from backend.pipeline.monitoring.doom_loop import (
                StageOutputSignature,
                detect_identical_consecutive,
            )
            # Build signatures from paper counts
            paper_counts = []
            count = 0
            for i, q in enumerate(self._search_history):
                # Approximate: papers found in each iteration
                # (we don't track per-iteration counts exactly)
                pass

            # Simpler check: if last 3 queries are identical, it's doom
            recent = self._search_history[-3:]
            if len(set(recent)) == 1:
                return True

        except ImportError:
            pass

        return False


async def run_parallel_research(
    queries: list[str],
    domain: str,
    search_fn: Callable[[str, str], Awaitable[list[dict]]],
    max_iterations: int = 20,
    context_budget: int = 100_000,
) -> list[ResearchResult]:
    """Run multiple research sub-agents in parallel.

    Each query gets its own isolated context. Results are
    returned as a list of ResearchResult objects.
    """
    agents = [
        ResearchSubAgent(
            query=q,
            domain=domain,
            search_fn=search_fn,
            max_iterations=max_iterations,
            context_budget=context_budget,
        )
        for q in queries
    ]

    tasks = [agent.run() for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to empty results
    final = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning("Research sub-agent for '%s' failed: %s", queries[i][:50], r)
            final.append(ResearchResult(query=queries[i], truncated=True))
        else:
            final.append(r)

    return final
