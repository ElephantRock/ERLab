"""
Reranker Microservice — runs on the RTX 3080 Ti machine.

Loads jina-reranker-v3 with CUDA BF16 acceleration and exposes
a /v1/rerank endpoint compatible with any RAG pipeline.

Usage:
    python reranker_service.py [--host 0.0.0.0] [--port 8100] [--model jinaai/jina-reranker-v3]

Endpoints:
    POST /v1/rerank   — rerank documents against a query
    GET  /health       — health check with model status
"""

import argparse
import json
import logging
import time
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reranker-service")

app = FastAPI(title="Reranker Service", version="1.0.0")

# ── Global model state ──────────────────────────────────────────────

_model = None
_tokenizer = None
_device = "cpu"
_model_id = "jinaai/jina-reranker-v3"
_max_length = 1024


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
        results = _model.rerank(
            request.query,
            request.documents,
            max_length=request.max_length or _max_length,
            top_n=request.top_n or len(request.documents),
        )

        elapsed = time.time() - start

        rerank_docs = [
            RerankDocument(
                text=r["document"]["text"],
                index=r["index"],
                relevance_score=r["relevance_score"],
            )
            for r in results
        ]

        logger.info(
            "Reranked %d docs in %.1fms (top_n=%d)",
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
                "total_tokens": sum(
                    len(d.text.split()) for d in rerank_docs
                ),
            },
        )

    except Exception as e:
        logger.error("Rerank failed: %s", str(e)[:200])
        raise HTTPException(status_code=500, detail=str(e)[:200])


# ── Startup ──────────────────────────────────────────────────────────

@app.on_event("startup")
async def load_model():
    """Load jina-reranker-v3 on startup."""
    global _model, _tokenizer, _device

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    _device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if _device == "cuda" else torch.float32

    logger.info("Loading %s on %s (dtype=%s)...", _model_id, _device, dtype)
    t0 = time.time()

    _tokenizer = AutoTokenizer.from_pretrained(_model_id, trust_remote_code=True)
    _model = AutoModelForSequenceClassification.from_pretrained(
        _model_id,
        trust_remote_code=True,
        torch_dtype=dtype,
    ).to(_device)
    _model.eval()

    elapsed = time.time() - t0
    logger.info("Model loaded in %.1fs on %s", elapsed, _device)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Reranker Microservice")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8100, help="Bind port")
    parser.add_argument("--model", default="jinaai/jina-reranker-v3", help="Model ID")
    parser.add_argument("--max-length", type=int, default=1024, help="Max token length")
    args = parser.parse_args()

    global _model_id, _max_length
    _model_id = args.model
    _max_length = args.max_length

    logger.info("Starting reranker service on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
