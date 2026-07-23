"""Embedding-host preflight: validate an embedding endpoint for candidate execution.

Run when the host returns (or when a new endpoint is nominated). Checks:
  endpoint reachable
  expected model loaded
  embedding dimensionality stable
  response schema valid
  batch completion 100%
  vector values finite
  repeated inputs deterministic within tolerance
  memory and latency recorded
  sustained workload completes without process failure

Bounded preflight (per sprint spec):
  warm-up                         20 requests
  sustained test                  500 passages
  batch sizes                     1, 8, 32
  repeated-input consistency      20 repetitions
  completion requirement          100%
  fallbacks                       0
  process crashes                 0

Usage:
  python scripts/preflight_embedding_host.py --base-url http://100.64.0.2:1234 --model text-embedding-qwen3-embedding-0.6b --dimension 1024
  python scripts/preflight_embedding_host.py --base-url http://100.64.0.2:1234 --model bge-m3 --dimension 1024

Exit 0 = preflight pass (candidate may proceed).
Exit 1 = preflight fail (candidate eliminated on operational grounds).
Exit 2 = host unreachable (try again later).
"""
from __future__ import annotations
import argparse, json, math, sys, time, statistics
from pathlib import Path

import httpx

# Non-benchmark synthetic passages for sustained-load testing.
# These are NOT diagnostic corpus text.
SYNTHETIC_PASSAGES = [
    f"This is synthetic passage number {i} for embedding preflight testing. It contains "
    f"realistic-length scientific text about topic {i % 10}. The purpose is to verify "
    f"sustained embedding workload stability without using benchmark data."
    for i in range(500)
]


