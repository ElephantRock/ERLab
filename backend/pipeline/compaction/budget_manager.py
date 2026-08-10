"""Per-stage token budgets with dynamic context-size adjustment."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class StageTokenBudget:
    """Token budget for a single pipeline stage's input context."""

    base: int
    min_budget: int
    max_budget: int
    consumed: int = 0

    def current(self) -> int:
        return max(self.min_budget, self.base - self.consumed)


@dataclass
class CompactionRecommendation:
    """Advice from the budget manager on how to compact context."""

    max_papers: int | None = None
    max_abstract_chars: int | None = None
    summarize_gaps: bool = False
    summarize_reports: bool = False
    summarize_critiques: bool = False


# Rough heuristic: 1 token ≈ 4 chars for English text
CHARS_PER_TOKEN = 4

# Hardcoded fallback values (used only when settings JSON parsing fails)
_FALLBACK_BUDGETS: dict[str, StageTokenBudget] = {
    "gap_analysis": StageTokenBudget(base=6000, min_budget=3000, max_budget=10000),
    "idea_generation": StageTokenBudget(base=8000, min_budget=4000, max_budget=15000),
    "novelty_checking": StageTokenBudget(base=4000, min_budget=2000, max_budget=8000),
    "feasibility_scoring": StageTokenBudget(base=2000, min_budget=1000, max_budget=4000),
    "proposal_synthesis": StageTokenBudget(base=10000, min_budget=5000, max_budget=20000),
}

_FALLBACK_PAPER_LIMITS: dict[str, int] = {
    "gap_analysis": 30,
    "idea_generation": 20,
    "novelty_checking": 10,
    "feasibility_scoring": 0,
    "proposal_synthesis": 15,
}


def _get_budgets_from_settings() -> dict[str, StageTokenBudget]:
    """Read stage token budgets from settings, with JSON parse fallback."""
    try:
        from backend.config import get_settings
        settings = get_settings()
        raw = json.loads(settings.compaction_stage_budgets)
        return {
            stage: StageTokenBudget(
                base=v["base"], min_budget=v["min_budget"], max_budget=v["max_budget"],
            )
            for stage, v in raw.items()
        }
    except Exception:
        return dict(_FALLBACK_BUDGETS)


def _get_paper_limits_from_settings() -> dict[str, int]:
    """Read per-stage paper limits from settings, with JSON parse fallback."""
    try:
        from backend.config import get_settings
        settings = get_settings()
        raw = json.loads(settings.compaction_paper_limits)
        return {stage: int(v) for stage, v in raw.items()}
    except Exception:
        return dict(_FALLBACK_PAPER_LIMITS)


def _get_abstract_chars_tight() -> int:
    """Read tight-mode abstract char limit from settings."""
    try:
        from backend.config import get_settings
        return get_settings().compaction_abstract_chars_tight
    except Exception:
        return 80


def _get_abstract_chars_loose() -> int:
    """Read loose-mode abstract char limit from settings."""
    try:
        from backend.config import get_settings
        return get_settings().compaction_abstract_chars_loose
    except Exception:
        return 150


# Module-level defaults read from settings (lazy)
DEFAULT_BUDGETS: dict[str, StageTokenBudget] = _get_budgets_from_settings()
DEFAULT_PAPER_LIMITS: dict[str, int] = _get_paper_limits_from_settings()


