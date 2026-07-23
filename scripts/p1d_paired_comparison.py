"""P1D.4b — Full paired comparison between P1B baseline and P1D TEI.

Uses the calibrated evaluator (proven parity in P1D.4a) to compute
all required metrics and per-query comparison.

Query preprocessing (frozen):
  - GTE queries: "query: {query_text}" (per model card convention)
  - Documents: "{title}\n\n{abstract}" (no prefix)
  - P1B baseline queries: query_text verbatim (no prefix — BGE-M3 model)
  - P1B baseline documents: "{title}\n\n{abstract}"

Both snapshots were generated with these exact conventions.
"""

from __future__ import annotations

import json
import math
import random
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases

P1B_SNAPSHOT = REPO_ROOT / "docs" / "p1b_snapshot" / "snapshot.json"
TEI_SNAPSHOT = REPO_ROOT / "docs" / "p1b_snapshot" / "snapshot_tei_gte_large_en_v15.json"
OUTPUT_PATH = REPO_ROOT / "docs" / "p1b_snapshot" / "p1d_paired_comparison.json"

FROZEN_RRF_K = 60
FROZEN_FINAL_LIMIT = 20


# ── Snapshot loaders ─────────────────────────────────────────────────

def load_governed(path: Path) -> dict:
    with open(path) as f:
        s = json.load(f)
    q, c = {}, {}
    for item in s["items"]:
        if item["item_role"] == "query":
            q[item["item_id"]] = item["vector"]
        elif item["item_role"] == "candidate":
            c[item["item_id"]] = item["vector"]
    return {"queries": q, "candidates": c}


def load_tei(path: Path) -> dict:
    with open(path) as f:
        s = json.load(f)
    return {
        "queries": {k: v["vector"] for k, v in s["queries"].items()},
        "candidates": {k: v["vector"] for k, v in s["candidates"].items()},
    }


# ── Ranking policies (exact P1B formulas) ────────────────────────────

def keyword_overlap(query: str, text: str) -> float:
    qw = set(re.findall(r"\w+", query.lower()))
    if not qw:
        return 0.0
    tw = set(re.findall(r"\w+", text.lower()))
    return len(qw & tw) / len(qw)


def cosine_sim(a, b):
    return sum(x * y for x, y in zip(a, b))


def semantic_rank(qvec, cvecs):
    scores = [(cid, cosine_sim(qvec, cv)) for cid, cv in cvecs.items()]
    scores.sort(key=lambda x: -x[1])
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def lexical_rank(query, candidates):
    scores = []
    for cid, cd in candidates.items():
        scores.append((cid, keyword_overlap(query, f"{cd['title']} {cd['abstract']}")))
    scores.sort(key=lambda x: (-x[1], x[0]))
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def rrf_rank(lex, sem, k=FROZEN_RRF_K):
    scores: dict[str, float] = {}
    for r, cid in enumerate(lex, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
    for r, cid in enumerate(sem, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])[:FROZEN_FINAL_LIMIT]]


# ── Graded metrics (exact P1B formulas) ──────────────────────────────

def _grade_for(case, cid):
    prov = case.judgments.get(cid)
    return prov.final_grade() if prov else 0


def _dcg(grades, k):
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades[:k]))


