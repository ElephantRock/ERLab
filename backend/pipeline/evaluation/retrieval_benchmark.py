"""Retrieval Benchmark Runner — evaluates search quality against benchmark datasets.

BATCH-RAG-01/TASK-03: Takes a BenchmarkDataset and runs literature search
for each question. Measures whether the correct source paper is found and
at what rank. Computes Hit Rate, MRR, and nDCG@K.

Design: Uses existing SearchService for search. Pure metric computation.
No modification to existing pipeline code.
"""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

from backend.pipeline.evaluation.benchmark_models import (
    BenchmarkDataset,
    BenchmarkRunReport,
    RetrievalResult,
)

if TYPE_CHECKING:
    from backend.pipeline.literature.search_service import SearchService

logger = logging.getLogger(__name__)


class RetrievalBenchmarkRunner:
    """Runs retrieval benchmarks: searches for each question, measures quality.

    Parameters
    ----------
    search_service:
        The SearchService to use for literature search.
    top_k:
        Number of results to retrieve per query.
    """

    def __init__(
        self,
        search_service: SearchService,
        top_k: int = 10,
    ) -> None:
        self._search = search_service
        self._top_k = max(1, top_k)

    async def run(
        self,
        dataset: BenchmarkDataset,
        strategy: str = "default",
    ) -> BenchmarkRunReport:
        """Run the full benchmark: search for each question, compute metrics.

        For each benchmark question:
        1. Run literature search with the question as query
        2. Check if the source paper appears in results
        3. Record its rank (position in results)
        """
        start = time.time()
        results: list[RetrievalResult] = []

        for q in dataset.questions:
            try:
                papers = await self._search.search_all(
                    query=q.question,
                    limit_per_source=self._top_k,
                )

                retrieved_ids = [p.id for p in papers]
                retrieved_titles = [p.title for p in papers]

                # Find rank of correct paper
                rank = None
                found = False
                for i, pid in enumerate(retrieved_ids):
                    if pid == q.source_paper_id:
                        rank = i + 1  # 1-indexed
                        found = True
                        break

                results.append(
                    RetrievalResult(
                        question=q.question,
                        source_paper_id=q.source_paper_id,
                        retrieved_paper_ids=retrieved_ids,
                        retrieved_titles=retrieved_titles,
                        rank_of_correct=rank,
                        found=found,
                    )
                )
            except Exception as e:
                logger.warning(
                    "Benchmark search failed for question '%s': %s",
                    q.question[:50],
                    str(e)[:100],
                )
                results.append(
                    RetrievalResult(
                        question=q.question,
                        source_paper_id=q.source_paper_id,
                        found=False,
                    )
                )

        elapsed = time.time() - start
        total = len(results)
        found_count = sum(1 for r in results if r.found)

        # Compute metrics
        hit_rate = found_count / total if total > 0 else 0.0
        mrr = compute_mrr(results)
        ndcg = compute_ndcg(results, k=self._top_k)

        report = BenchmarkRunReport(
            dataset_id=dataset.id,
            dataset_name=dataset.name,
            strategy=strategy,
            total_questions=total,
            questions_found=found_count,
            hit_rate=hit_rate,
            mrr=mrr,
            ndcg_at_k=ndcg,
            k=self._top_k,
            results=results,
            elapsed_seconds=elapsed,
        )

        logger.info(
            "Benchmark %s complete: hit_rate=%.2f, mrr=%.3f, ndcg@%d=%.3f (%.1fs)",
            dataset.id,
            hit_rate,
            mrr,
            self._top_k,
            ndcg,
            elapsed,
        )
        return report


# ── Metric computation functions ─────────────────────────────────────


def compute_hit_rate(results: list[RetrievalResult]) -> float:
    """Fraction of queries where the correct document was found.

    Hit Rate = (# queries where correct doc in top-K) / (total queries)
    """
    if not results:
        return 0.0
    found = sum(1 for r in results if r.found)
    return found / len(results)


def compute_mrr(results: list[RetrievalResult]) -> float:
    """Mean Reciprocal Rank.

    MRR = (1/|Q|) * sum(1/rank_i) for each query i
    where rank_i is the position of the first correct result.
    If not found, contribution is 0.
    """
    if not results:
        return 0.0
    reciprocal_sum = 0.0
    for r in results:
        if r.rank_of_correct is not None and r.rank_of_correct > 0:
            reciprocal_sum += 1.0 / r.rank_of_correct
    return reciprocal_sum / len(results)


def compute_ndcg(results: list[RetrievalResult], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain at K.

    For binary relevance (correct document = relevant):
    DCG@K = sum(rel_i / log2(i+1)) for i in 1..K
    IDCG@K = 1 / log2(2) = 1 (ideal: correct doc at rank 1)
    nDCG@K = DCG@K / IDCG@K
    """
    if not results:
        return 0.0

    ndcg_sum = 0.0
    for r in results:
        dcg = 0.0
        if r.found and r.rank_of_correct is not None:
            # Binary relevance: correct doc = 1, all others = 0
            dcg = 1.0 / math.log2(r.rank_of_correct + 1)
        # Ideal: correct doc at rank 1 → DCG = 1/log2(2) = 1.0
        idcg = 1.0
        ndcg_sum += dcg / idcg if idcg > 0 else 0.0

    return ndcg_sum / len(results)


def compute_precision_at_k(results: list[RetrievalResult], k: int = 10) -> float:
    """Precision@K: Fraction of top-K results that are relevant.

    For our benchmark: binary — the correct paper is the only relevant doc.
    P@K = 1 if correct in top-K, else 0. Average over all queries.
    """
    if not results:
        return 0.0
    hits = sum(1 for r in results if r.found and (r.rank_of_correct or 0) <= k)
    return hits / len(results)
