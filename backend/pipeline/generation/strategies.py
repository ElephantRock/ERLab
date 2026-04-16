"""Metacognitive strategy selection for the CriticAgent.

Adopted from Reflexion (strategy enum), Self-Refine (convergence detection),
and Reflexion (loop detection). Provides runtime strategy routing so the Critic
applies the right level of analysis based on pipeline state.
"""

from enum import Enum

from pydantic import BaseModel

from backend.pipeline.generation.models import Critique, ResearchIdea


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
        len(c.suggestions) == 0
        or all(len(s.strip()) < 5 for s in c.suggestions)
        for c in critiques
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

    return ConvergenceResult(converged=False, reason=f"active_refinement: delta={delta:.4f}", score_delta=delta)


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
