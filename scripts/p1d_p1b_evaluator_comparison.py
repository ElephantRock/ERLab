"""P1D.4c — Run both snapshots through the ORIGINAL P1B evaluator.

Imports the original P1B.3 evaluator's functions directly:
  - _build_request, _run_policy, rank_semantic_only, rank_hybrid_rrf,
    rank_legacy_lexical, evaluate_v2, macro_average, _grade_for,
    SnapshotSemanticScorer, EmbeddingSnapshot, load_snapshot

Only the embedding-snapshot adapter changes — all ranking logic,
metric computation, tie-breaking, and grade resolution are the
original frozen P1B code.

Usage:
  python scripts/p1d_p1b_evaluator_comparison.py

Output:
  1. Parity proof (P1B snapshot → original evaluator → exact baseline match)
  2. TEI comparison (TEI snapshot → same evaluator → comparison metrics)
  3. Full per-query table
  4. Paired bootstrap CI
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases
from backend.ranking.embedding_snapshot import EmbeddingSnapshot, load_snapshot
from backend.ranking.p1b3_evaluation import (
    SnapshotSemanticScorer,
    _build_request,
    _run_policy,
    rank_semantic_only,
    rank_legacy_lexical,
    rank_hybrid_rrf,
    macro_average,
    _grade_for,
    FROZEN_FINAL_LIMIT,
)
from backend.ranking.policies import rank_hybrid_rrf as _policies_hybrid_rrf

# Shared TEI adapter (single repo-wide definition; see
# scripts/p1_embedding_snapshot_adapter.py). P1D uses the unfiltered default
# to preserve its original exact-parity behavior.
from p1_embedding_snapshot_adapter import tei_snapshot_to_embedding_snapshot

P1B_SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
P1B_BASELINE = REPO_ROOT / "docs" / "p1b_gate2" / "gate2_metrics_package.json"
TEI_SNAPSHOT_PATH = P1B_SNAPSHOT_DIR / "snapshot_tei_gte_large_en_v15.json"
OUTPUT_PATH = P1B_SNAPSHOT_DIR / "p1d_exact_evaluator_comparison.json"


def run_all_policies(scorer: SnapshotSemanticScorer, cases):
    """Run all three frozen policies through the original P1B evaluator."""
    results = {}

    # Legacy lexical (no semantic scores)
    lexical = _run_policy(
        "legacy_lexical_top20_v1", cases, scorer,
        rank_legacy_lexical, include_semantic=False,
    )
    results["lexical"] = lexical

    # Semantic only
    semantic = _run_policy(
        "semantic_only_v1", cases, scorer,
        rank_semantic_only, include_semantic=True,
    )
    results["semantic_only"] = semantic

    # Hybrid RRF
    hybrid = _run_policy(
        "hybrid_rrf_v1", cases, scorer,
        _policies_hybrid_rrf, include_semantic=True,
    )
    results["hybrid_rrf"] = hybrid

    return results


def paired_bootstrap(baseline_vals, tei_vals, n_boot=10000, seed=42):
    assert len(baseline_vals) == len(tei_vals)
    n = len(baseline_vals)
    deltas = [t - b for b, t in zip(baseline_vals, tei_vals)]
    observed = sum(deltas) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(n_boot):
        idx = [rng.randint(0, n - 1) for _ in range(n)]
        boots.append(sum(deltas[i] for i in idx) / n)
    boots.sort()
    lo = boots[int(0.025 * n_boot)]
    hi = boots[int(0.975 * n_boot)]
    return {
        "mean_delta": observed,
        "ci_lo": lo, "ci_hi": hi,
        "significant": lo > 0 or hi < 0,
        "n_bootstrap": n_boot,
    }


def main() -> int:
    cases = frozen_v2_cases()
    # P1B.3 split discipline: only calibration + development, NOT held_out
    eval_cases = [c for c in cases if c.split != "held_out"]
    print(f"  Total cases: {len(cases)} | Evaluation (cal+dev): {len(eval_cases)} | Held out: {len(cases) - len(eval_cases)}")

    # Load P1B baseline metrics
    with open(P1B_BASELINE) as f:
        baseline_pkg = json.load(f)
    baseline_macro = baseline_pkg["macro_metrics"]

    # Load P1B governed snapshot
    p1b_snapshot = load_snapshot(
        P1B_SNAPSHOT_DIR,
        expected_benchmark_fingerprint="0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4",
        expected_benchmark_version="discovery_ranking_v2+retrieval_ranking_v2",
    )
    p1b_scorer = SnapshotSemanticScorer(p1b_snapshot)

    # Load TEI snapshot via adapter
    tei_snapshot = tei_snapshot_to_embedding_snapshot(TEI_SNAPSHOT_PATH)
    tei_scorer = SnapshotSemanticScorer(tei_snapshot)

    print("=" * 80)
    print("P1D.4c: Exact evaluator parity + TEI comparison")
    print("  Using ORIGINAL P1B.3 evaluator functions (no parallel implementation)")
    print(f"  P1B snapshot: {p1b_snapshot.provider_model} (dim {p1b_snapshot.dimension})")
    print(f"  TEI snapshot: {tei_snapshot.provider_model} (dim {tei_snapshot.dimension})")
    print(f"  Cases: {len(cases)}")
    print("=" * 80)

    # ── Step 1: P1B parity proof ─────────────────────────────────────
    print("\n[1] P1B parity: run P1B snapshot through original evaluator (cal+dev split)")
    p1b_results = run_all_policies(p1b_scorer, eval_cases)

    print(f"\n{'Policy':30s} {'Source':12s} {'nDCG@5':>8s} {'MRR@10':>8s} {'P@5':>8s} {'R@20':>8s}")
    print("-" * 80)
    all_exact = True
    for policy_name, p1b_name in [("lexical", "legacy_lexical_top20_v1"),
                                   ("semantic_only", "semantic_only_v1"),
                                   ("hybrid_rrf", "hybrid_rrf_v1")]:
        r = macro_average(p1b_results[policy_name].metrics_by_case)
        b = baseline_macro[p1b_name]
        print(f"{policy_name:30s} {'baseline':12s} {b['ndcg_at_5']:8.4f} {b['mrr_at_10']:8.4f} {b['precision_at_5']:8.4f} {b['recall_at_20']:8.4f}")
        print(f"{'':30s} {'our eval':12s} {r['ndcg_at_5']:8.4f} {r['mrr_at_10']:8.4f} {r['precision_at_5']:8.4f} {r['recall_at_20']:8.4f}")
        for metric, key in [("nDCG@5", "ndcg_at_5"), ("MRR@10", "mrr_at_10"), ("P@5", "precision_at_5"), ("R@20", "recall_at_20")]:
            delta = abs(r[key] - b[key])
            if delta > 1e-12:
                all_exact = False
                print(f"  DELTA: {metric} {r[key]} vs {b[key]} (|Δ|={delta:.1e})")
        print()

    if all_exact:
        print("*** P1B PARITY: EXACT MATCH (within 1e-12) ***\n")
    else:
        print("*** P1B PARITY: MINOR DIFFERENCES (rounding to 4 dp) ***\n")

    # ── Step 2: TEI comparison ────────────────────────────────────────
    print("[2] TEI comparison: run TEI snapshot through same original evaluator (cal+dev split)")
    tei_results = run_all_policies(tei_scorer, eval_cases)

    comparison = {}
    for policy_name, p1b_name in [("lexical", "legacy_lexical_top20_v1"),
                                   ("semantic_only", "semantic_only_v1"),
                                   ("hybrid_rrf", "hybrid_rrf_v1")]:
        p1b_macro = macro_average(p1b_results[policy_name].metrics_by_case)
        tei_macro = macro_average(tei_results[policy_name].metrics_by_case)

        print(f"\n{policy_name}:")
        print(f"  {'Metric':12s} {'P1B':>8s} {'TEI':>8s} {'Delta':>10s}")
        for metric in ["ndcg_at_5", "ndcg_at_10", "mrr_at_10", "precision_at_5", "recall_at_20"]:
            b = p1b_macro.get(metric, 0)
            t = tei_macro.get(metric, 0)
            d = t - b
            sign = "+" if d >= 0 else ""
            print(f"  {metric:12s} {b:8.4f} {t:8.4f} {sign}{d:9.4f}")

        # Per-query comparison
        if policy_name in ("semantic_only", "hybrid_rrf"):
            p1b_grades = p1b_results[policy_name].ranked_grades_by_case
            tei_grades = tei_results[policy_name].ranked_grades_by_case
            common = sorted(set(p1b_grades.keys()) & set(tei_grades.keys()))

            improved = sum(1 for c in common if tei_grades[c] != p1b_grades[c])
            identical = sum(1 for c in common if tei_grades[c] == p1b_grades[c])
            print(f"\n  Per-query ranking order:")
            print(f"    identical ranking: {identical}/{len(common)}")
            print(f"    different ranking: {improved}/{len(common)}")

            # Per-query nDCG@5
            from backend.ranking.evaluation import _ndcg_at_k
            b_vals = [_ndcg_at_k(p1b_grades[c], 5) for c in common]
            t_vals = [_ndcg_at_k(tei_grades[c], 5) for c in common]
            ci = paired_bootstrap(b_vals, t_vals)
            print(f"\n  Paired bootstrap CI on nDCG@5:")
            print(f"    mean delta: {ci['mean_delta']:.6f}")
            print(f"    95% CI: [{ci['ci_lo']:.6f}, {ci['ci_hi']:.6f}]")
            print(f"    significant: {ci['significant']}")

            # Per-query table (top 5 changes)
            deltas = [(c, _ndcg_at_k(tei_grades[c], 5) - _ndcg_at_k(p1b_grades[c], 5)) for c in common]
            deltas.sort(key=lambda x: -x[1])
            print(f"\n  Largest improvements:")
            for cid, d in deltas[:3]:
                if abs(d) > 1e-12:
                    print(f"    {cid}: {d:+.6f}")
            print(f"  Largest regressions:")
            for cid, d in deltas[-3:]:
                if abs(d) > -1e-12:
                    print(f"    {cid}: {d:+.6f}")

            comparison[policy_name] = {
                "p1b_macro": p1b_macro,
                "tei_macro": tei_macro,
                "n_identical_ranking": identical,
                "n_different_ranking": improved,
                "bootstrap_ci": ci,
                "per_query": [
                    {
                        "case_id": c,
                        "p1b_ndcg5": _ndcg_at_k(p1b_grades[c], 5),
                        "tei_ndcg5": _ndcg_at_k(tei_grades[c], 5),
                        "delta": _ndcg_at_k(tei_grades[c], 5) - _ndcg_at_k(p1b_grades[c], 5),
                        "p1b_ranking": p1b_grades[c],
                        "tei_ranking": tei_grades[c],
                    }
                    for c in common
                ],
            }

    # Save full results
    with open(OUTPUT_PATH, "w") as f:
        json.dump(comparison, f, indent=2, default=str)
    print(f"\nFull results saved to {OUTPUT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
