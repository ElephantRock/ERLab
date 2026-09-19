"""Relevance filter: scores and admits literature by domain similarity.

Scores each paper by cosine similarity of its embedding against the
domain query embedding. Papers below threshold are filtered out,
with a guaranteed minimum count (HB-01).

Embedding contract (citation-integrity remediation): providers expose the
batch API ``embed(texts: list[str]) -> list[list[float]]``. Every call here
passes exactly one text and validates that exactly one finite vector of the
expected dimension comes back. Failures are fail-closed: a paper that
cannot be validly scored is never admitted and never scored as a legitimate
``0.0``; a provider-level failure raises instead of returning the original
corpus, because callers treat survivors as the authoritative admission set.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.3
MIN_PAPERS = 5


class RelevanceFilterError(RuntimeError):
    """Embedding-backed relevance scoring could not be performed.

    Raised instead of silently returning the unfiltered corpus. Callers
    that treat filter survivors as an authoritative admission decision
    must fail closed on this error.
    """


class LiteratureAdmissionError(RuntimeError):
    """The literature stage's admission decision failed closed.

    Raised by the stage when relevance scoring cannot be completed, so a
    run never continues with an unfiltered corpus masquerading as admitted.
    """


class EmbeddingProvider(Protocol):
    """Batch embedding contract shared with the real providers."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass
class RelevanceFilterOutcome:
    """Full admission-scoring result for audit and persistence.

    survivors: papers whose relevance_score was set — the admitted set is
        derived from these.
    scores: paper id -> score for every validly scored paper, admitted or
        below-threshold excluded.
    failures: paper id -> reason for papers that could not be validly
        scored (malformed provider output, dimension mismatch, transport
        error). They are excluded from both threshold and floor selection.
    """

    survivors: list[Any] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)


class RelevanceFilter:
    """Filter papers by relevance to the research domain.

    Uses embedding cosine similarity to score each paper's title+abstract
    against the original domain query.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        min_papers: int = MIN_PAPERS,
    ) -> None:
        self._provider = embedding_provider
        self._threshold = threshold
        self._min_papers = min_papers

    async def _embed_one(self, text: str) -> list[float]:
        """Embed one text under the batch contract and validate the output.

        The provider must receive a single-element ``list[str]`` and return
        exactly one finite numeric vector. Any shape violation is an error,
        never a zero score.
        """
        vectors = await self._provider.embed([text])
        if not isinstance(vectors, list) or len(vectors) != 1:
            shape = (
                f"list of {len(vectors)} vectors"
                if isinstance(vectors, list)
                else type(vectors).__name__
            )
            raise RelevanceFilterError(
                f"embedding provider returned {shape} for a single-text batch "
                "(expected exactly 1 vector)"
            )
        vec = vectors[0]
        if not isinstance(vec, (list, tuple)) or not vec:
            raise RelevanceFilterError(
                "embedding provider returned an empty or non-list vector"
            )
        if not all(
            isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
            for x in vec
        ):
            raise RelevanceFilterError(
                "embedding vector contains non-numeric or non-finite components"
            )
        return [float(x) for x in vec]

    async def filter_with_scores(
        self,
        papers: list[Any],
        domain_query: str,
    ) -> RelevanceFilterOutcome:
        """Score every paper and select survivors.

        Papers that cannot be validly scored are recorded in
        ``outcome.failures`` and are never eligible for admission. A
        provider-level failure (missing provider, failing query embedding)
        raises :class:`RelevanceFilterError`.
        """
        outcome = RelevanceFilterOutcome()
        if not papers:
            return outcome

        if self._provider is None:
            raise RelevanceFilterError(
                "no embedding provider — relevance admission cannot be scored"
            )

        try:
            domain_vec = await self._embed_one(domain_query)
        except RelevanceFilterError:
            raise
        except Exception as e:
            raise RelevanceFilterError(f"domain query embedding failed: {e}") from e

        scored: list[tuple[Any, float]] = []
        for result in papers:
            text = f"{result.paper.title} {result.paper.abstract or ''}"
            try:
                paper_vec = await self._embed_one(text)
                if len(paper_vec) != len(domain_vec):
                    raise RelevanceFilterError(
                        f"paper embedding dimension {len(paper_vec)} != domain "
                        f"dimension {len(domain_vec)}"
                    )
                score = _cosine_similarity(domain_vec, paper_vec)
                if not math.isfinite(score):
                    raise RelevanceFilterError("computed similarity is not finite")
                result.relevance_score = score
                scored.append((result, score))
                outcome.scores[str(result.paper.id)] = score
            except Exception as e:
                outcome.failures[str(result.paper.id)] = str(e)
                logger.warning(
                    "Relevance scoring failed for '%s': %s",
                    str(result.paper.title)[:50],
                    e,
                )

        # Deterministic ranking: score descending, source id as tie-break.
        scored.sort(key=lambda item: (-item[1], str(item[0].paper.id)))
        survivors = [r for r, s in scored if s >= self._threshold]
        if len(survivors) < self._min_papers and len(scored) >= self._min_papers:
            survivors = [r for r, _ in scored[: self._min_papers]]
        outcome.survivors = survivors

        logger.info(
            "Relevance filter: %d candidates → %d scored (%d unscorable) → %d "
            "survivors (threshold=%.2f, floor=%d)",
            len(papers),
            len(scored),
            len(outcome.failures),
            len(survivors),
            self._threshold,
            self._min_papers,
        )
        return outcome

    async def filter(self, papers: list[Any], domain_query: str) -> list[Any]:
        """Return the survivor list for the given papers."""
        outcome = await self.filter_with_scores(papers, domain_query)
        return outcome.survivors


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
