"""Intent-based quality parameter mapping.

Maps user-facing intent levels to concrete pipeline parameters.
Base constants are immutable — effective values are computed per request
without mutating module-level state.

Mapping table:
    proposal_depth:  concise → 0.5x, standard → 1.0x, detailed → 1.5x
    novelty_depth:    light → top_k 10, standard → top_k 20, thorough → top_k 50
    idea_diversity:   focused → temp 0.3, balanced → temp 0.7, exploratory → temp 1.1
"""

from __future__ import annotations

from typing import Any

# ── Immutable base values (never mutated) ─────────────────────────

BASE_MIN_WORDS: dict[str, int] = {
    "abstract": 150,
    "introduction": 400,
    "related_work": 300,
    "proposed_method": 600,
    "expected_contributions": 150,
    "evaluation_plan": 300,
    "timeline": 100,
    "risk_mitigation": 150,
}

BASE_NOVELTY_TOP_K: int = 20

BASE_IDEATOR_TEMPERATURE: float = 0.7

# ── Intent → multiplier/value maps ────────────────────────────────

PROPOSAL_DEPTH_MULTIPLIERS: dict[str, float] = {
    "concise": 0.5,
    "standard": 1.0,
    "detailed": 1.5,
}

NOVELTY_DEPTH_TOP_K: dict[str, int] = {
    "light": 10,
    "standard": 20,
    "thorough": 50,
}

IDEA_DIVERSITY_TEMPERATURE: dict[str, float] = {
    "focused": 0.3,
    "balanced": 0.7,
    "exploratory": 1.1,
}

# ── Resolution functions ─────────────────────────────────────────


def resolve_min_words(
    proposal_depth: str | None = None,
) -> dict[str, int]:
    """Compute effective MIN_WORDS for a given proposal depth.

    Args:
        proposal_depth: "concise" | "standard" | "detailed".
            None or "standard" returns base values unchanged.

    Returns:
        Copy of base MIN_WORDS with multiplier applied.
    """
    multiplier = PROPOSAL_DEPTH_MULTIPLIERS.get(proposal_depth or "standard", 1.0)
    if multiplier == 1.0:
        return dict(BASE_MIN_WORDS)
    return {
        section: max(50, int(words * multiplier))
        for section, words in BASE_MIN_WORDS.items()
    }


def resolve_novelty_top_k(novelty_depth: str | None = None) -> int:
    """Compute effective novelty top_k for a given depth level.

    Args:
        novelty_depth: "light" | "standard" | "thorough".
            None returns the base default (20).

    Returns:
        Integer top_k value.
    """
    return NOVELTY_DEPTH_TOP_K.get(novelty_depth or "standard", BASE_NOVELTY_TOP_K)


def resolve_ideator_temperature(idea_diversity: str | None = None) -> float:
    """Compute effective ideator temperature for a given diversity level.

    Args:
        idea_diversity: "focused" | "balanced" | "exploratory".
            None returns the base default (0.7).

    Returns:
        Float temperature value.
    """
    return IDEA_DIVERSITY_TEMPERATURE.get(
        idea_diversity or "balanced", BASE_IDEATOR_TEMPERATURE
    )


def resolve_all(
    proposal_depth: str | None = None,
    novelty_depth: str | None = None,
    idea_diversity: str | None = None,
) -> dict[str, Any]:
    """Resolve all quality parameters at once.

    Returns a dict suitable for storing in run config or returning
    in run detail responses.
    """
    return {
        "proposal_depth": proposal_depth or "standard",
        "effective_min_words": resolve_min_words(proposal_depth),
        "novelty_depth": novelty_depth or "standard",
        "effective_novelty_top_k": resolve_novelty_top_k(novelty_depth),
        "idea_diversity": idea_diversity or "balanced",
        "effective_ideator_temperature": resolve_ideator_temperature(idea_diversity),
    }
