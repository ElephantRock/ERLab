"""Query hygiene for adaptive evidence search.

Mechanical, deterministic query normalization and filtering. No LLM
calls, no embedding similarity — just text-level dedup, length checks,
and refusal-pattern rejection. These functions keep the planner's
output clean without introducing a second retrieval mechanism.

Used by LLMQueryGenerator.generate_adaptive_queries (AES-1) and by
the adaptive loop in LiteratureSearchStage (AES-3).
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# ── Length conventions (match existing query expansion in stages.py) ────────

MIN_QUERY_LEN = 5
MAX_QUERY_LEN = 200

# ── Terminal-prose patterns (conservative prefix match on normalized text) ──

_TERMINAL_PATTERNS: tuple[str, ...] = (
    "no further quer",
    "no additional quer",
    "no further search",
    "no additional search",
    "nothing further",
    "sufficient coverage",
    "coverage is sufficient",
    "no more queries",
    "no more searches",
)


def normalize_query(text: str) -> str:
    """NFKC → strip → casefold → collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.strip().casefold()
    normalized = " ".join(normalized.split())
    return normalized


def query_similarity(a: str, b: str) -> float:
    """Return SequenceMatcher ratio on normalized query strings."""
    return SequenceMatcher(None, normalize_query(a), normalize_query(b)).ratio()


def is_terminal_planner_text(text: str) -> bool:
    """Return True if the text matches a common planner-refusal pattern."""
    normalized = normalize_query(text)
    return any(normalized.startswith(pat) for pat in _TERMINAL_PATTERNS)


def filter_adaptive_queries(
    candidates: list[str],
    attempted_queries: list[str],
    *,
    max_queries: int = 3,
    similarity_threshold: float = 0.85,
) -> list[str]:
    """Filter planner output through deterministic query hygiene.

    Filtering order (deterministic):
    1. Require string type.
    2. Strip whitespace.
    3. Reject blank.
    4. Reject too-short / too-long strings.
    5. Reject terminal prose (refusal patterns).
    6. Reject exact normalized duplicates against attempted queries.
    7. Reject high-similarity near-duplicates against attempted queries.
    8. Reject duplicates / near-duplicates within this planner output.
    9. Stop at ``max_queries``.
    """
    normalized_attempted = [
        normalize_query(q) for q in attempted_queries
    ]

    accepted: list[str] = []
    accepted_normalized: list[str] = []

    for candidate in candidates:
        if len(accepted) >= max_queries:
            break

        # 1. Require string.
        if not isinstance(candidate, str):
            continue

        # 2. Strip.
        stripped = candidate.strip()

        # 3. Reject blank.
        if not stripped:
            continue

        # 4. Length bounds.
        if len(stripped) < MIN_QUERY_LEN or len(stripped) > MAX_QUERY_LEN:
            continue

        # 5. Terminal prose.
        if is_terminal_planner_text(stripped):
            continue

        norm = normalize_query(stripped)

        # 6. Exact duplicate against attempted.
        if norm in normalized_attempted:
            continue

        # 7. Near-duplicate against attempted.
        if any(
            SequenceMatcher(None, norm, a).ratio() > similarity_threshold
            for a in normalized_attempted
        ):
            continue

        # 8. Duplicate / near-duplicate within this output.
        if any(
            SequenceMatcher(None, norm, a).ratio() > similarity_threshold
            for a in accepted_normalized
        ):
            continue

        accepted.append(stripped)
        accepted_normalized.append(norm)

    return accepted
