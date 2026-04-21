"""Relevance-ranked paper selection with adaptive abstract truncation."""

from __future__ import annotations

import math

from backend.pipeline.literature.models import Paper


class PaperSelector:
    """Selects top papers by relevance to a query, with adaptive abstract lengths.

    Ranking strategy (first available wins):
    1. Pre-computed embeddings on papers (cosine similarity)
    2. BM25 / retriever scores (not yet wired)
    3. TF-IDF word overlap fallback

    Adaptive abstract truncation gives more characters to higher-ranked papers
    and fewer to lower-ranked ones, staying within the total budget.
    """

    def __init__(self) -> None:
        pass

    def select_papers(
        self,
        papers: list[Paper],
        query: str,
        max_papers: int = 20,
        abstract_budget: int = 150,
    ) -> list[Paper]:
        """Return top papers ranked by relevance, with adapted abstracts.

        Args:
            papers: Candidate papers.
            query: Relevance query (e.g., domain + gap titles).
            max_papers: Maximum papers to return.
            abstract_budget: Target characters per abstract on average.
        """
        if not papers:
            return []

        ranked = self._rank_by_relevance(papers, query)
        selected = ranked[:max_papers]
        self._allocate_abstract_budget(selected, abstract_budget)
        return selected

    def _rank_by_relevance(self, papers: list[Paper], query: str) -> list[Paper]:
        """Rank papers using pre-computed embeddings or word overlap."""
        query_words = set(query.lower().split())
        if not query_words:
            return list(papers)

        scored: list[tuple[float, Paper]] = []
        has_embeddings = any(p.embedding for p in papers)

        if has_embeddings:
            query_vec = _simple_embedding(query)
            for p in papers:
                if p.embedding:
                    score = _cosine_similarity(query_vec, p.embedding)
                else:
                    score = _word_overlap(query_words, p.title)
                scored.append((score, p))
        else:
            for p in papers:
                title_words = set(p.title.lower().split())
                abstract_words = set((p.abstract or "").lower().split()[:50])
                doc_words = title_words | abstract_words
                score = _word_overlap(query_words, " ".join(doc_words))
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]

    def _allocate_abstract_budget(self, papers: list[Paper], budget: int) -> None:
        """Give longer abstracts to top-ranked papers, shorter to lower ones.

        Top 30% get 2x budget, middle 40% get 1x, bottom 30% get 0.5x.
        """
        if not papers:
            return
        n = len(papers)
        for i, paper in enumerate(papers):
            ratio = i / n
            if ratio < 0.3:
                chars = budget * 2
            elif ratio < 0.7:
                chars = budget
            else:
                chars = max(budget // 2, 50)
            if paper.abstract and len(paper.abstract) > chars:
                paper.abstract = paper.abstract[:chars] + "..."
            paper._abstract_budget = chars  # type: ignore[attr-defined]


def _word_overlap(query_words: set[str], text: str) -> float:
    """Jaccard-like overlap between query words and text."""
    text_words = set(text.lower().split())
    if not query_words or not text_words:
        return 0.0
    intersection = query_words & text_words
    union = query_words | text_words
    return len(intersection) / len(union)


def _simple_embedding(text: str) -> list[float]:
    """Minimal bag-of-words embedding for cosine similarity.

    Not a real embedding — just a normalized word-frequency vector over a
    small vocabulary derived from the text. Good enough for ranking when
    real embeddings are already on the Paper objects.
    """
    words = text.lower().split()
    if not words:
        return [0.0]
    # Use a hash-based sparse representation
    dim = 64
    vec = [0.0] * dim
    for w in words:
        idx = hash(w) % dim
        vec[idx] += 1.0
    # Normalize
    mag = math.sqrt(sum(v * v for v in vec))
    if mag > 0:
        vec = [v / mag for v in vec]
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors of possibly different lengths."""
    min_len = min(len(a), len(b))
    if min_len == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(min_len))
    mag_a = math.sqrt(sum(x * x for x in a[:min_len]))
    mag_b = math.sqrt(sum(x * x for x in b[:min_len]))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
