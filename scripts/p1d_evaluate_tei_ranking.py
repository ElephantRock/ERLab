"""P1D.4 — Evaluate TEI embeddings against the frozen P1B corpus.

Computes the same ranking policies and metrics as the P1B.3 evaluation,
but using the TEI-generated embedding snapshot instead of the governed
BGE-M3 snapshot.

Policies:
  - semantic_only (cosine similarity ranking)
  - hybrid_rrf (reciprocal rank fusion of lexical + semantic, k=60)

Metrics (per the frozen P1B contract):
  - MRR@10
  - nDCG@5, nDCG@10
  - Precision@5
  - Recall@20

Comparison is against the frozen P1B baseline results.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases

SNAPSHOT_PATH = REPO_ROOT / "docs" / "p1b_snapshot" / "snapshot_tei_gte_large_en_v15.json"
FROZEN_RRF_K = 60
FROZEN_FINAL_LIMIT = 20


def load_snapshot() -> dict:
    with open(SNAPSHOT_PATH) as f:
        return json.load(f)


def cosine_sim(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def keyword_overlap(query: str, candidate_text: str) -> int:
    """Simple keyword overlap count (matches the legacy lexical policy)."""
    q_terms = set(query.lower().split())
    c_terms = set(candidate_text.lower().split())
    return len(q_terms & c_terms)


def semantic_rank(query_vec: list[float], candidate_vecs: dict[str, list[float]]) -> list[str]:
    """Rank candidates by cosine similarity to the query vector."""
    scores = [(cid, cosine_sim(query_vec, cv)) for cid, cv in candidate_vecs.items()]
    scores.sort(key=lambda x: -x[1])
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def lexical_rank(query: str, candidates: dict[str, dict]) -> list[str]:
    """Rank candidates by keyword overlap count."""
    scores = []
    for cid, cdata in candidates.items():
        text = f"{cdata['title']} {cdata['abstract']}"
        scores.append((cid, keyword_overlap(query, text)))
    scores.sort(key=lambda x: (-x[1], x[0]))  # tie-break by candidate_id
    return [cid for cid, _ in scores[:FROZEN_FINAL_LIMIT]]


def rrf_rank(lexical: list[str], semantic: list[str], k: int = FROZEN_RRF_K) -> list[str]:
    """Reciprocal Rank Fusion of two ranked lists."""
    scores: dict[str, float] = {}
    for rank, cid in enumerate(lexical, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank)
    for rank, cid in enumerate(semantic, 1):
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [cid for cid, _ in ranked[:FROZEN_FINAL_LIMIT]]


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for i, cid in enumerate(ranked[:k], 1):
        if cid in relevant:
            dcg += 1.0 / math.log2(i + 1)
    ideal_n = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_n + 1))
    return dcg / idcg if idcg > 0 else 0.0


def mrr_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    for i, cid in enumerate(ranked[:k], 1):
        if cid in relevant:
            return 1.0 / i
    return 0.0


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    hits = sum(1 for cid in ranked[:k] if cid in relevant)
    return hits / min(k, len(ranked)) if ranked else 0.0


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hits = sum(1 for cid in ranked[:k] if cid in relevant)
    return hits / len(relevant)


def evaluate_policy(
    cases,
    snapshot: dict,
    policy_fn,
    policy_name: str,
) -> dict:
    """Evaluate a ranking policy across all cases."""
    query_vecs = snapshot["queries"]
    candidate_vecs = snapshot["candidates"]

    all_ndcg5 = []
    all_ndcg10 = []
    all_mrr10 = []
    all_p5 = []
    all_r20 = []
    per_case: list[dict] = []

    for case in cases:
        case_id = case.case_id
        query_text = case.query_text
        case_candidates = {c.candidate_id: {"title": c.title, "abstract": c.abstract} for c in case.candidates}
        case_candidate_vecs = {cid: candidate_vecs[cid]["vector"] for cid in case_candidates if cid in candidate_vecs}
        case_query_entry = query_vecs.get(case_id)
        case_query_vec = case_query_entry.get("vector") if case_query_entry else None

        # Get relevant candidates (adjudicated_grade >= 2 on 0-3 scale)
        relevant = set()
        for cand_id, judgment in case.judgments.items():
            grade = getattr(judgment, "adjudicated_grade", None)
            if grade is not None and grade >= 2:
                relevant.add(cand_id)

        if not relevant:
            continue  # skip cases with no relevant items

        # Rank
        if policy_name == "semantic_only":
            if case_query_vec:
                ranked = semantic_rank(case_query_vec, case_candidate_vecs)
            else:
                continue
        elif policy_name == "lexical":
            ranked = lexical_rank(query_text, case_candidates)
        elif policy_name == "hybrid_rrf":
            lex = lexical_rank(query_text, case_candidates)
            if case_query_vec:
                sem = semantic_rank(case_query_vec, case_candidate_vecs)
            else:
                sem = list(case_candidates.keys())
            ranked = rrf_rank(lex, sem)
        else:
            continue

        ndcg5 = ndcg_at_k(ranked, relevant, 5)
        ndcg10 = ndcg_at_k(ranked, relevant, 10)
        mrr10 = mrr_at_k(ranked, relevant, 10)
        p5 = precision_at_k(ranked, relevant, 5)
        r20 = recall_at_k(ranked, relevant, 20)

        all_ndcg5.append(ndcg5)
        all_ndcg10.append(ndcg10)
        all_mrr10.append(mrr10)
        all_p5.append(p5)
        all_r20.append(r20)

        per_case.append({
            "case_id": case_id,
            "n_relevant": len(relevant),
            "ndcg5": ndcg5,
            "ndcg10": ndcg10,
            "mrr10": mrr10,
            "p5": p5,
            "r20": r20,
        })

    n = len(all_ndcg5)
    return {
        "policy": policy_name,
        "n_cases": n,
        "ndcg5": sum(all_ndcg5) / n if n else 0,
        "ndcg10": sum(all_ndcg10) / n if n else 0,
        "mrr10": sum(all_mrr10) / n if n else 0,
        "p5": sum(all_p5) / n if n else 0,
        "r20": sum(all_r20) / n if n else 0,
        "per_case": per_case,
    }


def main() -> int:
    cases = frozen_v2_cases()
    snapshot = load_snapshot()

    print(f"P1D.4: TEI ranking evaluation")
    print(f"  model: {snapshot['embedding_profile']['model']}")
    print(f"  dimension: {snapshot['embedding_profile']['dimension']}")
    print(f"  cases: {len(cases)}")
    print(f"  queries in snapshot: {len(snapshot['queries'])}")
    print(f"  candidates in snapshot: {len(snapshot['candidates'])}")
    print()

    results = {}
    for policy in ["lexical", "semantic_only", "hybrid_rrf"]:
        r = evaluate_policy(cases, snapshot, None, policy)
        results[policy] = r
        print(f"{policy:20s}  n={r['n_cases']:2d}  "
              f"nDCG@5={r['ndcg5']:.4f}  nDCG@10={r['ndcg10']:.4f}  "
              f"MRR@10={r['mrr10']:.4f}  P@5={r['p5']:.4f}  R@20={r['r20']:.4f}")

    # Save full results
    output_path = REPO_ROOT / "docs" / "p1b_snapshot" / "results_tei_gte_large_en_v15.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results saved to {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
