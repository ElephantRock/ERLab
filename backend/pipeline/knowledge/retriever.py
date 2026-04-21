"""Two-stage retriever with RRF fusion of BM25 + semantic search.

Stage 1: Parallel BM25 keyword + ChromaDB semantic search.
Stage 2: Reciprocal Rank Fusion (RRF) merges both result sets.
Stage 3 (optional): Cross-encoder or LLM reranking for final scoring.

Reference: langchain RRF fusion (k=60), khoj bi-encoder/cross-encoder,
haystack hybrid retrieval with distribution-based normalization.
"""

import asyncio
import logging
from enum import Enum

from pydantic import BaseModel

from backend.pipeline.knowledge.bm25_index import BM25Index
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.query_transform import QueryTransformer
from backend.pipeline.knowledge.reranker import Reranker, ScoredDocument
from backend.pipeline.knowledge.vector_store import VectorStore

logger = logging.getLogger(__name__)


class RetrievalSource(str, Enum):
    BM25 = "bm25"
    SEMANTIC = "semantic"
    FUSED = "fused"
    RERANKED = "reranked"


class RetrievalResult(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict = {}
    source: RetrievalSource = RetrievalSource.FUSED


class TwoStageRetriever:
    """Two-stage retrieval: BM25+semantic RRF fusion with optional reranking."""

    def __init__(
        self,
        vector_store: VectorStore,
        bm25_index: BM25Index,
        embedding_service: EmbeddingService,
        reranker: Reranker | None = None,
        query_transformer: QueryTransformer | None = None,
        rrf_k: int = 60,
        retrieval_mode: str = "hybrid",
    ):
        self._vector_store = vector_store
        self._bm25 = bm25_index
        self._embedding = embedding_service
        self._reranker = reranker
        self._query_transformer = query_transformer
        self._default_rrf_k = rrf_k
        self._retrieval_mode = retrieval_mode

    async def retrieve(
        self,
        query: str,
        n_results: int = 10,
        overfetch: int = 3,
        rrf_k: int | None = None,
        min_score: float = 0.0,
        filter_metadata: dict | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve documents via hybrid BM25+semantic search with RRF fusion.

        Args:
            query: Search query text.
            n_results: Number of final results to return.
            overfetch: Multiplier for candidate generation (fetch n_results*overfetch from each source).
            rrf_k: Reciprocal Rank Fusion constant (default 60, from langchain). Falls back to constructor default.
            min_score: Minimum RRF score threshold for results.
            filter_metadata: Optional metadata filters passed to both sources.
        """
        effective_k = rrf_k if rrf_k is not None else self._default_rrf_k
        fetch_count = n_results * overfetch

        # Stage 0: Query transformation (optional multi-query)
        queries = [query]
        if self._query_transformer:
            queries = await self._query_transformer.transform(query)

        # Stage 1: Parallel retrieval from both sources (across all query variants)
        all_bm25: list[dict] = []
        all_semantic: list[dict] = []
        for q in queries:
            semantic_task = self._vector_store.query(q, fetch_count, filter_metadata)

            if self._retrieval_mode == "semantic":
                # Semantic-only mode: skip BM25
                semantic_results = await semantic_task
                bm25_results: list[dict] = []
            else:
                # Hybrid mode: parallel BM25 + semantic
                bm25_task = asyncio.to_thread(self._bm25.query, q, fetch_count, filter_metadata)

                bm25_results_raw: list[dict] | Exception
                semantic_results_raw: list[dict] | Exception
                bm25_results_raw, semantic_results_raw = await asyncio.gather(
                    bm25_task, semantic_task, return_exceptions=True
                )

                bm25_results = [] if isinstance(bm25_results_raw, Exception) else bm25_results_raw
                if isinstance(bm25_results_raw, Exception):
                    logger.warning("BM25 query failed for variant '%s': %s", q[:50], bm25_results_raw)
                semantic_results = [] if isinstance(semantic_results_raw, Exception) else semantic_results_raw
                if isinstance(semantic_results_raw, Exception):
                    logger.warning(
                        "Semantic query failed for variant '%s': %s", q[:50], semantic_results_raw
                    )

            if isinstance(bm25_results, Exception):
                logger.warning("BM25 query failed for variant '%s': %s", q[:50], bm25_results)
                bm25_results = []
            if isinstance(semantic_results, Exception):
                logger.warning(
                    "Semantic query failed for variant '%s': %s", q[:50], semantic_results
                )
                semantic_results = []

            all_bm25.extend(bm25_results)
            all_semantic.extend(semantic_results)

        # Stage 2: Reciprocal Rank Fusion
        fused = self._rrf_fuse(
            bm25_results=all_bm25,
            semantic_results=all_semantic,
            k=effective_k,
        )

        # Apply minimum score filter
        if min_score > 0:
            fused = [r for r in fused if r.score >= min_score]

        # Stage 3: Optional reranking
        if self._reranker and fused:
            reranked = await self._rerank(query, fused, n_results)
            return reranked

        return fused[:n_results]

    def _rrf_fuse(
        self,
        bm25_results: list[dict],
        semantic_results: list[dict],
        k: int = 60,
    ) -> list[RetrievalResult]:
        """Reciprocal Rank Fusion: merge BM25 and semantic results by rank.

        RRF score = sum(1 / (k + rank)) for each source where doc appears.
        """
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            docs[doc_id] = doc

        for rank, doc in enumerate(semantic_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = doc

        fused = [
            RetrievalResult(
                id=doc_id,
                text=docs[doc_id].get("text", ""),
                score=score,
                metadata=docs[doc_id].get("metadata", {}),
                source=RetrievalSource.FUSED,
            )
            for doc_id, score in scores.items()
        ]
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused

    async def _rerank(
        self,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """Apply reranker to candidates and return top_k."""
        docs_for_reranker = [
            {"id": r.id, "text": r.text, "metadata": r.metadata} for r in candidates
        ]
        scored: list[ScoredDocument] = await self._reranker.rerank(query, docs_for_reranker, top_k)  # type: ignore[union-attr]
        return [
            RetrievalResult(
                id=d.id,
                text=d.text,
                score=d.score,
                metadata=d.metadata,
                source=RetrievalSource.RERANKED,
            )
            for d in scored
        ]