class ContextBudgetManager:
    """Manages per-stage context budgets and recommends compaction levels."""

    def __init__(
        self,
        budgets: dict[str, StageTokenBudget] | None = None,
        paper_limits: dict[str, int] | None = None,
        global_token_limit: int = 500000,
    ) -> None:
        self._budgets = budgets or DEFAULT_BUDGETS
        self._paper_limits = paper_limits or DEFAULT_PAPER_LIMITS
        self._global_token_limit = global_token_limit
        self._total_consumed: int = 0

    def record_consumption(self, stage_name: str, tokens: int) -> None:
        """Record actual tokens consumed by a stage."""
        self._total_consumed += tokens
        if stage_name in self._budgets:
            self._budgets[stage_name].consumed += tokens

    def remaining_budget(self) -> int:
        return max(0, self._global_token_limit - self._total_consumed)

    def estimate_context_size(self, ctx: object, stage_name: str) -> int:
        """Rough estimate of context token usage for a stage.

        Uses the heuristic 1 token ≈ 4 chars. Counts papers, gaps,
        ideas, and reports based on what each stage accesses.
        """
        chars = 0

        if stage_name == "gap_analysis":
            chars += self._count_papers_chars(ctx, 30)
        elif stage_name == "idea_generation":
            chars += self._count_papers_chars(ctx, 20)
            chars += self._count_gaps_chars(ctx)
            chars += self._count_critiques_chars(ctx)
        elif stage_name == "novelty_checking" or stage_name == "feasibility_scoring":
            chars += self._count_ideas_chars(ctx)
        elif stage_name == "proposal_synthesis":
            chars += self._count_papers_chars(ctx, 15)
            chars += self._count_gaps_chars(ctx)
            chars += self._count_ideas_chars(ctx)
            chars += self._count_reports_chars(ctx)

        return chars // CHARS_PER_TOKEN

    def recommend_compaction(
        self,
        ctx: object,
        stage_name: str,
        remaining_stages: int = 3,
    ) -> CompactionRecommendation:
        """Recommend compaction level based on budget vs. estimated size."""
        budget = self._budgets.get(stage_name)
        if not budget:
            return CompactionRecommendation()

        estimated = self.estimate_context_size(ctx, stage_name)
        is_tight = estimated > budget.current()
        is_global_tight = self.remaining_budget() < self._global_token_limit * 0.2

        rec = CompactionRecommendation()

        # Paper limits
        default_papers = self._paper_limits.get(stage_name, 20)
        if is_tight or is_global_tight:
            rec.max_papers = max(default_papers // 2, 5)
            rec.max_abstract_chars = _get_abstract_chars_tight()
        else:
            rec.max_papers = default_papers
            rec.max_abstract_chars = _get_abstract_chars_loose()

        # Summarization flags
        if is_tight or is_global_tight:
            rec.summarize_gaps = True
            rec.summarize_reports = True
            rec.summarize_critiques = True
        elif estimated > budget.base * 0.7:
            rec.summarize_gaps = stage_name == "proposal_synthesis"
            rec.summarize_reports = stage_name == "proposal_synthesis"

        return rec

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _count_papers_chars(ctx: object, limit: int) -> int:
        papers = getattr(ctx, "all_papers", [])
        count = min(len(papers), limit) if papers else 0
        return count * 250  # title + truncated abstract avg

    @staticmethod
    def _count_gaps_chars(ctx: object) -> int:
        result = getattr(ctx, "result", None)
        if not result:
            return 0
        gaps = getattr(result, "gaps", [])
        return len(gaps) * 200 if gaps else 0

    @staticmethod
    def _count_ideas_chars(ctx: object) -> int:
        result = getattr(ctx, "result", None)
        if not result:
            return 0
        ideas = getattr(result, "ideas", [])
        return len(ideas) * 400 if ideas else 0

    @staticmethod
    def _count_critiques_chars(ctx: object) -> int:
        result = getattr(ctx, "result", None)
        if not result:
            return 0
        history = getattr(result, "critique_history", {})
        total = sum(len(v) * 200 for v in history.values()) if history else 0
        return total

    @staticmethod
    def _count_reports_chars(ctx: object) -> int:
        result = getattr(ctx, "result", None)
        if not result:
            return 0
        novelty = getattr(result, "novelty_reports", {})
        feasibility = getattr(result, "feasibility_reports", {})
        return (len(novelty) + len(feasibility)) * 300
