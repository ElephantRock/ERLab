"""Phase 4 / WP-4E — scope-alignment detection.

Deterministic scope-drift checker used by the paper-evaluation gate. Compares
the persisted research intent (question/domain) against the generated paper's
title and abstract. Reuses the existing evaluation architecture — no new
evaluator service, no aggregate score, no LLM call (so it works in the
controlled 4H integration without an external provider).

Decision rules (per Phase 4 plan):
  * Missing persisted research intent → ``unavailable`` (not an inferred result).
  * Materially off-topic → ``off_scope``.
  * Topically aligned → ``on_scope``.
  * Borderline / partial overlap → ``partially_on_scope``.
  * Do NOT use title similarity alone — combine title + abstract signal.

This is a heuristic overreach indicator, not a semantic judge. It detects the
Phase 3 Q-Sym drift pattern (neuro-symbolic verifiability → quantization) where
the paper's core vocabulary shares no overlap with the research intent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ScopeAlignmentResult:
    """Outcome of scope-alignment classification."""

    classification: str  # on_scope | partially_on_scope | off_scope | unavailable
    reason: str
    relevant_sections: str = ""  # which paper sections drove the classification


# Tokenization: lowercase, split on non-alphanumeric, drop stopwords + short tokens.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with",
    "by", "as", "is", "are", "be", "we", "our", "this", "that", "from",
    "via", "using", "into", "at", "it", "its", "their", "such", "which",
    "these", "those", "based", "approach", "method", "paper", "study",
    "propose", "proposed", "show", "shows", "shown", "results", "result",
}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {
        t for t in re.split(r"[^a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in _STOPWORDS
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def classify_scope_alignment(
    research_intent: str,
    paper_title: str,
    paper_abstract: str,
) -> ScopeAlignmentResult:
    """Classify whether the paper stays on the frozen research intent.

    Uses vocabulary overlap between the research intent and the paper's title +
    abstract. Title similarity alone is NOT sufficient — both signals combine.
    """
    intent = (research_intent or "").strip()
    if not intent:
        return ScopeAlignmentResult(
            classification="unavailable",
            reason="No persisted research intent; scope cannot be inferred.",
        )

    intent_tokens = _tokens(intent)
    title_tokens = _tokens(paper_title or "")
    abstract_tokens = _tokens(paper_abstract or "")
    paper_tokens = title_tokens | abstract_tokens

    if not paper_tokens:
        return ScopeAlignmentResult(
            classification="unavailable",
            reason="Paper title and abstract are empty; scope cannot be assessed.",
        )

    # Title-only signal (must NOT be used alone, but contributes).
    title_overlap = _jaccard(intent_tokens, title_tokens)
    # Combined title+abstract signal (the authoritative measure).
    combined_overlap = _jaccard(intent_tokens, paper_tokens)
    # Count of distinct intent terms that appear anywhere in the paper.
    intent_hits = len(intent_tokens & paper_tokens)

    # Decision thresholds. The Phase 3 Q-Sym case (neuro-symbolic verifiability
    # vs quantization/compression) has near-zero overlap.
    if combined_overlap == 0.0 and intent_hits == 0:
        return ScopeAlignmentResult(
            classification="off_scope",
            reason=(
                "Paper vocabulary shares no overlap with the research intent "
                f"(title overlap {title_overlap:.2f}, combined {combined_overlap:.2f}, "
                f"{intent_hits} intent terms hit)."
            ),
            relevant_sections="title, abstract",
        )
    if combined_overlap >= 0.15 or intent_hits >= max(2, len(intent_tokens) // 3):
        return ScopeAlignmentResult(
            classification="on_scope",
            reason=(
                f"Paper aligns with research intent (combined overlap "
                f"{combined_overlap:.2f}, {intent_hits} intent terms hit)."
            ),
            relevant_sections="title, abstract",
        )
    return ScopeAlignmentResult(
        classification="partially_on_scope",
        reason=(
            "Paper partially overlaps the research intent (combined overlap "
            f"{combined_overlap:.2f}, {intent_hits} intent terms hit)."
        ),
        relevant_sections="title, abstract",
    )
