"""Retrieval Metrics — measures literature search quality.

BATCH-RAG-02/TASK-01: Pure metric computation functions for evaluating
how well the literature search retrieves relevant papers.

Metrics:
  - Hit Rate: Fraction of queries returning ≥1 relevant result
  - MRR (Mean Reciprocal Rank): Average position of first relevant result
  - nDCG@K (Normalized Discounted Cumulative Gain): Ranking quality
  - Precision@K: Fraction of top-K that are relevant
  - Recall@K: Fraction of known relevant docs in top-K
  - MAP (Mean Average Precision): Average precision across all ranks

All functions are pure math — no external dependencies.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class RetrievedDocument:
    """A document retrieved by search, with relevance information."""

    doc_id: str
    rank: int  # 1-indexed position in results
    score: float = 0.0  # search engine relevance score
    is_relevant: bool = False  # ground-truth relevance


@dataclass
class QueryMetrics:
    """Metrics for a single query."""

    query: str
    hit: bool = False  # Did we find at least 1 relevant doc?
    first_relevant_rank: int | None = None
    precision_at_k: dict[int, float] = field(default_factory=dict)
    average_precision: float = 0.0  # For MAP computation


@dataclass
class RetrievalMetricsReport:
    """Aggregated metrics across all queries in a search."""

    total_queries: int = 0
    total_documents_retrieved: int = 0

    # Core metrics
    hit_rate: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: dict[int, float] = field(default_factory=dict)
    map_score: float = 0.0
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)

    # Per-query details
    query_metrics: list[QueryMetrics] = field(default_factory=list)

    # Metadata
    domain: str = ""
    strategy: str = ""
    search_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_queries": self.total_queries,
            "total_documents_retrieved": self.total_documents_retrieved,
            "hit_rate": round(self.hit_rate, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_k": {str(k): round(v, 4) for k, v in self.ndcg_at_k.items()},
            "map_score": round(self.map_score, 4),
            "recall_at_k": {str(k): round(v, 4) for k, v in self.recall_at_k.items()},
            "precision_at_k": {str(k): round(v, 4) for k, v in self.precision_at_k.items()},
            "domain": self.domain,
            "strategy": self.strategy,
            "search_sources": self.search_sources,
        }


def compute_retrieval_metrics(
    queries_with_results: list[tuple[str, list[RetrievedDocument]]],
    k_values: list[int] | None = None,
) -> RetrievalMetricsReport:
    """Compute all retrieval metrics from search results.

    Parameters
    ----------
    queries_with_results:
        List of (query, retrieved_documents) tuples.
    k_values:
        K values for computing nDCG@K, Precision@K, Recall@K.
        Default: [5, 10, 20].
    """
    if k_values is None:
        k_values = [5, 10, 20]

    if not queries_with_results:
        return RetrievalMetricsReport()

    total_queries = len(queries_with_results)
    total_docs = 0
    hits = 0
    reciprocal_ranks: list[float] = []
    average_precisions: list[float] = []
    query_metrics: list[QueryMetrics] = []

    # Per-K accumulators
    ndcg_per_k: dict[int, list[float]] = {k: [] for k in k_values}
    precision_per_k: dict[int, list[float]] = {k: [] for k in k_values}
    recall_per_k: dict[int, list[float]] = {k: [] for k in k_values}

    for query, docs in queries_with_results:
        total_docs += len(docs)
        relevant_docs = [d for d in docs if d.is_relevant]
        total_relevant = len(relevant_docs)

        # Hit: at least 1 relevant doc
        hit = len(relevant_docs) > 0
        if hit:
            hits += 1

        # First relevant rank
        first_rank = None
        for d in docs:
            if d.is_relevant:
                first_rank = d.rank
                break

        # Reciprocal rank
        rr = 1.0 / first_rank if first_rank else 0.0
        reciprocal_ranks.append(rr)

        # Average precision (for MAP)
        ap = _average_precision(docs)
        average_precisions.append(ap)

        # Per-K metrics
        for k in k_values:
            top_k = [d for d in docs if d.rank <= k]
            relevant_in_k = sum(1 for d in top_k if d.is_relevant)

            # Precision@K
            p_at_k = relevant_in_k / k if k > 0 else 0.0
            precision_per_k[k].append(p_at_k)

            # Recall@K
            r_at_k = relevant_in_k / total_relevant if total_relevant > 0 else 0.0
            recall_per_k[k].append(r_at_k)

            # nDCG@K
            ndcg = _ndcg_at_k(docs, k)
            ndcg_per_k[k].append(ndcg)

        query_metrics.append(
            QueryMetrics(
                query=query,
                hit=hit,
                first_relevant_rank=first_rank,
                average_precision=ap,
            )
        )

    # Aggregate
    report = RetrievalMetricsReport(
        total_queries=total_queries,
        total_documents_retrieved=total_docs,
        hit_rate=hits / total_queries if total_queries else 0.0,
        mrr=sum(reciprocal_ranks) / total_queries if total_queries else 0.0,
        map_score=sum(average_precisions) / total_queries if total_queries else 0.0,
        query_metrics=query_metrics,
    )

    for k in k_values:
        report.ndcg_at_k[k] = (
            sum(ndcg_per_k[k]) / len(ndcg_per_k[k]) if ndcg_per_k[k] else 0.0
        )
        report.precision_at_k[k] = (
            sum(precision_per_k[k]) / len(precision_per_k[k])
            if precision_per_k[k]
            else 0.0
        )
        report.recall_at_k[k] = (
            sum(recall_per_k[k]) / len(recall_per_k[k]) if recall_per_k[k] else 0.0
        )

    return report


def _average_precision(docs: list[RetrievedDocument]) -> float:
    """Compute Average Precision for a single query.

    AP = sum(P@k * rel(k)) / total_relevant
    """
    relevant_count = 0
    precision_sum = 0.0

    for doc in docs:
        if doc.is_relevant:
            relevant_count += 1
            precision_at_rank = relevant_count / doc.rank
            precision_sum += precision_at_rank

    total_relevant = sum(1 for d in docs if d.is_relevant)
    if total_relevant == 0:
        return 0.0
    return precision_sum / total_relevant


def _ndcg_at_k(docs: list[RetrievedDocument], k: int) -> float:
    """Compute nDCG@K for a single query.

    DCG@K = sum(rel(i) / log2(i+1)) for i in 1..K
    IDCG@K = DCG of ideal ranking (all relevant docs first)
    nDCG@K = DCG@K / IDCG@K
    """
    top_k = [d for d in docs if d.rank <= k]

    # DCG@K (binary relevance: 1 if relevant, 0 otherwise)
    dcg = 0.0
    for doc in top_k:
        if doc.is_relevant:
            dcg += 1.0 / math.log2(doc.rank + 1)

    # IDCG@K: ideal ranking — relevant docs first
    total_relevant = sum(1 for d in docs if d.is_relevant)
    ideal_count = min(total_relevant, k)
    idcg = 0.0
    for i in range(1, ideal_count + 1):
        idcg += 1.0 / math.log2(i + 1)

    if idcg == 0:
        return 0.0
    return dcg / idcg


def evaluate_search_results(
    search_results: list[dict],
    relevant_ids: set[str],
    query: str = "",
    k_values: list[int] | None = None,
) -> RetrievalMetricsReport:
    """Convenience function: evaluate raw search results against known relevant IDs.

    Parameters
    ----------
    search_results:
        List of dicts with 'id' and optionally 'score' keys.
    relevant_ids:
        Set of document IDs that are known to be relevant.
    query:
        The search query string.
    """
    docs = [
        RetrievedDocument(
            doc_id=r.get("id", ""),
            rank=i + 1,
            score=r.get("score", 0.0),
            is_relevant=r.get("id", "") in relevant_ids,
        )
        for i, r in enumerate(search_results)
    ]
    return compute_retrieval_metrics(
        [(query, docs)],
        k_values=k_values,
    )