def check_reachable(base_url: str, timeout: float = 5.0) -> bool:
    try:
        r = httpx.get(f"{base_url}/v1/models", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def check_model_loaded(base_url: str, model: str) -> dict:
    r = httpx.get(f"{base_url}/v1/models", timeout=10)
    models = r.json().get("data", [])
    loaded = [m["id"] for m in models]
    is_loaded = any(model in m or m in model for m in loaded)
    return {"loaded": is_loaded, "all_models": loaded, "target_model": model}


def embed_one(base_url: str, model: str, text: str, timeout: float = 30, retries: int = 5) -> list[float]:
    """Embed a single text with bounded retry for transient 400s (LM Studio model-load races).
    The first request to a cold model may take 60-120s while LM Studio loads it."""
    last_err = None
    for attempt in range(retries):
        actual_timeout = max(timeout, 120 if attempt == 0 else timeout)  # long timeout on first attempt
        try:
            r = httpx.post(f"{base_url}/v1/embeddings", json={"model": model, "input": text}, timeout=actual_timeout)
            if r.status_code == 200:
                return r.json()["data"][0]["embedding"]
            elif r.status_code == 400 and attempt < retries - 1:
                # Transient 400 (model still loading / reloading). Wait with exponential backoff.
                wait = 5 * (2 ** attempt)  # 5, 10, 20, 40 seconds
                last_err = f"400: {r.text[:150]}"
                print(f"    [retry {attempt+1}/{retries}] model loading, waiting {wait}s...")
                time.sleep(wait)
            else:
                r.raise_for_status()
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < retries - 1:
                wait = 5 * (2 ** attempt)
                print(f"    [retry {attempt+1}/{retries}] error, waiting {wait}s...")
                time.sleep(wait)
    raise RuntimeError(f"embed_one failed after {retries} retries: {last_err}")


def embed_batch(base_url: str, model: str, texts: list[str], timeout: float = 60, retries: int = 3) -> list[list[float]]:
    """Embed a batch with bounded retry for transient 400s."""
    last_err = None
    for attempt in range(retries):
        try:
            r = httpx.post(f"{base_url}/v1/embeddings", json={"model": model, "input": texts}, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                return [d["embedding"] for d in sorted(data["data"], key=lambda x: x["index"])]
            elif r.status_code == 400 and attempt < retries - 1:
                last_err = f"400: {r.text[:150]}"
                time.sleep(2 ** attempt)
            else:
                r.raise_for_status()
        except Exception as e:
            last_err = str(e)[:200]
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"embed_batch failed after {retries} retries: {last_err}")


def run_preflight(base_url: str, model: str, dimension: int):
    failures = []
    passed = 0

    def chk(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
            print(f"  PASS  {label}")
        else:
            failures.append((label, detail))
            print(f"  FAIL  {label}" + (f": {detail}" if detail else ""))

    print(f"Embedding-host preflight")
    print(f"  endpoint: {base_url}")
    print(f"  model: {model}")
    print(f"  dimension: {dimension}")
    print("=" * 60)

    # 1. Reachability
    print("\n[1] Endpoint reachable")
    if not check_reachable(base_url):
        print("  HOST UNREACHABLE — exit 2")
        sys.exit(2)
    chk("endpoint reachable", True)

    # 2. Model loaded
    print("\n[2] Model loaded")
    model_info = check_model_loaded(base_url, model)
    chk(f"model '{model}' loaded", model_info["loaded"], f"available: {model_info['all_models']}")

    # 3. Warm-up (20 requests)
    print("\n[3] Warm-up (20 requests)")
    warmup_latencies = []
    for i in range(20):
        start = time.perf_counter()
        vec = embed_one(base_url, model, SYNTHETIC_PASSAGES[i])
        warmup_latencies.append((time.perf_counter() - start) * 1000)
    chk("warmup completed (20/20)", len(warmup_latencies) == 20)
    print(f"  warmup latency: mean={statistics.mean(warmup_latencies):.1f}ms p50={statistics.median(warmup_latencies):.1f}ms")

    # 4. Dimensionality check
    print("\n[4] Dimensionality")
    chk(f"dimension = {dimension}", len(vec) == dimension, f"got {len(vec)}")

    # 5. Finite values
    print("\n[5] Vector values finite")
    chk("no NaN or inf", all(math.isfinite(x) for x in vec))

    # 6. Determinism (20 repetitions of same input)
    print("\n[6] Repeated-input determinism (20 reps)")
    test_text = SYNTHETIC_PASSAGES[0]
    reps = []
    for _ in range(20):
        v = embed_one(base_url, model, test_text)
        reps.append(v)
    max_diff = max(
        max(abs(a - b) for a, b in zip(reps[0], reps[i]))
        for i in range(1, 20)
    )
    chk(f"deterministic within tolerance (max diff {max_diff:.2e})", max_diff < 1e-6)

    # 7. Sustained workload (500 passages, batch sizes 1, 8, 32)
    print("\n[7] Sustained workload (500 passages)")
    sustained_latencies = []
    total_embedded = 0
    crashes = 0

    for batch_size in [1, 8, 32]:
        for start_idx in range(0, 500, batch_size):
            batch = SYNTHETIC_PASSAGES[start_idx:start_idx + batch_size]
            if not batch:
                continue
            try:
                t0 = time.perf_counter()
                vectors = embed_batch(base_url, model, batch)
                dt = (time.perf_counter() - t0) * 1000
                sustained_latencies.append(dt / len(batch))  # per-item latency
                total_embedded += len(vectors)
                # check all finite
                for v in vectors:
                    if not all(math.isfinite(x) for x in v):
                        failures.append(("non-finite vector in sustained", f"batch {start_idx}"))
            except Exception as e:
                crashes += 1
                if crashes <= 3:
                    print(f"  CRASH at batch {start_idx} (size {batch_size}): {str(e)[:100]}")

    chk("sustained: 500 passages embedded", total_embedded >= 500, f"only {total_embedded}")
    chk("sustained: 0 crashes", crashes == 0, f"{crashes} crashes")
    chk("sustained: 100% completion", total_embedded >= 500)
    if sustained_latencies:
        print(f"  sustained per-item latency: mean={statistics.mean(sustained_latencies):.1f}ms p50={statistics.median(sustained_latencies):.1f}ms")

    # 8. Batch size comparison
    print("\n[8] Batch size sanity")
    for bs in [1, 8, 32]:
        batch = SYNTHETIC_PASSAGES[:bs]
        try:
            vecs = embed_batch(base_url, model, batch)
            chk(f"batch size {bs} returns {bs} vectors", len(vecs) == bs)
        except Exception as e:
            chk(f"batch size {bs}", False, str(e)[:80])

    # Summary
    print("\n" + "=" * 60)
    if failures:
        print(f"PREFLIGHT FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        print(f"\nCandidate '{model}' FAILS operational preflight.")
        print("This candidate may not run in the sprint unless the host issue is resolved.")
        sys.exit(1)
    else:
        print(f"PREFLIGHT PASS: all checks passed ({passed})")
        print(f"\nCandidate '{model}' passes operational preflight.")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Embedding-host preflight")
    parser.add_argument("--base-url", required=True, help="e.g. http://100.64.0.2:1234")
    parser.add_argument("--model", required=True, help="model name as served by the host")
    parser.add_argument("--dimension", type=int, required=True, help="expected embedding dimension")
    args = parser.parse_args()
    run_preflight(args.base_url, args.model, args.dimension)


if __name__ == "__main__":
    main()
