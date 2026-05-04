"""Mechanical (objective, non-LLM) quality metrics for research ideas.

All metrics are pure-computation — no LLM API calls (HB-02).
All return values are clamped to [0.0, 1.0] (HB-01).

Metrics
-------
1. reference_uniqueness  – fraction of cited papers not previously cited in
                           the same domain.
2. gap_coverage           – fraction of identified research gaps whose
                           keywords appear in the idea's proposed_method text.
3. citation_density       – normalised average citation count of supporting
                           papers (capped at 1 000).
4. method_specificity     – count of concrete claims / 10.
5. prior_art_distance     – 1 − max word-overlap similarity to closest papers.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# ── Clamping helper ──────────────────────────────────────────────────────────


def _clamp(value: float) -> float:
    """Force *value* into [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


# ── Lightweight protocols (duck-typed) ───────────────────────────────────────


class _HasProposedMethod(Protocol):
    proposed_method: str


class _HasSupportingPapers(Protocol):
    supporting_papers: list[str]


class _HasKeywords(Protocol):
    keywords: list[str]


class _HasCitationCount(Protocol):
    citation_count: int | None


class _HasAbstract(Protocol):
    abstract: str | None


# ── Word-overlap similarity (no embeddings) ──────────────────────────────────

_WORD_SPLIT = re.compile(r"[A-Za-z0-9]+")

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "it", "that", "this", "which",
        "be", "are", "was", "were", "been", "have", "has", "had", "do", "does",
        "did", "will", "would", "could", "should", "may", "might", "can",
        "we", "they", "our", "their", "its", "not", "no", "if", "then",
    }
)


def _tokenise(text: str) -> set[str]:
    """Lower-case word tokens, minus stop-words."""
    return {
        w.lower()
        for w in _WORD_SPLIT.findall(text)
        if w.lower() not in _STOP_WORDS
    }


def _word_overlap_similarity(text_a: str, text_b: str) -> float:
    """Jaccard-like overlap: |A ∩ B| / |A ∪ B|, 0 when both empty."""
    a = _tokenise(text_a)
    b = _tokenise(text_b)
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


# ── Concrete-claim patterns ──────────────────────────────────────────────────

_CONCRETE_PATTERNS: list[re.Pattern[str]] = [
    # Numbered items: "1.", "2)", "(3)", etc.
    re.compile(r"(?:^|\n)\s*\d+[\.\)]\s", re.MULTILINE),
    # "we will …"
    re.compile(r"\bwe will\b", re.IGNORECASE),
    # "we propose …"
    re.compile(r"\bwe propose\b", re.IGNORECASE),
    # "using X" / "utilising X"
    re.compile(r"\b(?:using|utilizing|employing|leveraging)\b", re.IGNORECASE),
    # "X-based" / "X-driven"
    re.compile(r"\b\w+-(?:based|driven|guided|aware|centric)\b", re.IGNORECASE),
    # Explicit quantitative claims: "N%", "N times", "≥ N"
    re.compile(r"\d+\s*[%×x]|≥|≥|≤|≤|\bat least\b", re.IGNORECASE),
    # "implement / deploy / evaluate / train / fine-tune"
    re.compile(
        r"\b(?:implement|deploy|evaluate|train|fine[-\s]?tune|benchmark)\b",
        re.IGNORECASE,
    ),
    # "our approach / our method / our system"
    re.compile(r"\bour\s+(?:approach|method|system|model|framework)\b", re.IGNORECASE),
    # "specifically, …"
    re.compile(r"\bspecifically\b", re.IGNORECASE),
    # "compared to / against X baseline"
    re.compile(r"\bcompared\s+to\b|\bbaseline\b", re.IGNORECASE),
]


def _count_concrete_claims(text: str) -> int:
    """Count distinct concrete-claim signals in *text* (capped at 10)."""
    count = sum(1 for pat in _CONCRETE_PATTERNS if pat.search(text))
    return min(count, 10)


# ── Calculator ────────────────────────────────────────────────────────────────


