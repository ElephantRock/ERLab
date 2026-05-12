"""Token Budget Guard — trims document chunks to fit within token budgets.

BATCH-RAG-05: Sits between the reranker/scorer and the LLM consumer stages.
Counts tokens precisely using tiktoken and drops lowest-scoring chunks
when the total exceeds the configured budget.

Prevents:
  - OOM errors on constrained hardware (RTX 3080 Ti 12GB)
  - Context window overflow in local LLM models
  - Wasted tokens on low-relevance documents
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default token budgets per stage (approximate, tuned for qwen3-4b 4K context)
DEFAULT_STAGE_BUDGETS: dict[str, int] = {
    "gap_analysis": 3500,
    "gap_reflection": 3000,
    "idea_generation": 4000,
    "idea_reflection": 3000,
    "novelty_checking": 3000,
    "feasibility_scoring": 3000,
    "proposal_synthesis": 6000,
    "adversarial_review": 4000,
    "evaluation": 3000,
    "paper_synthesis": 6000,
    "proposal_deepening": 5000,
}


@dataclass
class ScoredChunk:
    """A text chunk with a relevance score for budget-aware trimming."""

    text: str
    score: float = 0.0
    source_id: str = ""
    metadata: dict = field(default_factory=dict)
    token_count: int = 0


@dataclass
class BudgetReport:
    """Report from token budget trimming operation."""

    original_chunks: int = 0
    original_tokens: int = 0
    trimmed_chunks: int = 0
    trimmed_tokens: int = 0
    budget: int = 0
    dropped: int = 0
    stage: str = ""

    @property
    def savings_pct(self) -> float:
        """Percentage of tokens saved by trimming."""
        if self.original_tokens == 0:
            return 0.0
        return (self.original_tokens - self.trimmed_tokens) / self.original_tokens


class TokenCounter:
    """Precise token counting using tiktoken.

    Falls back to character-based estimation if tiktoken unavailable.
    """

    def __init__(self, model: str = "cl100k_base"):
        self._encoder = None
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding(model)
        except Exception:
            logger.debug("tiktoken unavailable, using char-based estimation")

    def count(self, text: str) -> int:
        """Count tokens in text."""
        if not text:
            return 0
        if self._encoder:
            return len(self._encoder.encode(text))
        # Fallback: ~4 chars per token (rough estimate)
        return max(1, len(text) // 4)

    def count_messages(self, messages: list[dict]) -> int:
        """Count total tokens in a list of chat messages."""
        total = 0
        for msg in messages:
            total += 4  # message overhead (role, separators)
            total += self.count(msg.get("content", ""))
            total += self.count(msg.get("role", ""))
        return total


class TokenBudgetGuard:
    """Trims scored chunks to fit within a token budget.

    Algorithm:
    1. Sort chunks by score (descending)
    2. Accumulate tokens until budget reached
    3. Drop lowest-scoring chunks that exceed budget
    4. Return trimmed list preserving score order

    Parameters
    ----------
    budget:
        Maximum total tokens allowed.
    counter:
        TokenCounter instance for precise counting.
    """

    def __init__(
        self,
        budget: int = 4000,
        counter: TokenCounter | None = None,
    ):
        self._budget = max(256, budget)  # Minimum 256 tokens
        self._counter = counter or TokenCounter()

    def trim(self, chunks: list[ScoredChunk]) -> tuple[list[ScoredChunk], BudgetReport]:
        """Trim chunks to fit within token budget.

        Returns (trimmed_chunks, report).
        """
        if not chunks:
            return [], BudgetReport(budget=self._budget)

        # Count tokens for each chunk
        for chunk in chunks:
            chunk.token_count = self._counter.count(chunk.text)

        original_count = len(chunks)
        original_tokens = sum(c.token_count for c in chunks)

        # Already within budget?
        if original_tokens <= self._budget:
            return chunks, BudgetReport(
                original_chunks=original_count,
                original_tokens=original_tokens,
                trimmed_chunks=original_count,
                trimmed_tokens=original_tokens,
                budget=self._budget,
                dropped=0,
            )

        # Sort by score descending (highest relevance first)
        sorted_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)

        # Accumulate until budget reached
        kept: list[ScoredChunk] = []
        total_tokens = 0

        for chunk in sorted_chunks:
            if total_tokens + chunk.token_count <= self._budget:
                kept.append(chunk)
                total_tokens += chunk.token_count
            # else: drop this chunk (too many tokens)

        dropped = original_count - len(kept)

        report = BudgetReport(
            original_chunks=original_count,
            original_tokens=original_tokens,
            trimmed_chunks=len(kept),
            trimmed_tokens=total_tokens,
            budget=self._budget,
            dropped=dropped,
        )

        logger.info(
            "Token budget trim: %d→%d chunks, %d→%d tokens (budget %d, dropped %d)",
            original_count,
            len(kept),
            original_tokens,
            total_tokens,
            self._budget,
            dropped,
        )

        return kept, report

    def trim_texts(
        self,
        texts: list[str],
        scores: list[float] | None = None,
    ) -> tuple[list[str], BudgetReport]:
        """Convenience: trim plain texts with optional scores.

        Returns (trimmed_texts, report).
        """
        scores = scores or [1.0] * len(texts)
        chunks = [
            ScoredChunk(text=t, score=s)
            for t, s in zip(texts, scores)
        ]
        kept, report = self.trim(chunks)
        return [c.text for c in kept], report

    def trim_for_stage(
        self,
        texts: list[str],
        stage: str,
        scores: list[float] | None = None,
        override_budget: int | None = None,
    ) -> tuple[list[str], BudgetReport]:
        """Trim texts using stage-specific budget from config.

        Parameters
        ----------
        texts:
            Input text chunks.
        stage:
            Pipeline stage name (e.g., "gap_analysis").
        scores:
            Optional relevance scores per chunk.
        override_budget:
            Override the stage's default budget.
        """
        budget = override_budget or DEFAULT_STAGE_BUDGETS.get(stage, 4000)
        guard = TokenBudgetGuard(budget=budget, counter=self._counter)
        result, report = guard.trim_texts(texts, scores)
        report.stage = stage
        return result, report
