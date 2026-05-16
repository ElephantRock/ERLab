"""
Reranker Microservice — jina-reranker-v3 via transformers AutoModel.

Uses the custom JinaForRanking class with trust_remote_code=True.
Works on CPU (~2s for 5 docs) or CUDA (~50ms for 5 docs).

Usage:
    python reranker_service.py [--host 0.0.0.0] [--port 8100]

Endpoints:
    POST /v1/rerank   — rerank documents against a query
    GET  /health       — health check with model status
"""

import argparse
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reranker-service")

# ── Global model state ──────────────────────────────────────────────

_model = None
_device = "cpu"
_model_id = "jinaai/jina-reranker-v3"
_model_revision = "10fb694fc21f7a710a563ff1eb977a460f3868e4"  # pinned for trust_remote_code safety


# ── Request / Response models ────────────────────────────────────────

class RerankRequest(BaseModel):
    """Request format matching Jina/Cohere rerank API."""

    query: str = Field(..., min_length=1, max_length=4096)
    documents: list[str] = Field(..., min_length=1, max_length=64)
    top_n: int | None = Field(default=None, ge=1)
    max_length: int = Field(default=1024, ge=128, le=8192)

    @field_validator("documents")
    @classmethod
    def validate_documents(cls, docs: list[str]) -> list[str]:
        if any(not d.strip() for d in docs):
            raise ValueError("documents must not contain empty strings")
        return docs


class RerankDocument(BaseModel):
    text: str
    index: int
    relevance_score: float


class RerankResponse(BaseModel):
    model: str
    results: list[RerankDocument]
    usage: dict[str, int]


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Load model on startup, cleanup on shutdown."""
    global _model, _device

    import torch
    from transformers import AutoModel

    _device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info("Loading %s (rev=%s) on %s...", _model_id, _model_revision[:12], _device)
    t0 = time.perf_counter()

    _model = AutoModel.from_pretrained(
        _model_id,
        revision=_model_revision,
        trust_remote_code=True,
    )

    if _device == "cuda":
        _model = _model.to(_device)

    _model.eval()

    elapsed = time.perf_counter() - t0
    logger.info("Model loaded in %.1fs on %s", elapsed, _device)

    yield  # application runs here

    # Cleanup
    _model = None


app = FastAPI(title="Reranker Service", version="2.2.0", lifespan=lifespan)


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check with model status."""
    return {
        "status": "ok" if _model is not None else "loading",
        "model": _model_id,
        "revision": _model_revision[:12],
        "device": _device,
        "cuda_available": _device == "cuda",
    }


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """Rerank documents against a query using jina-reranker-v3."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    top_n = request.top_n if request.top_n is not None else len(request.documents)
    top_n = min(top_n, len(request.documents))

    start = time.perf_counter()

    try:
        results = _model.rerank(
            request.query,
            request.documents,
            top_n=top_n,
            max_doc_length=request.max_length,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        rerank_docs = [
            RerankDocument(
                text=str(r["document"]),
                index=int(r["index"]),
                relevance_score=float(r["relevance_score"]),
            )
            for r in results
        ]

        logger.info(
            "Reranked %d docs in %.0fms; returned=%d; device=%s",
            len(request.documents),
            elapsed_ms,
            len(rerank_docs),
            _device,
        )

        return RerankResponse(
            model=_model_id,
            results=rerank_docs,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": sum(len(d.split()) for d in request.documents),
            },
        )

    except TypeError as e:
        logger.exception("Rerank API mismatch")
        raise HTTPException(status_code=500, detail=f"Model API mismatch: {str(e)[:200]}")

    except Exception as e:
        logger.exception("Rerank failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reranker Microservice")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8100, help="Bind port")
    args = parser.parse_args()

    logger.info("Starting reranker service on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
