"""Reranker abstractions for second-pass retrieval scoring.

Two implementations:
  - LLMReranker: LLM scores each document 0.0-1.0 for relevance (mem0 pattern).
  - CrossEncoderReranker: sentence-transformers cross-encoder (khoj pattern).

Reference: mem0 LLMReranker, khoj cross-encoder reranking.
"""

import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ScoredDocument(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict = {}


class Reranker(ABC):
    """Abstract reranker for second-pass retrieval scoring."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[ScoredDocument]:
        ...


class LLMReranker(Reranker):
    """LLM-based reranking — scores each document 0.0-1.0 for relevance.

    Reference: mem0 LLMReranker (prompt-based scoring per document).
    """

    SCORING_PROMPT = (
        "Score this document's relevance to the query on a 0.0-1.0 scale.\n"
        "Respond with ONLY a number between 0.0 and 1.0.\n\n"
        "Query: {query}\n\n"
        "Document: {document}\n\n"
        "Relevance score:"
    )

    def __init__(self, provider):
        self._provider = provider

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[ScoredDocument]:
        scored: list[ScoredDocument] = []
        for doc in documents:
            try:
                prompt = self.SCORING_PROMPT.format(
                    query=query,
                    document=doc.get("text", "")[:2000],
                )
                response = await self._provider.complete(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=10,
                )
                score = self._extract_score(response)
            except Exception as e:
                logger.warning("LLM rerank failed for doc %s: %s", doc.get("id", "?"), e)
                score = 0.5

            scored.append(
                ScoredDocument(
                    id=doc.get("id", ""),
                    text=doc.get("text", ""),
                    score=score,
                    metadata=doc.get("metadata", {}),
                )
            )

        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k] if top_k else scored

    @staticmethod
    def _extract_score(response: str) -> float:
        text = response.strip()
        for token in text.split():
            try:
                val = float(token)
                return max(0.0, min(1.0, val))
            except ValueError:
                continue
        return 0.5


class CrossEncoderReranker(Reranker):
    """Cross-encoder reranking using sentence-transformers.

    Reference: khoj bi-encoder + cross-encoder two-stage retrieval.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[ScoredDocument]:
        self._ensure_model()

        if not documents:
            return []

        pairs = [(query, doc.get("text", "")) for doc in documents]
        assert self._model is not None
        scores = self._model.predict(pairs)

        scored = [
            ScoredDocument(
                id=doc.get("id", ""),
                text=doc.get("text", ""),
                score=float(s),
                metadata=doc.get("metadata", {}),
            )
            for doc, s in zip(documents, scores, strict=True)
        ]
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k] if top_k else scored
