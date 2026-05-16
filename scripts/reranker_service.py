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

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reranker-service")

app = FastAPI(title="Reranker Service", version="2.1.0")

# ── Global model state ──────────────────────────────────────────────

_model = None
_device = "cpu"
_model_id = "jinaai/jina-reranker-v3"


class RerankRequest(BaseModel):
    """Request format matching Jina/Cohere rerank API."""

    query: str
    documents: list[str]
    top_n: int | None = None
    max_length: int = 1024


class RerankDocument(BaseModel):
    text: str
    index: int
    relevance_score: float


class RerankResponse(BaseModel):
    model: str
    results: list[RerankDocument]
    usage: dict[str, int]


# ── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check with model status."""
    return {
        "status": "ok" if _model is not None else "loading",
        "model": _model_id,
        "device": _device,
        "cuda_available": _device == "cuda",
    }


@app.post("/v1/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest):
    """Rerank documents against a query using jina-reranker-v3."""
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start = time.time()

    try:
        top_n = request.top_n or len(request.documents)

        results = _model.rerank(
            request.query,
            request.documents,
            top_n=top_n,
            max_doc_length=request.max_length,
        )

        elapsed = time.time() - start

        rerank_docs = [
            RerankDocument(
                text=r["document"] if isinstance(r["document"], str) else str(r["document"]),
                index=int(r["index"]),
                relevance_score=float(r["relevance_score"]),
            )
            for r in results
        ]

        logger.info(
            "Reranked %d docs in %.0fms (top_n=%d)",
            len(request.documents),
            elapsed * 1000,
            len(rerank_docs),
        )

        return RerankResponse(
            model=_model_id,
            results=rerank_docs,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": sum(len(d.text.split()) for d in rerank_docs),
            },
        )

    except Exception as e:
        logger.error("Rerank failed: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ── Startup ──────────────────────────────────────────────────────────

@app.on_event("startup")
async def load_model():
    """Load jina-reranker-v3 on startup."""
    global _model, _device

    import torch
    from transformers import AutoModel

    _device = "cuda" if torch.cuda.is_available() else "cpu"

    logger.info("Loading %s on %s...", _model_id, _device)
    t0 = time.time()

    _model = AutoModel.from_pretrained(
        _model_id,
        trust_remote_code=True,
    )

    if _device == "cuda":
        _model = _model.to(_device)

    _model.eval()

    elapsed = time.time() - t0
    logger.info("Model loaded in %.1fs on %s", elapsed, _device)


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
