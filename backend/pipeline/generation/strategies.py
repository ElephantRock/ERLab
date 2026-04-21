"""Metacognitive strategy selection for the CriticAgent.

Adopted from Reflexion (strategy enum), Self-Refine (convergence detection),
and Reflexion (loop detection). Provides runtime strategy routing so the Critic
applies the right level of analysis based on pipeline state.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from backend.pipeline.generation.models import Critique, ResearchIdea

# Borda tournament state — only active when use_borda=True
_borda_state: dict | None = None


class CriticStrategy(str, Enum):
    SHALLOW_REVIEW = "shallow_review"  # Round 1: breadth, cover many ideas quickly
    DEEP_DIAGNOSIS = "deep_diagnosis"  # Round 2+: depth, focus on top ideas
    META_REFLECTION = "meta_reflection"  # Final: meta-level quality gate


class ConvergenceResult(BaseModel):
    converged: bool
    reason: str
    score_delta: float = 0.0


def select_strategy(
    round_num: int,
    total_rounds: int,
    prior_converged: bool,
) -> CriticStrategy:
    """Select critic strategy based on pipeline state."""
    if prior_converged:
        return CriticStrategy.META_REFLECTION
    if round_num == 1:
        return CriticStrategy.SHALLOW_REVIEW
    if round_num >= total_rounds:
        return CriticStrategy.META_REFLECTION
    return CriticStrategy.DEEP_DIAGNOSIS


def check_convergence(
    current_ideas: list[ResearchIdea],
    previous_ideas: list[ResearchIdea],
    critiques: list[Critique],
    threshold: float = 0.05,
) -> ConvergenceResult:
    """Detect convergence: score delta < threshold, or all suggestions are trivial."""
    if not previous_ideas or not current_ideas:
        return ConvergenceResult(converged=False, reason="insufficient_data")

    prev_scores = sorted((i.score for i in previous_ideas), reverse=True)
    curr_scores = sorted((i.score for i in current_ideas), reverse=True)

    min_len = min(len(prev_scores), len(curr_scores))
    if min_len == 0:
        return ConvergenceResult(converged=False, reason="empty_ideas")

    delta = sum(abs(curr_scores[i] - prev_scores[i]) for i in range(min_len)) / min_len

    # Check if all critiques have no substantive suggestions (independent signal)
    no_suggestions = all(
        len(c.suggestions) == 0 or all(len(s.strip()) < 5 for s in c.suggestions) for c in critiques
    )
    if no_suggestions:
        return ConvergenceResult(
            converged=True,
            reason="no_substantive_suggestions",
            score_delta=delta,
        )

    if delta < threshold:
        return ConvergenceResult(
            converged=True,
            reason=f"score_delta_below_threshold: {delta:.4f} < {threshold}",
            score_delta=delta,
        )

    return ConvergenceResult(
        converged=False, reason=f"active_refinement: delta={delta:.4f}", score_delta=delta
    )


_HEDGED_PATTERNS = [
    "consider",
    "might",
    "could",
    "possibly",
    "perhaps",
    "may want to",
    "it might be",
    "you could",
    "optionally",
    "if desired",
    "it would be",
]


def check_plateau(
    critiques: list[Critique],
    qualification_threshold: float = 0.5,
) -> ConvergenceResult:
    """Detect plateau via qualified-item ratio (autonovel pattern).

    When >threshold of suggestions use hedged language, the critic
    has run out of real problems and is inventing work.
    """
    if not critiques:
        return ConvergenceResult(converged=False, reason="no_critiques")

    total_suggestions = 0
    qualified_count = 0
    for c in critiques:
        for s in c.suggestions:
            total_suggestions += 1
            s_lower = s.lower()
            if any(p in s_lower for p in _HEDGED_PATTERNS):
                qualified_count += 1

    if total_suggestions == 0:
        return ConvergenceResult(converged=True, reason="no_suggestions")

    ratio = qualified_count / total_suggestions
    if ratio >= qualification_threshold:
        return ConvergenceResult(
            converged=True,
            reason=f"plateau: {qualified_count}/{total_suggestions} qualified ({ratio:.0%})",
        )
    return ConvergenceResult(
        converged=False,
        reason=f"active: {qualified_count}/{total_suggestions} qualified ({ratio:.0%})",
    )


def detect_loop(
    critiques: list[Critique],
    history: list[list[Critique]],
    similarity_threshold: float = 0.7,
) -> bool:
    """Detect if critiques are substantively identical to a prior round."""
    if not critiques or not history:
        return False

    current_weaknesses = set()
    for c in critiques:
        for w in c.weaknesses:
            current_weaknesses.add(w.lower().strip())

    if not current_weaknesses:
        return False

    for past_critiques in history:
        past_weaknesses = set()
        for c in past_critiques:
            for w in c.weaknesses:
                past_weaknesses.add(w.lower().strip())

        if not past_weaknesses:
            continue

        intersection = current_weaknesses & past_weaknesses
        union = current_weaknesses | past_weaknesses

        if union and len(intersection) / len(union) >= similarity_threshold:
            return True

    return False


def keep_best_n(
    ideas: list[ResearchIdea],
    n: int,
    min_score: float = 0.3,
) -> list[ResearchIdea]:
    """Quality gate: keep top-N ideas above minimum score threshold."""
    filtered = [i for i in ideas if i.score >= min_score]
    return sorted(filtered, key=lambda i: i.score, reverse=True)[:n]


def check_convergence_borda(
    current_ideas: list[ResearchIdea],
    previous_ideas: list[ResearchIdea],
    borda_winner: str | None = None,
    borda_scores: dict[str, int] | None = None,
) -> ConvergenceResult:
    """Convergence via Borda tournament (autoreason pattern).

    Falls back to standard check_convergence if no Borda data.
    When Borda data is provided, returns converged=True only when
    the incumbent (A) has won enough consecutive rounds.
    """
    if borda_winner is not None and borda_scores is not None:
        if borda_winner == "A":
            return ConvergenceResult(
                converged=True,
                reason=f"borda_incumbent_wins: scores={borda_scores}",
                score_delta=0.0,
            )
        return ConvergenceResult(
            converged=False,
            reason=f"borda_challenger_wins: {borda_winner} scores={borda_scores}",
            score_delta=0.0,
        )

    # Fallback to standard convergence
    return check_convergence(current_ideas, previous_ideas, [])


class StrategyOutcome(BaseModel):
    """Record of a strategy application and its result quality."""

    strategy: CriticStrategy
    round_num: int
    idea_count: int
    avg_score: float
    convergence: bool = False
    context_signals: dict[str, Any] = Field(default_factory=dict)


class StrategyTracker:
    """Data-driven strategy selection based on historical outcomes.

    Tracks which strategies produce the best results under which
    conditions, then recommends the empirically best strategy
    for a given context.
    """

    def __init__(self):
        self._history: list[StrategyOutcome] = []

    def record(self, outcome: StrategyOutcome) -> None:
        self._history.append(outcome)

    def recommend(self, round_num: int, total_rounds: int) -> CriticStrategy:
        """Recommend strategy based on historical performance.

        If enough data exists, picks the strategy with highest avg_score
        for similar round contexts. Falls back to rule-based selection.
        """
        if len(self._history) < 5:
            return select_strategy(round_num, total_rounds, False)

        round_bucket = (
            "early"
            if round_num <= total_rounds // 3
            else ("mid" if round_num <= 2 * total_rounds // 3 else "late")
        )

        strategy_scores: dict[CriticStrategy, list[float]] = {}
        for h in self._history:
            h_bucket = (
                "early"
                if h.round_num <= total_rounds // 3
                else ("mid" if h.round_num <= 2 * total_rounds // 3 else "late")
            )
            if h_bucket == round_bucket:
                strategy_scores.setdefault(h.strategy, []).append(h.avg_score)

        if not strategy_scores:
            return select_strategy(round_num, total_rounds, False)

        best = max(strategy_scores, key=lambda s: sum(strategy_scores[s]) / len(strategy_scores[s]))
        return best

    @property
    def history(self) -> list[StrategyOutcome]:
        return list(self._history)

    @property
    def record_count(self) -> int:
        return len(self._history)
