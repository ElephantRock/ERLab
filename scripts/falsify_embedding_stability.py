"""Falsification harness for embedding-host stability under isolated loads.

Verifies isolation via `lms ps` (NOT /v1/models, which returns the full
downloaded catalog regardless of actual load state). Does NOT retry through
crashes or 400s. Records resp_model on every 2xx for routing detection.
"""
from __future__ import annotations
import argparse, json, math, sys, time, statistics, subprocess
import httpx


def build_passages(n: int = 500) -> list[str]:
    passages = []
    for i in range(n):
        target_len = 80 + (i % 15) * 80  # 80..1200 chars
        prefix = (f"This is synthetic passage number {i} for embedding preflight testing. "
                  f"It contains realistic-length scientific text about topic {i % 10}. ")
        body = (f"The measurement of quantity {i} under condition set {i % 7} "
                f"yields a representative result suitable for load testing. ") * 50
        passages.append((prefix + body)[:target_len])
    return passages


PASSAGES = build_passages(500)


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def check_isolation(base_url: str, requested_model: str) -> dict:
    loaded = []
    source = "lms_ps"
    try:
        out = subprocess.run(["lms", "ps"], capture_output=True, text=True, timeout=15).stdout
        for line in out.splitlines():
            line = line.strip()
            if not line or line.startswith("IDENTIFIER") or line.startswith("No models"):
                continue
            parts = line.split()
            if parts:
                loaded.append(parts[0])
    except Exception:
        source = "api_catalog_UNRELIABLE"
        r = httpx.get(f"{base_url}/v1/models", timeout=10)
        loaded = [m["id"] for m in r.json().get("data", [])]
    return {"loaded": loaded, "count": len(loaded), "source": source, "requested": requested_model}


def embed_once(base_url: str, model: str, texts, timeout: float = 120) -> dict:
    t0 = time.perf_counter()
    try:
        r = httpx.post(f"{base_url}/v1/embeddings",
                       json={"model": model, "input": texts}, timeout=timeout)
        dt = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            body = r.json()
            vecs = [d["embedding"] for d in sorted(body["data"], key=lambda x: x["index"])]
            resp_model = body.get("model", "<missing>")
            non_finite = sum(1 for v in vecs if not all(math.isfinite(x) for x in v))
            return {"ok": True, "status": 200, "latency_ms": dt, "count": len(vecs),
                    "resp_model": resp_model, "non_finite": non_finite,
                    "dim": len(vecs[0]) if vecs else 0}
        return {"ok": False, "status": r.status_code, "latency_ms": dt, "body": r.text[:500]}
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return {"ok": False, "status": -1, "latency_ms": dt, "body": str(e)[:500]}


def _finalize(result: dict) -> dict:
    if "error" in result:
        result["verdict"] = "HARNESS_ERROR"
        return result
    s = result.get("sustained", {})
    if s.get("skipped"):
        result["verdict"] = "FAIL_CRASHED_IN_WARMUP"
        return result
    total = s.get("total_embedded", 0)
    crashes = s.get("crashes", 0)
    nf = s.get("non_finite", 0)
    if total >= 500 and crashes == 0 and nf == 0 and not result["routing"]["routing_detected"]:
        result["verdict"] = "PASS"
    elif result["routing"]["routing_detected"]:
        result["verdict"] = "FAIL_ROUTING_DETECTED"
    elif crashes > 0:
        result["verdict"] = "FAIL_CRASH"
    elif nf > 0:
        result["verdict"] = "FAIL_NON_FINITE"
    else:
        result["verdict"] = "FAIL_INCOMPLETE"
    return result


