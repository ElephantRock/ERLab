"""Method DNA Extraction — structured fingerprint for cross-run recombination.

Extracts a compact, comparable fingerprint from each ``IdeaCandidate`` so that
ideas from different pipeline runs can be meaningfully recombined.  The
extraction is fully deterministic and requires no LLM calls.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from backend.pipeline.generation.models import IdeaCandidate

# ── Minimal English stopword set (no external NLTK dependency) ──────────

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "it", "its", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "will", "would", "shall", "should", "may", "might", "must",
        "can", "could", "not", "no", "nor", "so", "if", "then", "than",
        "too", "very", "just", "about", "above", "after", "again", "all",
        "also", "am", "any", "because", "before", "between", "both", "each",
        "few", "further", "get", "got", "he", "her", "here", "him", "his",
        "how", "i", "into", "more", "most", "my", "new", "now", "only",
        "other", "our", "out", "own", "same", "she", "some", "such", "that",
    "their", "them", "there", "these", "they", "this", "those", "through",
        "up", "us", "we", "what", "when", "where", "which", "while", "who",
        "whom", "why", "you", "your",
    }
)

_MAX_TECHNIQUE_LEN = 100
_MAX_KEYWORDS = 10


def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def _extract_keywords(text: str, top_n: int = _MAX_KEYWORDS) -> list[str]:
    """Return the most frequent non-stopword tokens from *text*."""
    cleaned = _normalise(text)
    # Keep only alphanumeric tokens (drops punctuation)
    tokens = re.findall(r"[a-z0-9]+", cleaned)
    # Remove stopwords and very short tokens
    tokens = [t for t in tokens if len(t) > 2 and t not in _STOPWORDS]

    freq: dict[str, int] = {}
    for tok in tokens:
        freq[tok] = freq.get(tok, 0) + 1

    ranked = sorted(freq, key=lambda w: (-freq[w], w))
    return ranked[:top_n]


def _extract_core_technique(text: str) -> str:
    """Return the first sentence/clause of *text*, capped at 100 chars."""
    if not text.strip():
        return "unknown"
    # Split on sentence-ending punctuation or semicolons
    parts = re.split(r"[.;!?]", text, maxsplit=1)
    core = parts[0].strip()
    if len(core) > _MAX_TECHNIQUE_LEN:
        core = core[: _MAX_TECHNIQUE_LEN].rsplit(" ", 1)[0].rstrip(",") + "…"
    return core if core else "unknown"


def _infer_domain(title: str, method: str) -> str:
    """Lightweight domain inference from title + method text."""
    blob = f"{title} {method}".lower()
    domain_hits = [
        ("healthcare", ["health", "medical", "clinical", "patient"]),
        ("NLP", ["nlp", "language", "text", "translation", "summarization"]),
        ("computer vision", ["vision", "image", "visual", "detection", "segmentation"]),
        ("reinforcement learning", ["reinforcement", "reward", "policy", "agent"]),
        ("robotics", ["robot", "manipulation", "locomotion"]),
        ("finance", ["finance", "trading", "portfolio", "risk"]),
        ("education", ["education", "tutor", "learning analytics"]),
    ]
    for domain_name, keywords in domain_hits:
        if any(kw in blob for kw in keywords):
            return domain_name
    return "general"


def _infer_evaluation(text: str) -> str:
    """Return evaluation approach, defaulting to 'unknown' when empty."""
    return text.strip() if text.strip() else "unknown"


# ── Public API ───────────────────────────────────────────────────────────


@dataclass
class MethodDNA:
    """Structured fingerprint of a research idea's methodology."""

    core_technique: str
    domain: str
    evaluation_approach: str
    method_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON / API responses."""
        return {
            "core_technique": self.core_technique,
            "domain": self.domain,
            "evaluation_approach": self.evaluation_approach,
            "method_keywords": self.method_keywords,
        }


class MethodDNAExtractor:
    """Deterministic, LLM-free extractor for ``MethodDNA`` from ideas."""

    def extract(self, idea: IdeaCandidate) -> MethodDNA:
        """Extract structured method DNA from a single idea.

        Handles missing/empty fields by falling back to ``"unknown"``
        placeholders so downstream recombination never crashes on bad data.
        """
        method_text = idea.proposed_method or ""

        return MethodDNA(
            core_technique=_extract_core_technique(method_text),
            domain=_infer_domain(idea.title or "", method_text),
            evaluation_approach=_infer_evaluation(idea.evaluation_approach or ""),
            method_keywords=_extract_keywords(
                f"{idea.title or ''} {method_text}"
            ),
        )

    def extract_batch(self, ideas: list[IdeaCandidate]) -> list[MethodDNA]:
        """Extract DNA from multiple ideas."""
        return [self.extract(idea) for idea in ideas]
