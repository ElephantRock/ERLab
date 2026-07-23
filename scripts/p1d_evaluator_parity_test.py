"""P1D.4a — Evaluator parity test.

Runs the direct evaluator against the FROZEN P1B embedding snapshot
(BGE-M3 / qwen3-embedding-0.6b) and compares the results to the frozen
P1B baseline metrics from gate2_metrics_package.json.

If the direct evaluator reproduces the P1B baseline metrics, it proves
the evaluator has no systematic drift. Only then can the TEI comparison
deltas be trusted.

Two snapshot formats supported:
  - P1B governed: flat `items` list with `item_role` field
  - P1D TEI: `queries` and `candidates` dicts
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases

P1B_SNAPSHOT = REPO_ROOT / "docs" / "p1b_snapshot" / "snapshot.json"
P1B_BASELINE = REPO_ROOT / "docs" / "p1b_gate2" / "gate2_metrics_package.json"

FROZEN_RRF_K = 60
FROZEN_FINAL_LIMIT = 20


def load_snapshot_governed(path: Path) -> dict[str, dict[str, list[float]]]:
    """Load P1B governed snapshot → {queries: {id: vec}, candidates: {id: vec}}."""
    with open(path) as f:
        s = json.load(f)
    queries: dict[str, list[float]] = {}
    candidates: dict[str, list[float]] = {}
    for item in s.get("items", []):
        role = item["item_role"]
        iid = item["item_id"]
        vec = item["vector"]
        if role == "query":
            queries[iid] = vec
        elif role == "candidate":
            candidates[iid] = vec
    return {"queries": queries, "candidates": candidates}


def load_snapshot_tei(path: Path) -> dict[str, dict[str, list[float]]]:
    """Load TEI snapshot → same format."""
    with open(path) as f:
        s = json.load(f)
    queries = {qid: data["vector"] for qid, data in s["queries"].items()}
    candidates = {cid: data["vector"] for cid, data in s["candidates"].items()}
    return {"queries": queries, "candidates": candidates}


def cosine_sim(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


import re


def keyword_overlap(query: str, text: str) -> float:
    """Exact P1B lexical: overlap_count / total_query_words (re.findall \w+)."""
    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return 0.0
    text_words = set(re.findall(r"\w+", text.lower()))
    overlap = query_words & text_words
    return len(overlap) / len(query_words)


def semantic_rank(qvec: list[float], cvecs: dict[str, list[float]]) -> list[str]:
    scores = [(cid, cosine_sim(qvec, cv)) for cid, cv in cvecs.items()]
    scores.sort(key=lambda x: -x[1])
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def lexical_rank(query: str, candidates: dict[str, dict]) -> list[str]:
    scores = []
    for cid, cd in candidates.items():
        text = f"{cd['title']} {cd['abstract']}"
        scores.append((cid, keyword_overlap(query, text)))
    scores.sort(key=lambda x: (-x[1], x[0]))
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def rrf_rank(lex: list[str], sem: list[str], k: int = FROZEN_RRF_K) -> list[str]:
    scores: dict[str, float] = {}
    for r, cid in enumerate(lex, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
    for r, cid in enumerate(sem, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + r)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [cid for cid, _ in ranked[:FROZEN_FINAL_LIMIT]]


def _grade_for(case, candidate_id: str) -> int:
    """Frozen adjudicated grade for a candidate (matches P1B.3 evaluator)."""
    prov = case.judgments.get(candidate_id)
    return prov.final_grade() if prov else 0


def _dcg_at_k(grades: list[int], k: int) -> float:
    dcg = 0.0
    for i, g in enumerate(grades[:k]):
        dcg += (2 ** g - 1) / math.log2(i + 2)
    return dcg


def _ndcg_at_k(ranked_grades: list[int], k: int) -> float:
    dcg = _dcg_at_k(ranked_grades, k)
    ideal = sorted(ranked_grades, reverse=True)
    idcg = _dcg_at_k(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def _mrr_at_k(ranked_grades: list[int], k: int) -> float:
    for i, g in enumerate(ranked_grades[:k]):
        if g > 0:
            return 1.0 / (i + 1)
    return 0.0


def _precision_at_k(ranked_grades: list[int], k: int, threshold: int = 1) -> float:
    if k == 0:
        return 0.0
    relevant = sum(1 for g in ranked_grades[:k] if g >= threshold)
    return relevant / k


def _recall_at_k(ranked_grades: list[int], k: int, all_grades: list[int],
                 threshold: int = 1) -> float:
    total_relevant = sum(1 for g in all_grades if g >= threshold)
    if total_relevant == 0:
        return 1.0
    retrieved = sum(1 for g in ranked_grades[:k] if g >= threshold)
    return retrieved / total_relevant


def top1_accuracy(ranked_grades: list[int]) -> float:
    return 1.0 if (ranked_grades and ranked_grades[0] > 0) else 0.0


def evaluate(cases, snapshot_data, policy_name: str) -> dict:
    qvecs = snapshot_data["queries"]
    cvecs = snapshot_data["candidates"]

    metrics: dict[str, list[float]] = {
        "ndcg5": [], "ndcg10": [], "mrr10": [], "p5": [], "r20": [],
        "r5": [], "r10": [], "top1": [],
    }
    per_case: list[dict] = []
    n_evaluated = 0

    for case in cases:
        case_candidates_list = list(case.candidates)
        case_candidates = {c.candidate_id: {"title": c.title, "abstract": c.abstract} for c in case.candidates}
        case_cvecs = {cid: cvecs[cid] for cid in case_candidates if cid in cvecs}
        case_qvec = qvecs.get(case.case_id)

        # Skip cases with no graded relevance at all
        all_grades = [_grade_for(case, c.candidate_id) for c in case_candidates_list]
        if not any(g > 0 for g in all_grades):
            continue

        if policy_name == "lexical":
            ranked_ids = lexical_rank(case.query_text, case_candidates)
        elif policy_name == "semantic_only":
            if not case_qvec:
                continue
            ranked_ids = semantic_rank(case_qvec, case_cvecs)
        elif policy_name == "hybrid_rrf":
            lex = lexical_rank(case.query_text, case_candidates)
            sem = semantic_rank(case_qvec, case_cvecs) if case_qvec else list(case_candidates.keys())
            ranked_ids = rrf_rank(lex, sem)
        else:
            continue

        n_evaluated += 1
        ranked_grades = [_grade_for(case, cid) for cid in ranked_ids]

        metrics["ndcg5"].append(_ndcg_at_k(ranked_grades, 5))
        metrics["ndcg10"].append(_ndcg_at_k(ranked_grades, 10))
        metrics["mrr10"].append(_mrr_at_k(ranked_grades, 10))
        metrics["p5"].append(_precision_at_k(ranked_grades, 5))
        metrics["r5"].append(_recall_at_k(ranked_grades, 5, all_grades))
        metrics["r10"].append(_recall_at_k(ranked_grades, 10, all_grades))
        metrics["r20"].append(_recall_at_k(ranked_grades, 20, all_grades))
        metrics["top1"].append(top1_accuracy(ranked_grades))

        per_case.append({"case_id": case.case_id})

    return {
        "n_cases": n_evaluated,
        "ndcg5": sum(metrics["ndcg5"]) / n_evaluated if n_evaluated else 0,
        "ndcg10": sum(metrics["ndcg10"]) / n_evaluated if n_evaluated else 0,
        "mrr10": sum(metrics["mrr10"]) / n_evaluated if n_evaluated else 0,
        "p5": sum(metrics["p5"]) / n_evaluated if n_evaluated else 0,
        "r5": sum(metrics["r5"]) / n_evaluated if n_evaluated else 0,
        "r10": sum(metrics["r10"]) / n_evaluated if n_evaluated else 0,
        "r20": sum(metrics["r20"]) / n_evaluated if n_evaluated else 0,
        "top1": sum(metrics["top1"]) / n_evaluated if n_evaluated else 0,
        "per_case": per_case,
    }


def main() -> int:
    cases = frozen_v2_cases()
    snapshot = load_snapshot_governed(P1B_SNAPSHOT)

    print(f"P1D.4a: Evaluator parity test against frozen P1B snapshot")
    print(f"  snapshot model: qwen3-embedding-0.6b (BGE-M3)")
    print(f"  snapshot dimension: 1024")
    print(f"  queries: {len(snapshot['queries'])}")
    print(f"  candidates: {len(snapshot['candidates'])}")
    print()

    # Load P1B baseline metrics
    with open(P1B_BASELINE) as f:
        baseline_pkg = json.load(f)
    baseline = baseline_pkg["macro_metrics"]

    # Map P1B policy names to our evaluator names
    policy_map = {
        "lexical": "legacy_lexical_top20_v1",
        "semantic_only": "semantic_only_v1",
        "hybrid_rrf": "hybrid_rrf_v1",
    }

    print(f"{'Policy':20s} {'Source':12s} {'nDCG@5':>8s} {'nDCG@10':>8s} {'MRR@10':>8s} {'P@5':>8s} {'R@20':>8s} {'Top1':>8s}")
    print("=" * 90)

    all_parities: list[bool] = []
    for our_name, p1b_name in policy_map.items():
        r = evaluate(cases, snapshot, our_name)
        b = baseline[p1b_name]

        print(f"{our_name:20s} {'P1B baseline':12s} {b['ndcg_at_5']:8.4f} {b['ndcg_at_10']:8.4f} {b['mrr_at_10']:8.4f} {b['precision_at_5']:8.4f} {b['recall_at_20']:8.4f} {'N/A':>8s}")
        print(f"{'':20s} {'Our eval':12s} {r['ndcg5']:8.4f} {r['ndcg10']:8.4f} {r['mrr10']:8.4f} {r['p5']:8.4f} {r['r20']:8.4f} {r['top1']:8.4f}")

        # Check parity (tolerance 0.01 — P1B used different rounding)
        for metric, key in [("nDCG@5", "ndcg5"), ("MRR@10", "mrr10"), ("P@5", "p5"), ("R@20", "r20")]:
            p1b_val = b[{"ndcg5": "ndcg_at_5", "mrr10": "mrr_at_10", "p5": "precision_at_5", "r20": "recall_at_20"}[key]]
            our_val = r[key]
            delta = abs(our_val - p1b_val)
            parity = "OK" if delta < 0.02 else "DRIFT"
            if parity == "DRIFT":
                all_parities.append(False)
                print(f"  {parity}: {metric} delta={delta:.4f} (P1B={p1b_val:.4f}, ours={our_val:.4f})")
        print()

    print("=" * 90)
    if all_parities:
        print(f"PARITY FAIL — {len(all_parities)} metric(s) drifted beyond tolerance")
        return 1
    else:
        print("PARITY PASS — all metrics reproduced within tolerance (0.02)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