def run_phase(base_url: str, requested_model: str, phase: str) -> dict:
    iso = check_isolation(base_url, requested_model)
    if iso["count"] != 1:
        return {"phase": phase, "requested_model": requested_model,
                "error": "isolation_violated", "loaded_at_start": iso["loaded"],
                "note": "Harness requires exactly one model loaded."}

    result = {
        "phase": phase, "requested_model": requested_model, "loaded_at_start": iso["loaded"],
        "length_probe": {}, "warmup": {}, "sustained": {},
        "routing": {"resp_models_seen": set(), "routing_detected": False},
        "failures": [],
    }

    # Length probe
    threshold = None
    probe_body = ("The methodology section describes the experimental apparatus and the "
                  "controlled conditions under which each sample was measured repeatedly. ") * 64
    for L in [32, 64, 128, 256, 384, 512, 768, 1024, 2048, 4096]:
        res = embed_once(base_url, requested_model, probe_body[:L])
        if res.get("ok"):
            threshold = {"last_ok_chars": L, "resp_model": res["resp_model"]}
            result["routing"]["resp_models_seen"].add(res["resp_model"])
        else:
            threshold = {"first_fail_chars": L,
                         "last_ok_chars": threshold["last_ok_chars"] if threshold else 0,
                         "failure": res}
            post = check_isolation(base_url, requested_model)
            threshold["model_loaded_after"] = post["count"]
            break
    result["length_probe"] = threshold

    if threshold and "first_fail_chars" in threshold and threshold.get("model_loaded_after", 1) == 0:
        result["warmup"] = {"completed": 0, "crashed_during_warmup": True,
                            "note": "Crashed in length probe before warmup"}
        result["sustained"] = {"skipped": "crashed in length probe"}
        result["routing"]["resp_models_seen"] = sorted(result["routing"]["resp_models_seen"])
        return _finalize(result)

    # Warmup
    warm_ok = 0
    warm_resp_models = []
    for i in range(20):
        res = embed_once(base_url, requested_model, PASSAGES[i])
        if res.get("ok"):
            warm_ok += 1
            warm_resp_models.append(res["resp_model"])
            result["routing"]["resp_models_seen"].add(res["resp_model"])
        else:
            result["failures"].append({"stage": "warmup", "idx": i, **res})
            if "crashed" in res.get("body", "").lower() or res.get("status") in (500, 502, -1):
                result["warmup"] = {"completed": warm_ok, "crashed_during_warmup": True, "first_crash": res}
                result["routing"]["resp_models_seen"] = sorted(result["routing"]["resp_models_seen"])
                result["sustained"] = {"skipped": "crashed during warmup"}
                return _finalize(result)
    result["warmup"] = {"completed": warm_ok, "crashed_during_warmup": False}

    # Sustained
    total_embedded = 0
    crashes = 0
    non_finite_total = 0
    latencies = []
    first_failure = None
    shortest_failing = None
    resp_model_tally = {}
    for bs in [1, 8, 32]:
        for start_idx in range(0, 500, bs):
            batch = PASSAGES[start_idx:start_idx + bs]
            if not batch:
                continue
            res = embed_once(base_url, requested_model, batch)
            if res.get("ok"):
                total_embedded += res["count"]
                non_finite_total += res["non_finite"]
                latencies.append(res["latency_ms"] / res["count"])
                resp_model_tally[res["resp_model"]] = resp_model_tally.get(res["resp_model"], 0) + 1
            else:
                crashes += 1
                if first_failure is None:
                    first_failure = {"batch_idx": start_idx, "batch_size": bs, **res}
                for t in batch:
                    cand = {"chars": len(t), "words": len(t.split()),
                            "est_tokens": est_tokens(t), "text": t[:120]}
                    if shortest_failing is None or len(t) < shortest_failing["chars"]:
                        shortest_failing = cand
                post = check_isolation(base_url, requested_model)
                if post["count"] == 0:
                    result["_model_unloaded_after_crash"] = True
                    break
                break
        if result.get("_model_unloaded_after_crash"):
            break

    distinct = set(resp_model_tally.keys()) | set(warm_resp_models)
    result["routing"]["resp_models_seen"] = sorted(result["routing"]["resp_models_seen"])
    result["routing"]["routing_detected"] = any(
        m != requested_model and requested_model not in m for m in distinct)
    result["routing"]["resp_model_tally"] = resp_model_tally
    result["sustained"] = {
        "total_embedded": total_embedded, "target": 500,
        "completion_pct": round(100 * total_embedded / 500, 1),
        "crashes": crashes, "non_finite": non_finite_total,
        "batch_sizes_tested": [1, 8, 32],
        "per_item_latency_ms": {
            "mean": round(statistics.mean(latencies), 1) if latencies else None,
            "p50": round(statistics.median(latencies), 1) if latencies else None,
        },
        "first_failure": first_failure,
        "shortest_failing_input": shortest_failing,
    }
    return _finalize(result)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", required=True)
    p.add_argument("--requested-model", required=True)
    p.add_argument("--phase", required=True, choices=["cold", "warm"])
    p.add_argument("--out", required=True)
    args = p.parse_args()

    print(f"Falsification harness — phase={args.phase} model={args.requested_model}")
    print("=" * 60)
    iso = check_isolation(args.base_url, args.requested_model)
    print(f"[isolation] loaded models ({iso['source']}): {iso['loaded']}")
    if iso["count"] != 1:
        print(f"[isolation] VIOLATED — {iso['count']} models loaded. Need exactly 1.")
        sys.exit(1)

    result = run_phase(args.base_url, args.requested_model, args.phase)
    print(f"\n[result] verdict: {result.get('verdict', '?')}")
    if result.get("length_probe"):
        lp = result["length_probe"]
        if "first_fail_chars" in lp:
            print(f"  length probe: FAIL at {lp['first_fail_chars']} chars (last ok {lp['last_ok_chars']})")
        else:
            print(f"  length probe: OK through {lp.get('last_ok_chars')} chars")
    if result.get("sustained") and not result["sustained"].get("skipped"):
        s = result["sustained"]
        print(f"  embedded: {s['total_embedded']}/500 ({s['completion_pct']}%)")
        print(f"  crashes: {s['crashes']}  non_finite: {s['non_finite']}")
        print(f"  resp_model tally: {result['routing'].get('resp_model_tally', {})}")
        if s.get("shortest_failing_input"):
            sf = s["shortest_failing_input"]
            print(f"  shortest failing: {sf['chars']} chars / {sf['words']} words / ~{sf['est_tokens']} tok")
    elif result.get("sustained", {}).get("skipped"):
        print(f"  sustained SKIPPED: {result['sustained']['skipped']}")

    from pathlib import Path
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    print(f"\n[written] {out}")
    sys.exit(0)


if __name__ == "__main__":
    main()
