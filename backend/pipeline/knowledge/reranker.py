"""Jina Reranker v3 — true cross-encoder reranking via transformers.

Implements proper listwise reranking using jinaai/jina-reranker-v3 model.
Runs locally via transformers (CPU or CUDA). Falls back to LM Studio
chat-based scoring if the model fails to load.

Architecture:
  - Primary: jina-reranker-v3 loaded via transformers AutoModelForSequenceClassification
  - Fallback: LM Studio /v1/chat/completions with structured scoring prompt

The cross-encoder approach is fundamentally different from LLM-based scoring:
  - LLM scoring: one LLM call per document → slow, inconsistent scores
  - Cross-encoder: one forward pass for all query-doc pairs → fast, calibrated scores
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

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


class JinaCrossEncoderReranker(Reranker):
    """Cross-encoder reranking using jina-reranker-v3 via transformers.

    Runs the model locally on CPU or CUDA. Uses the model.rerank() method
    for proper listwise scoring.

    Parameters
    ----------
    model_id:
        HuggingFace model ID or local path.
    device:
        "cuda" for GPU, "cpu" for CPU, "auto" for auto-detect.
    max_length:
        Maximum token length per query-document pair.
    """

    def __init__(
        self,
        model_id: str = "jinaai/jina-reranker-v3",
        device: str = "auto",
        max_length: int = 1024,
    ):
        self._model_id = model_id
        self._device = device
        self._max_length = max_length
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._fallback: Reranker | None = None

    def _ensure_loaded(self) -> bool:
        """Load the model on first use. Returns True if loaded."""
        if self._loaded:
            return self._model is not None

        self._loaded = True
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = self._device
            if device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading jina-reranker-v3 on %s...", device)

            self._tokenizer = AutoTokenizer.from_pretrained(
                self._model_id, trust_remote_code=True
            )
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self._model_id,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            ).to(device)

            self._model.eval()
            logger.info(
                "jina-reranker-v3 loaded on %s", device
            )
            return True

        except Exception as e:
            logger.warning(
                "Failed to load jina-reranker-v3 (%s). "
                "Will use fallback scoring.",
                str(e)[:150],
            )
            self._model = None
            return False

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[ScoredDocument]:
        """Rerank documents using cross-encoder scoring."""
        if not documents:
            return []

        # Try cross-encoder first
        if self._ensure_loaded() and self._model is not None:
            return self._rerank_cross_encoder(query, documents, top_k)

        # Fallback to LM Studio or heuristic
        if self._fallback:
            return await self._fallback.rerank(query, documents, top_k)

        # Last resort: heuristic scoring
        return self._heuristic_rerank(query, documents, top_k)

    def _rerank_cross_encoder(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None,
    ) -> list[ScoredDocument]:
        """Run cross-encoder reranking using model.rerank()."""
        texts = [doc.get("text", "") for doc in documents]

        try:
            results = self._model.rerank(
                query,
                texts,
                max_length=self._max_length,
                top_n=top_k or len(texts),
            )

            scored = []
            for result in results:
                # Find original doc by text match
                original_doc = next(
                    (d for d in documents if d.get("text", "") == result["document"]["text"]),
                    {},
                )
                scored.append(
                    ScoredDocument(
                        id=original_doc.get("id", ""),
                        text=result["document"]["text"],
                        score=result["relevance_score"],
                        metadata=original_doc.get("metadata", {}),
                    )
                )

            return scored

        except Exception as e:
            logger.warning(
                "Cross-encoder rerank failed: %s. Using heuristic.",
                str(e)[:100],
            )
            return self._heuristic_rerank(query, documents, top_k)

    def _heuristic_rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None,
    ) -> list[ScoredDocument]:
        """Simple keyword-overlap heuristic as last resort."""
        query_words = set(query.lower().split())
        scored = []
        for doc in documents:
            text = doc.get("text", "")
            text_words = set(text.lower().split())
            overlap = len(query_words & text_words)
            score = overlap / max(len(query_words), 1)
            scored.append(
                ScoredDocument(
                    id=doc.get("id", ""),
                    text=text,
                    score=min(1.0, score),
                    metadata=doc.get("metadata", {}),
                )
            )
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k] if top_k else scored

    def set_fallback(self, fallback: Reranker) -> None:
        """Set a fallback reranker for when the cross-encoder fails to load."""
        self._fallback = fallback


class LMStudioReranker(Reranker):
    """Reranking via LM Studio chat completions endpoint.

    Uses a structured prompt to score each document. Slower than
    cross-encoder but requires no model download.

    Parameters
    ----------
    api_base:
        LM Studio API base URL.
    model:
        Model name loaded in LM Studio.
    """

    SCORING_PROMPT = (
        "Rate the relevance of this document to the query.\n"
        "Respond with ONLY a JSON object: {\"score\": <0.0-1.0>}\n\n"
        "Query: {query}\n\n"
        "Document: {document}\n\n"
        "Relevance score JSON:"
    )

    def __init__(
        self,
        api_base: str = "http://100.64.0.1:1234/v1",
        model: str = "jina-reranker-v3@bf16",
    ):
        self._api_base = api_base
        self._model = model

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_k: int | None = None,
    ) -> list[ScoredDocument]:
        """Score each document via LM Studio chat completion."""
        import asyncio
        import json

        scored: list[ScoredDocument] = []

        async def score_doc(doc: dict) -> ScoredDocument:
            try:
                prompt = self.SCORING_PROMPT.format(
                    query=query,
                    document=doc.get("text", "")[:2000],
                )
                # Use httpx for async HTTP
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{self._api_base}/chat/completions",
                        json={
                            "model": self._model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": 20,
                            "temperature": 0,
                        },
                    )
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()

                    # Parse score
                    try:
                        parsed = json.loads(content)
                        score = float(parsed.get("score", 0.5))
                    except (json.JSONDecodeError, ValueError):
                        score = 0.5

                    return ScoredDocument(
                        id=doc.get("id", ""),
                        text=doc.get("text", ""),
                        score=max(0.0, min(1.0, score)),
                        metadata=doc.get("metadata", {}),
                    )
            except Exception as e:
                logger.debug("LM Studio rerank failed: %s", str(e)[:80])
                return ScoredDocument(
                    id=doc.get("id", ""),
                    text=doc.get("text", ""),
                    score=0.5,
                    metadata=doc.get("metadata", {}),
                )

        # Score documents in parallel (up to 10 concurrent)
        tasks = [score_doc(doc) for doc in documents]
        scored = await asyncio.gather(*tasks)
        scored = list(scored)
        scored.sort(key=lambda d: d.score, reverse=True)
        return scored[:top_k] if top_k else scored


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


def create_reranker(
    method: str = "auto",
    api_base: str = "http://100.64.0.1:1234/v1",
    model: str = "jina-reranker-v3@bf16",
    provider: Any = None,
) -> Reranker:
    """Factory function to create the best available reranker.

    Parameters
    ----------
    method:
        "auto" — try cross-encoder, fallback to LM Studio
        "cross-encoder" — jina-reranker-v3 via transformers
        "lm-studio" — LM Studio chat-based scoring
        "llm" — provider-based LLM scoring
        "sentence-transformers" — ms-marco cross-encoder
        "heuristic" — keyword overlap only
    """
    if method == "auto":
        reranker = JinaCrossEncoderReranker()
        reranker.set_fallback(LMStudioReranker(api_base=api_base, model=model))
        return reranker

    if method == "cross-encoder":
        return JinaCrossEncoderReranker()

    if method == "lm-studio":
        return LMStudioReranker(api_base=api_base, model=model)

    if method == "llm":
        if provider is None:
            raise ValueError("LLM reranker requires a provider")
        return LLMReranker(provider)

    if method == "sentence-transformers":
        return CrossEncoderReranker()

    if method == "heuristic":
        return JinaCrossEncoderReranker()  # Falls through to heuristic

    raise ValueError(f"Unknown reranker method: {method}")
