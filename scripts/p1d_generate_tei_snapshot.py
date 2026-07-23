"""P1D.4 — Generate embedding snapshot using TEI's gte-large-en-v1.5.

Bypasses the governed capability system (which is designed for the
production runtime and requires a database-backed binding). This is a
P1D experiment script that generates a snapshot in the same format as
the governed generator so the P1B evaluation can consume it.

Canonical text convention (matches the governed generator):
  query    = query_text verbatim (with "query: " prefix for GTE models)
  candidate = "{title}\n\n{abstract}"
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import BENCHMARK_V2, frozen_v2_cases

TEI_URL = "http://127.0.0.1:9090/v1/embeddings"
MODEL = "cpu-embed"
QUERY_PREFIX = "query: "
OUTPUT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
OUTPUT_FILE = OUTPUT_DIR / "snapshot_tei_gte_large_en_v15.json"


def embed_one(text: str) -> list[float]:
    r = httpx.post(
        TEI_URL,
        json={"model": MODEL, "input": text},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    cases = frozen_v2_cases()

    # Collect unique queries (case_id → query_text) and candidates
    queries: dict[str, str] = {}
    candidates: dict[str, dict[str, str]] = {}
    for case in cases:
        queries[case.case_id] = case.query_text
        for cand in case.candidates:
            candidates[cand.candidate_id] = {
                "title": cand.title,
                "abstract": cand.abstract,
            }

    print(f"P1D.4: generating TEI embedding snapshot")
    print(f"  model: {MODEL}")
    print(f"  queries: {len(queries)}")
    print(f"  candidates: {len(candidates)}")

    # Embed queries (with GTE query prefix)
    query_vectors: dict[str, list[float]] = {}
    t0 = time.monotonic()
    for i, (qid, qtext) in enumerate(queries.items()):
        prefixed = f"{QUERY_PREFIX}{qtext}"
        vec = embed_one(prefixed)
        query_vectors[qid] = vec
        if (i + 1) % 10 == 0:
            print(f"  queries: {i+1}/{len(queries)} ({time.monotonic()-t0:.1f}s)")
    print(f"  queries done in {time.monotonic()-t0:.1f}s")

    # Embed candidates (title + abstract, no prefix)
    candidate_vectors: dict[str, list[float]] = {}
    t0 = time.monotonic()
    for i, (cid, cdata) in enumerate(candidates.items()):
        canonical = f"{cdata['title']}\n\n{cdata['abstract']}"
        vec = embed_one(canonical)
        candidate_vectors[cid] = vec
        if (i + 1) % 20 == 0:
            print(f"  candidates: {i+1}/{len(candidates)} ({time.monotonic()-t0:.1f}s)")
    print(f"  candidates done in {time.monotonic()-t0:.1f}s")

    # Build snapshot in the same format as EmbeddingSnapshot
    snapshot = {
        "schema_version": "embedding_snapshot_v1",
        "benchmark_fingerprint": BENCHMARK_V2.get("version", "v2_unknown"),
        "embedding_profile": {
            "provider": "tei",
            "model": "Alibaba-NLP/gte-large-en-v1.5",
            "dimension": len(next(iter(query_vectors.values()))),
            "normalization": "l2",
            "query_protocol": "gte_query_prefix_v1",
            "tei_version": "1.9.3",
            "tei_sha": "06670157fb6c1523482219bdb2d1660277d38088",
        },
        "queries": {},
        "candidates": {},
    }

    for qid, qtext in queries.items():
        vec = query_vectors[qid]
        canonical = f"{QUERY_PREFIX}{qtext}"
        snapshot["queries"][qid] = {
            "text_hash": text_hash(canonical),
            "vector": vec,
        }

    for cid, cdata in candidates.items():
        vec = candidate_vectors[cid]
        canonical = f"{cdata['title']}\n\n{cdata['abstract']}"
        snapshot["candidates"][cid] = {
            "text_hash": text_hash(canonical),
            "vector": vec,
        }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(snapshot, f)

    print(f"\nSnapshot written to {OUTPUT_FILE}")
    print(f"  queries: {len(snapshot['queries'])}")
    print(f"  candidates: {len(snapshot['candidates'])}")
    print(f"  dimension: {snapshot['embedding_profile']['dimension']}")
    print(f"  size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