def ndcg(ranked_grades, k):
    dcg = _dcg(ranked_grades, k)
    ideal = sorted(ranked_grades, reverse=True)
    idcg = _dcg(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def mrr(ranked_grades, k):
    for i, g in enumerate(ranked_grades[:k]):
        if g > 0:
            return 1.0 / (i + 1)
    return 0.0


def p_at_k(ranked_grades, k, threshold=1):
    return sum(1 for g in ranked_grades[:k] if g >= threshold) / k if k else 0.0


def r_at_k(ranked_grades, k, all_grades, threshold=1):
    total = sum(1 for g in all_grades if g >= threshold)
    if total == 0:
        return 1.0
    return sum(1 for g in ranked_grades[:k] if g >= threshold) / total


def top1(ranked_grades):
    return 1.0 if (ranked_grades and ranked_grades[0] > 0) else 0.0


# ── Evaluation ───────────────────────────────────────────────────────

def evaluate_snapshot(cases, snapshot, policy_name):
    qvecs, cvecs = snapshot["queries"], snapshot["candidates"]
    per_case = {}
    macro = {k: [] for k in ["ndcg5", "ndcg10", "mrr10", "p5", "r5", "r10", "r20", "top1"]}
    n = 0

    for case in cases:
        cands = {c.candidate_id: {"title": c.title, "abstract": c.abstract} for c in case.candidates}
        cvecs_case = {cid: cvecs[cid] for cid in cands if cid in cvecs}
        qvec = qvecs.get(case.case_id)
        all_grades = [_grade_for(case, c.candidate_id) for c in case.candidates]
        if not any(g > 0 for g in all_grades):
            continue

        if policy_name == "lexical":
            ranked = lexical_rank(case.query_text, cands)
        elif policy_name == "semantic_only":
            if not qvec:
                continue
            ranked = semantic_rank(qvec, cvecs_case)
        elif policy_name == "hybrid_rrf":
            lex = lexical_rank(case.query_text, cands)
            sem = semantic_rank(qvec, cvecs_case) if qvec else list(cands.keys())
            ranked = rrf_rank(lex, sem)
        else:
            continue

        rg = [_grade_for(case, cid) for cid in ranked]
        n += 1
        vals = {
            "ndcg5": ndcg(rg, 5), "ndcg10": ndcg(rg, 10),
            "mrr10": mrr(rg, 10), "p5": p_at_k(rg, 5),
            "r5": r_at_k(rg, 5, all_grades), "r10": r_at_k(rg, 10, all_grades),
            "r20": r_at_k(rg, 20, all_grades), "top1": top1(rg),
        }
        per_case[case.case_id] = vals
        for k in macro:
            macro[k].append(vals[k])

    return {
        "macro": {k: sum(v) / n if v else 0 for k, v in macro.items()},
        "n_cases": n,
        "per_case": per_case,
    }


# ── Paired bootstrap CI ──────────────────────────────────────────────

def paired_bootstrap_ci(baseline_vals: list[float], tei_vals: list[float],
                        n_bootstrap: int = 10000, ci: float = 0.95) -> dict:
    """Paired bootstrap CI on per-query deltas."""
    assert len(baseline_vals) == len(tei_vals)
    n = len(baseline_vals)
    deltas = [t - b for b, t in zip(baseline_vals, tei_vals)]
    observed_mean = sum(deltas) / n

    rng = random.Random(42)  # deterministic seed
    boot_means = []
    for _ in range(n_bootstrap):
        indices = [rng.randint(0, n - 1) for _ in range(n)]
        boot_delta = sum(deltas[i] for i in indices) / n
        boot_means.append(boot_delta)

    boot_means.sort()
    lo_idx = int((1 - ci) / 2 * n_bootstrap)
    hi_idx = int((1 + ci) / 2 * n_bootstrap)
    return {
        "mean_delta": observed_mean,
        "ci_lo": boot_means[lo_idx],
        "ci_hi": boot_means[hi_idx],
        "n_bootstrap": n_bootstrap,
        "ci_level": ci,
        "significant": (boot_means[lo_idx] > 0 or boot_means[hi_idx] < 0),
    }


def main() -> int:
    cases = frozen_v2_cases()
    p1b_snapshot = load_governed(P1B_SNAPSHOT)
    tei_snapshot = load_tei(TEI_SNAPSHOT)

    print(f"P1D.4b: Full paired comparison")
    print(f"  P1B model: qwen3-embedding-0.6b (dim {len(next(iter(p1b_snapshot['queries'].values())))})")
    print(f"  TEI model: gte-large-en-v1.5 (dim {len(next(iter(tei_snapshot['queries'].values())))})")
    print(f"  Cases: {len(cases)}")
    print()

    results = {}
    for policy in ["lexical", "semantic_only", "hybrid_rrf"]:
        # Lexical is the same for both snapshots (it doesn't use embeddings)
        if policy == "lexical":
            p1b_result = evaluate_snapshot(cases, p1b_snapshot, policy)
            tei_result = p1b_result  # lexical is embedding-independent
        else:
            p1b_result = evaluate_snapshot(cases, p1b_snapshot, policy)
            tei_result = evaluate_snapshot(cases, tei_snapshot, policy)

        results[policy] = {"p1b": p1b_result, "tei": tei_result}

        print(f"\n{'='*80}")
        print(f"Policy: {policy}")
        print(f"{'Metric':12s} {'P1B baseline':>14s} {'P1D TEI':>14s} {'Delta':>10s}")
        print(f"{'-'*50}")
        for metric in ["ndcg5", "ndcg10", "mrr10", "p5", "r5", "r10", "r20", "top1"]:
            b = p1b_result["macro"][metric]
            t = tei_result["macro"][metric]
            d = t - b
            sign = "+" if d >= 0 else ""
            print(f"{metric:12s} {b:14.4f} {t:14.4f} {sign}{d:9.4f}")
        print(f"{'n_cases':12s} {p1b_result['n_cases']:14d} {tei_result['n_cases']:14d}")

        # Per-query comparison (for embedding-dependent policies)
        if policy != "lexical":
            p1b_pc = p1b_result["per_case"]
            tei_pc = tei_result["per_case"]
            common = sorted(set(p1b_pc.keys()) & set(tei_pc.keys()))

            improved = sum(1 for c in common if tei_pc[c]["ndcg5"] > p1b_pc[c]["ndcg5"] + 1e-9)
            regressed = sum(1 for c in common if tei_pc[c]["ndcg5"] < p1b_pc[c]["ndcg5"] - 1e-9)
            tied = sum(1 for c in common if abs(tei_pc[c]["ndcg5"] - p1b_pc[c]["ndcg5"]) <= 1e-9)

            print(f"\nPer-query nDCG@5 comparison:")
            print(f"  improved: {improved}/{len(common)}")
            print(f"  regressed: {regressed}/{len(common)}")
            print(f"  tied: {tied}/{len(common)}")

            # Top1 changes
            top1_improved = sum(1 for c in common if tei_pc[c]["top1"] > p1b_pc[c]["top1"])
            top1_regressed = sum(1 for c in common if tei_pc[c]["top1"] < p1b_pc[c]["top1"])
            print(f"  top-1 improved: {top1_improved}")
            print(f"  top-1 regressed: {top1_regressed}")

            # Bootstrap CI on nDCG@5
            b_vals = [p1b_pc[c]["ndcg5"] for c in common]
            t_vals = [tei_pc[c]["ndcg5"] for c in common]
            ci = paired_bootstrap_ci(b_vals, t_vals)
            print(f"\nPaired bootstrap CI on nDCG@5 delta:")
            print(f"  mean delta: {ci['mean_delta']:.6f}")
            print(f"  95% CI: [{ci['ci_lo']:.6f}, {ci['ci_hi']:.6f}]")
            print(f"  significant (excludes 0): {ci['significant']}")

            # Largest changes
            deltas = [(c, tei_pc[c]["ndcg5"] - p1b_pc[c]["ndcg5"]) for c in common]
            deltas.sort(key=lambda x: -x[1])
            print(f"\n  Largest improvements:")
            for cid, d in deltas[:3]:
                print(f"    {cid}: {d:+.4f}")
            print(f"  Largest regressions:")
            for cid, d in deltas[-3:]:
                print(f"    {cid}: {d:+.4f}")

    # Save full results
    # (serialize per_case as lists for JSON)
    serializable = {}
    for policy, pr in results.items():
        serializable[policy] = {
            "p1b_macro": pr["p1b"]["macro"],
            "tei_macro": pr["tei"]["macro"],
            "n_cases": pr["p1b"]["n_cases"],
        }
        if policy != "lexical":
            p1b_pc = pr["p1b"]["per_case"]
            tei_pc = pr["tei"]["per_case"]
            common = sorted(set(p1b_pc.keys()) & set(tei_pc.keys()))
            serializable[policy]["per_query"] = [
                {
                    "case_id": c,
                    "p1b_ndcg5": p1b_pc[c]["ndcg5"],
                    "tei_ndcg5": tei_pc[c]["ndcg5"],
                    "delta": tei_pc[c]["ndcg5"] - p1b_pc[c]["ndcg5"],
                    "p1b_top1": p1b_pc[c]["top1"],
                    "tei_top1": tei_pc[c]["top1"],
                }
                for c in common
            ]

    with open(OUTPUT_PATH, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"\nFull results saved to {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