@dataclass
class MechanicalMetricsCalculator:
    """Stateless calculator — safe to reuse across ideas."""

    max_claims: int = 10
    citation_normalisation_target: int = 1_000

    # ── 1. reference_uniqueness ───────────────────────────────────────────
    def reference_uniqueness(
        self,
        idea: Any,
        all_domain_papers: Sequence[Any],
    ) -> float:
        """Fraction of *idea*'s cited papers not previously cited in domain.

        Parameters
        ----------
        idea : object with ``supporting_papers: list[str]``
        all_domain_papers : sequence of objects with ``id: str``
            Papers already known/cited in this domain (excluding current idea).

        Returns
        -------
        float in [0.0, 1.0]
        """
        cited_ids: set[str] = set(getattr(idea, "supporting_papers", []))
        if not cited_ids:
            return 0.0

        domain_ids: set[str] = {
            getattr(p, "id", "") for p in all_domain_papers
        }
        novel = cited_ids - domain_ids
        return _clamp(len(novel) / len(cited_ids))

    # ── 2. gap_coverage ───────────────────────────────────────────────────
    def gap_coverage(
        self,
        idea: Any,
        gaps: Sequence[Any],
    ) -> float:
        """Fraction of *gaps* whose keywords appear in idea's proposed_method.

        Parameters
        ----------
        idea : object with ``proposed_method: str``
        gaps : sequence of objects with ``keywords: list[str]``

        Returns
        -------
        float in [0.0, 1.0]
        """
        gaps = list(gaps)
        if not gaps:
            return 0.0

        method_text = getattr(idea, "proposed_method", "").lower()
        if not method_text:
            return 0.0

        covered = 0
        for gap in gaps:
            keywords: list[str] = getattr(gap, "keywords", [])
            if any(kw.lower() in method_text for kw in keywords if kw):
                covered += 1

        return _clamp(covered / len(gaps))

    # ── 3. citation_density ───────────────────────────────────────────────
    def citation_density(
        self,
        idea: Any,
        supporting_papers: Sequence[Any],
    ) -> float:
        """Normalised average citation count of *supporting_papers*.

        ``min(1.0, avg_citations / citation_normalisation_target)``

        Parameters
        ----------
        idea : unused (kept for consistent signature).
        supporting_papers : sequence of objects with ``citation_count: int | None``

        Returns
        -------
        float in [0.0, 1.0]
        """
        papers = list(supporting_papers)
        if not papers:
            return 0.0

        total = 0
        for p in papers:
            cc = getattr(p, "citation_count", None)
            total += cc if cc is not None else 0

        avg = total / len(papers)
        return _clamp(avg / self.citation_normalisation_target)

    # ── 4. method_specificity ─────────────────────────────────────────────
    def method_specificity(self, idea: Any) -> float:
        """Concrete claims in the proposed_method / max_claims.

        Parameters
        ----------
        idea : object with ``proposed_method: str``

        Returns
        -------
        float in [0.0, 1.0]
        """
        text = getattr(idea, "proposed_method", "")
        if not text:
            return 0.0

        count = _count_concrete_claims(text)
        return _clamp(count / self.max_claims)

    # ── 5. prior_art_distance ─────────────────────────────────────────────
    def prior_art_distance(
        self,
        idea: Any,
        closest_papers: Sequence[Any],
    ) -> float:
        """1 − max word-overlap similarity between idea and closest papers.

        Uses simple word overlap as a proxy — no embeddings needed.

        Parameters
        ----------
        idea : object with ``proposed_method: str``
        closest_papers : sequence of objects with ``abstract: str | None``

        Returns
        -------
        float in [0.0, 1.0]
        """
        papers = list(closest_papers)
        if not papers:
            return 1.0  # no prior art → maximum distance

        idea_text = getattr(idea, "proposed_method", "")
        if not idea_text:
            return 0.0

        max_sim = 0.0
        for p in papers:
            abstract: str | None = getattr(p, "abstract", None)
            if not abstract:
                continue
            sim = _word_overlap_similarity(idea_text, abstract)
            if sim > max_sim:
                max_sim = sim

        return _clamp(1.0 - max_sim)

    # ── Composite entry-point ─────────────────────────────────────────────
    def compute_all(
        self,
        idea: Any,
        gaps: Sequence[Any],
        supporting_papers: Sequence[Any],
        all_domain_papers: Sequence[Any],
        closest_papers: Sequence[Any] | None = None,
    ) -> dict[str, float]:
        """Compute all five mechanical metrics and return a dict.

        Parameters
        ----------
        idea
            IdeaCandidate (or any duck-typed object with the required fields).
        gaps
            Research gaps (with ``keywords``).
        supporting_papers
            Papers cited by the idea (with ``citation_count``).
        all_domain_papers
            All papers previously cited in the domain (with ``id``).
        closest_papers
            Nearest prior-art papers (with ``abstract``).  Falls back to
            *supporting_papers* if not supplied.

        Returns
        -------
        dict mapping metric name → float in [0.0, 1.0]
        """
        if closest_papers is None:
            closest_papers = supporting_papers

        results: dict[str, float] = {
            "reference_uniqueness": self.reference_uniqueness(idea, all_domain_papers),
            "gap_coverage": self.gap_coverage(idea, gaps),
            "citation_density": self.citation_density(idea, supporting_papers),
            "method_specificity": self.method_specificity(idea),
            "prior_art_distance": self.prior_art_distance(idea, closest_papers),
        }

        # Defensive: ensure every value is in [0.0, 1.0] (HB-01)
        for name, val in results.items():
            if not (0.0 <= val <= 1.0):
                logger.warning(
                    "Metric %s out of range [0.0, 1.0]: %.6f — clamping",
                    name,
                    val,
                )
                results[name] = _clamp(val)

        return results
