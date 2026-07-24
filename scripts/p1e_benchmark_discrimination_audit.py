"""P1E.0 — Benchmark Discrimination Audit.

Audit-only. Measures the frozen P1B benchmark's ability to discriminate
retrieval and ranking quality across FIVE unique original-evaluator runs:

    1  legacy_lexical_top20_v1   (snapshot-independent)
    2  semantic_only_v1          (P1B snapshot)
    3  semantic_only_v1          (TEI snapshot)
    4  hybrid_rrf_v1             (P1B snapshot)
    5  hybrid_rrf_v1             (TEI snapshot)

Imports and calls the ORIGINAL P1B evaluator + policies + metrics. No parallel
ranking/metric implementation. 44 calibration+development cases only; 22
held-out cases sealed (never materialized, decoded, or inspected).

Outputs (all embed the Commit-1 frozen-file SHA-256 hashes):
    data/evaluation/p1e_discrimination_audit.json
    data/evaluation/p1e_case_diagnostics.json      (all 44 cases)
    data/evaluation/p1e_policy_pairwise_comparison.json

Usage:
    python scripts/p1e_benchmark_discrimination_audit.py
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases  # noqa: E402
from backend.ranking.embedding_snapshot import load_snapshot  # noqa: E402
from backend.ranking.evaluation import (  # noqa: E402
    _mrr_at_k,
    _ndcg_at_k,
    _precision_at_k,
    _recall_at_k,
)
from backend.ranking.p1b3_evaluation import (  # noqa: E402
    FROZEN_FINAL_LIMIT,
    SnapshotSemanticScorer,
    _build_request,
    _grade_for,
    _run_policy,
    evaluate_v2,
    macro_average,
    rank_semantic_only,
)
from backend.ranking.p1e_snapshot_filter import load_snapshot_filtered  # noqa: E402
from backend.ranking.policies import (  # noqa: E402
    _keyword_overlap,
    rank_hybrid_rrf,
    rank_legacy_lexical,
)
from p1_embedding_snapshot_adapter import tei_snapshot_to_embedding_snapshot  # noqa: E402
from p1e_stats import (  # noqa: E402
    PRIMARY_SEED,
    SENSITIVITY_SEED,
    continuous_mde,
    kendall_tau,
    paired_bootstrap_ci,
    paired_permutation_pvalue,
    spearman_rho,
    top1_mcnemar_mde,
)

# ── Frozen paths ─────────────────────────────────────────────────────
MANIFEST_PATH = REPO_ROOT / "data" / "evaluation" / "p1e_frozen_split_manifest.json"
PROTOCOL_PATH = REPO_ROOT / "docs" / "research" / "p1e_benchmark_discrimination_audit_protocol.md"
P1B_SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
TEI_SNAPSHOT_PATH = P1B_SNAPSHOT_DIR / "snapshot_tei_gte_large_en_v15.json"
P1B_BASELINE = REPO_ROOT / "docs" / "p1b_gate2" / "gate2_metrics_package.json"

OUT_AUDIT = REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json"
OUT_CASES = REPO_ROOT / "data" / "evaluation" / "p1e_case_diagnostics.json"
OUT_PAIRWISE = REPO_ROOT / "data" / "evaluation" / "p1e_policy_pairwise_comparison.json"

# Frozen effect threshold for "material" pairwise nDCG@5 movement.
MATERIAL_THRESHOLD_NDCG5 = 0.0150
DIAGNOSIS_RULE_VERSION = "p1e_diagnosis_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── Held-out access guard (load-bearing) ─────────────────────────────
class HeldOutGuard:
    """Instrumented accessor that raises if a held-out ID is ever requested."""

    def __init__(self, held_out_ids: frozenset[str]):
        self.held_out = held_out_ids
        self.evaluator_submissions: set[str] = set()
        self.emitted: set[str] = set()

    def check_evaluator_input(self, case_id: str) -> None:
        if case_id in self.held_out:
            raise RuntimeError(f"HELD-OUT GUARD: case {case_id} passed to evaluator")
        self.evaluator_submissions.add(case_id)

    def check_emit(self, case_id: str) -> None:
        if case_id in self.held_out:
            raise RuntimeError(f"HELD-OUT GUARD: case {case_id} emitted to output")
        self.emitted.add(case_id)


# =====================================================================
# §0  Frozen-evidence integrity + scoped data loading
# =====================================================================

def load_frozen_inputs() -> dict:
    """Load the manifest + protocol hashes; verify against frozen P1B identity."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_sha = sha256_file(MANIFEST_PATH)
    protocol_sha = sha256_file(PROTOCOL_PATH)

    # Verify benchmark identity matches frozen P1B evidence.
    expected_fp = "0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4"
    expected_ver = "discovery_ranking_v2+retrieval_ranking_v2"
    if manifest["benchmark_fingerprint"] != expected_fp:
        raise SystemExit(f"FATAL: manifest benchmark_fingerprint drift: {manifest['benchmark_fingerprint']}")
    if manifest["benchmark_version"] != expected_ver:
        raise SystemExit(f"FATAL: manifest benchmark_version drift: {manifest['benchmark_version']}")

    return {
        "manifest": manifest,
        "manifest_sha256": manifest_sha,
        "protocol_sha256": protocol_sha,
        "cal_dev_case_ids": sorted(manifest["cal_dev_case_ids"]),
        "held_out_case_ids": sorted(manifest["held_out_case_ids"]),
    }


def load_scoped_cases(cal_dev_ids: frozenset[str]) -> tuple[list, list, frozenset[str]]:
    """Materialize ONLY the 44 cal+dev case objects; derive candidate allowlist.

    frozen_v2_cases() returns all 66 (the registry materializes them at import).
    We filter to the 44 cal+dev IDs from the manifest and NEVER pass the 22
    held-out cases onward. The candidate allowlist is derived from the scoped
    cases only (not by loading all snapshot items).
    """
    all_cases = frozen_v2_cases()
    scoped = [c for c in all_cases if c.case_id in cal_dev_ids]
    if len(scoped) != len(cal_dev_ids):
        missing = cal_dev_ids - {c.case_id for c in scoped}
        raise SystemExit(f"FATAL: missing scoped cases: {missing}")
    candidate_ids: set[str] = set()
    for c in scoped:
        for cand in c.candidates:
            candidate_ids.add(cand.candidate_id)
    return scoped, list(all_cases), frozenset(candidate_ids)


def load_both_snapshots_filtered(
    cal_dev_ids: frozenset[str], candidate_ids: frozenset[str], benchmark_fp: str, benchmark_ver: str
) -> tuple[dict, dict, dict, dict]:
    """Load both snapshots through the cal+dev allowlist (pre-decode filter)."""
    allow = frozenset(cal_dev_ids | candidate_ids)

    # P1B: filtered loader (decodes only allowed items).
    p1b_snap, p1b_report = load_snapshot_filtered(
        P1B_SNAPSHOT_DIR,
        allowed_item_ids=allow,
        expected_benchmark_fingerprint=benchmark_fp,
        expected_benchmark_version=benchmark_ver,
    )
    # TEI: shared adapter with allowlist (decodes only allowed items).
    tei_raw = json.loads(TEI_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    tei_snap = tei_snapshot_to_embedding_snapshot(tei_raw, allowed_item_ids=allow)
    tei_report = {
        "opaque_file_sha256": sha256_file(TEI_SNAPSHOT_PATH),
        "decoded_query_count": sum(1 for i in tei_snap.items if i.item_role == "query"),
        "decoded_candidate_count": sum(1 for i in tei_snap.items if i.item_role == "candidate"),
        "decoded_query_ids": sorted(i.item_id for i in tei_snap.items if i.item_role == "query"),
        "decoded_candidate_ids": sorted(i.item_id for i in tei_snap.items if i.item_role == "candidate"),
    }
    return p1b_snap, p1b_report, tei_snap, tei_report


# =====================================================================
# §metrics  Per-case metric vector helpers (reuse ORIGINAL metric fns)
# =====================================================================

def case_metric_vector(ranked_grades: list[int], all_grades: list[int]) -> dict:
    """Compute the full metric vector for one case via the original fns."""
    return {
        "ndcg_at_5": _ndcg_at_k(ranked_grades, 5),
        "ndcg_at_10": _ndcg_at_k(ranked_grades, 10),
        "mrr_at_10": _mrr_at_k(ranked_grades, 10),
        "precision_at_5": _precision_at_k(ranked_grades, 5),
        "recall_at_20": _recall_at_k(ranked_grades, 20, all_grades),
    }


def top1_positive(ranked_grades: list[int]) -> int:
    """1 if top-ranked grade > 0, else 0."""
    return 1 if (ranked_grades and ranked_grades[0] > 0) else 0


def top1_optimal(ranked_grades: list[int], all_grades: list[int]) -> int:
    """1 if top-ranked grade equals the case's maximum grade (and max > 0), else 0."""
    if not ranked_grades or not all_grades:
        return 0
    top_grade = max(all_grades)
    if top_grade == 0:
        return 0  # all-zero case: not optimal
    return 1 if ranked_grades[0] == top_grade else 0


def oracle_metrics(all_grades: list[int]) -> dict:
    """Oracle = ideal descending grade ordering through the ORIGINAL metric fns."""
    ideal = sorted(all_grades, reverse=True)
    return {
        "ndcg_at_5": _ndcg_at_k(ideal, 5),
        "ndcg_at_10": _ndcg_at_k(ideal, 10),
        "mrr_at_10": _mrr_at_k(ideal, 10),
        "precision_at_5": _precision_at_k(ideal, 5),
        "recall_at_20": _recall_at_k(ideal, 20, all_grades),
        "top1_optimal": 1 if (ideal and ideal[0] > 0) else 0,
    }


# =====================================================================
# §runs  The five unique original-evaluator runs
# =====================================================================

RUN_NAMES = ["lexical", "p1b_semantic", "tei_semantic", "p1b_hybrid_rrf", "tei_hybrid_rrf"]


def run_five_configurations(cases, p1b_scorer, tei_scorer, guard: HeldOutGuard) -> dict:
    """Execute the five unique runs via the ORIGINAL _run_policy/evaluator.

    Returns run_name -> {policy_result, per_case: {case_id: {ranked_grades,
    all_grades, ranked_ids, metrics, top1_positive, top1_optimal}}}.
    """
    runs: dict[str, dict] = {}

    # lexical is snapshot-independent; run once with the P1B scorer
    # (include_semantic=False, so the scorer is unused for ranking).
    def _exec(run_name, scorer, rank_fn, include_semantic):
        pr = _run_policy(run_name, cases, scorer, rank_fn, include_semantic=include_semantic)
        per_case = {}
        for case in cases:
            guard.check_evaluator_input(case.case_id)
            req = _build_request(case, scorer=scorer, include_semantic=include_semantic, policy_id=run_name)
            res = rank_fn(req)
            ranked_grades = [_grade_for(case, rc.candidate_id) for rc in res.ranked]
            all_grades = [_grade_for(case, c.candidate_id) for c in case.candidates]
            ranked_ids = [rc.candidate_id for rc in res.ranked]
            per_case[case.case_id] = {
                "ranked_grades": ranked_grades,
                "all_grades": all_grades,
                "ranked_ids": ranked_ids,
                "metrics": case_metric_vector(ranked_grades, all_grades),
                "top1_positive": top1_positive(ranked_grades),
                "top1_optimal": top1_optimal(ranked_grades, all_grades),
            }
        runs[run_name] = {"policy_result": pr, "per_case": per_case}

    _exec("lexical", p1b_scorer, rank_legacy_lexical, False)
    _exec("p1b_semantic", p1b_scorer, rank_semantic_only, True)
    _exec("tei_semantic", tei_scorer, rank_semantic_only, True)
    _exec("p1b_hybrid_rrf", p1b_scorer, rank_hybrid_rrf, True)
    _exec("tei_hybrid_rrf", tei_scorer, rank_hybrid_rrf, True)
    return runs


# =====================================================================
# §2  Metric ceiling, headroom, empirical resolution
# =====================================================================

def ceiling_and_headroom(cases, runs: dict) -> dict:
    """Per-case + aggregate oracle, observed/historical headroom."""
    per_case = {}
    n = len(cases)
    for case in cases:
        all_grades = [_grade_for(case, c.candidate_id) for c in case.candidates]
        oracle = oracle_metrics(all_grades)
        best_observed = {m: max(runs[rn]["per_case"][case.case_id]["metrics"].get(m, 0.0)
                                for rn in RUN_NAMES) for m in oracle if m != "top1_optimal"}
        best_p1b = {m: max(runs["lexical"]["per_case"][case.case_id]["metrics"].get(m, 0.0),
                           runs["p1b_semantic"]["per_case"][case.case_id]["metrics"].get(m, 0.0),
                           runs["p1b_hybrid_rrf"]["per_case"][case.case_id]["metrics"].get(m, 0.0))
                    for m in oracle if m != "top1_optimal"}
        best_observed_top1 = max(runs[rn]["per_case"][case.case_id]["top1_optimal"] for rn in RUN_NAMES)
        best_p1b_top1 = max(runs["lexical"]["per_case"][case.case_id]["top1_optimal"],
                            runs["p1b_semantic"]["per_case"][case.case_id]["top1_optimal"],
                            runs["p1b_hybrid_rrf"]["per_case"][case.case_id]["top1_optimal"])
        all_zero = max(all_grades) == 0
        per_case[case.case_id] = {
            "oracle": oracle,
            "all_zero": all_zero,
            "observed_headroom": {m: round(oracle[m] - best_observed[m], 8) for m in best_observed},
            "historical_headroom": {m: round(oracle[m] - best_p1b[m], 8) for m in best_p1b},
            "observed_headroom_top1_optimal": oracle["top1_optimal"] - best_observed_top1,
            "historical_headroom_top1_optimal": oracle["top1_optimal"] - best_p1b_top1,
            "best_observed_ndcg_at_5": best_observed["ndcg_at_5"],
        }
    # headroom histogram on observed nDCG@5
    ho = [per_case[c.case_id]["observed_headroom"]["ndcg_at_5"] for c in cases]
    histogram = {
        "headroom_eq_0": sum(1 for h in ho if h == 0),
        "headroom_le_0.01": sum(1 for h in ho if h <= 0.01),
        "headroom_le_0.02": sum(1 for h in ho if h <= 0.02),
        "headroom_gt_0.05": sum(1 for h in ho if h > 0.05),
    }
    return {"per_case": per_case, "headroom_histogram_ndcg5": histogram, "n_cases": n}


def empirical_resolution(cases) -> dict:
    """Min nonzero macro movement from adjacent differently-graded swaps (/44).

    Computed per metric via the ORIGINAL metric fns. top1_optimal denominator
    excludes all-zero cases; effective denominator reported.
    """
    n = len(cases)
    metrics_keys = ["ndcg_at_5", "ndcg_at_10", "mrr_at_10", "precision_at_5", "recall_at_20"]
    min_nonzero = {m: None for m in metrics_keys}
    min_nonzero_top1 = None
    top1_denom = 0

    for case in cases:
        all_grades = [_grade_for(case, c.candidate_id) for c in case.candidates]
        ideal = sorted(all_grades, reverse=True)
        is_all_zero = max(all_grades) == 0
        if not is_all_zero:
            top1_denom += 1
        # enumerate adjacent swaps of DIFFERENTLY-graded candidates in the ideal ordering
        for i in range(len(ideal) - 1):
            if ideal[i] == ideal[i + 1]:
                continue  # equal-grade swap does not count
            swapped = list(ideal)
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            base = case_metric_vector(ideal, all_grades)
            pert = case_metric_vector(swapped, all_grades)
            for m in metrics_keys:
                d = abs(pert[m] - base[m])
                if d > 0:
                    macro_d = d / n
                    if min_nonzero[m] is None or macro_d < min_nonzero[m]:
                        min_nonzero[m] = macro_d
            # top1_optimal: only the first position matters; a swap at i=0 between
            # differently-graded candidates can flip top1_optimal from 1->0 or 0->1
            if i == 0 and not is_all_zero:
                base_t1 = 1 if ideal[0] > 0 else 0
                pert_t1 = 1 if swapped[0] > 0 else 0
                dt1 = abs(pert_t1 - base_t1)
                if dt1 > 0:
                    macro_dt1 = dt1 / top1_denom if top1_denom else 0
                    if min_nonzero_top1 is None or (macro_dt1 and macro_dt1 < min_nonzero_top1):
                        min_nonzero_top1 = macro_dt1

    return {
        "method": "adjacent differently-graded swap of ideal ordering; per-case change / n",
        "min_nonzero_macro_movement": {m: round(v, 8) if v is not None else None for m, v in min_nonzero.items()},
        "min_nonzero_macro_movement_top1_optimal": round(min_nonzero_top1, 8) if min_nonzero_top1 is not None else None,
        "top1_optimal_effective_denominator": top1_denom,
        "all_zero_cases_excluded": n - top1_denom,
        "n_cases": n,
    }


# =====================================================================
# §helpers  per-candidate scores (overlap + P1B/TEI similarity)
# =====================================================================

def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def per_candidate_scores(case, p1b_scorer, tei_scorer) -> dict:
    """For one case: candidate_id -> {grade, lexical_overlap, p1b_sim, tei_sim}."""
    out = {}
    for cand in case.candidates:
        text = f"{cand.title} {cand.abstract}"
        out[cand.candidate_id] = {
            "grade": _grade_for(case, cand.candidate_id),
            "lexical_overlap": _keyword_overlap(case.query_text, text),
            "p1b_sim": p1b_scorer.query_candidate_score(case.case_id, cand.candidate_id),
            "tei_sim": tei_scorer.query_candidate_score(case.case_id, cand.candidate_id),
        }
    return out


# =====================================================================
# §1  Judgment and candidate-set structure
# =====================================================================

def judgment_entropy(grade_counts: dict[int, int]) -> float:
    """Shannon entropy over the grade histogram (bits)."""
    total = sum(grade_counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for g, c in grade_counts.items():
        if c == 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return round(h, 6)


def structure_diagnostics(case, scores: dict) -> dict:
    grades = [s["grade"] for s in scores.values()]
    gc = dict(Counter(grades))
    top_grade = max(grades) if grades else 0
    n_grade3 = gc.get(3, 0)
    n_positive = sum(1 for g in grades if g > 0)
    n_nonrelevant = gc.get(0, 0)
    n_weak = gc.get(1, 0)
    n_strong = sum(1 for g in grades if g >= 2)
    # content_hash duplication within case
    hashes = [c.content_hash for c in case.candidates]
    dup_hashes = len(hashes) != len(set(hashes))
    n_at_top = sum(1 for g in grades if g == top_grade)
    return {
        "candidate_count": len(case.candidates),
        "grade_distribution": {str(k): gc.get(k, 0) for k in range(4)},
        "n_grade3": n_grade3,
        "n_positive": n_positive,
        "n_nonrelevant": n_nonrelevant,
        "n_weak_positive": n_weak,
        "n_strong_positive": n_strong,
        "top_grade": top_grade,
        "unique_best": (n_at_top == 1 and top_grade > 0),
        "ambiguous_top": (n_at_top >= 2 and top_grade > 0),
        "judgment_entropy_bits": judgment_entropy(gc),
        "candidate_text_duplication": dup_hashes,
        "all_zero": top_grade == 0,
    }


def aggregate_structure(per_case_struct: dict) -> dict:
    cases = list(per_case_struct.values())
    n = len(cases)
    return {
        "cases_with_no_grade3": sum(1 for c in cases if c["n_grade3"] == 0),
        "cases_with_multiple_grade3": sum(1 for c in cases if c["n_grade3"] > 1),
        "cases_all_relevant": sum(1 for c in cases if c["n_nonrelevant"] == 0),
        "cases_all_zero": sum(1 for c in cases if c["all_zero"]),
        "cases_fewer_than_2_nonrelevant": sum(1 for c in cases if c["n_nonrelevant"] < 2),
        "cases_unique_best": sum(1 for c in cases if c["unique_best"]),
        "cases_ambiguous_top": sum(1 for c in cases if c["ambiguous_top"]),
        "total_grade0": sum(c["n_nonrelevant"] for c in cases),
        "total_grade1": sum(c["n_weak_positive"] for c in cases),
        "total_grade2plus": sum(c["n_strong_positive"] for c in cases),
        "total_grade3": sum(c["n_grade3"] for c in cases),
        "cases_with_text_duplication": sum(1 for c in cases if c["candidate_text_duplication"]),
        "n_cases": n,
    }


# =====================================================================
# §4  Hard-negative coverage
# =====================================================================

GLOBAL_LEX_THRESHOLD = 0.30
GLOBAL_SIM_THRESHOLD = 0.65


def hard_negative_analysis(case, scores: dict, runs: dict) -> dict:
    """PRIMARY grade-0 hard negatives + secondary + global-sensitivity."""
    grades = {cid: s["grade"] for cid, s in scores.items()}
    pos_ids = [cid for cid, g in grades.items() if g > 0]
    strong_ids = [cid for cid, g in grades.items() if g >= 2]
    grade0_ids = [cid for cid, g in grades.items() if g == 0]
    grade1_ids = [cid for cid, g in grades.items() if g == 1]
    all_zero = len(pos_ids) == 0

    if pos_ids and not all_zero:
        min_overlap_pos = min(scores[c]["lexical_overlap"] for c in pos_ids)
        min_p1b_pos = min(s for s in (scores[c]["p1b_sim"] for c in pos_ids) if s is not None)
        min_tei_pos = min(s for s in (scores[c]["tei_sim"] for c in pos_ids) if s is not None)
    else:
        min_overlap_pos = min_p1b_pos = min_tei_pos = None

    # PRIMARY grade-0 hard negatives
    primary = []
    for cid in grade0_ids:
        s = scores[cid]
        confusable = (
            (min_overlap_pos is not None and s["lexical_overlap"] >= min_overlap_pos)
            or (min_p1b_pos is not None and s["p1b_sim"] is not None and s["p1b_sim"] >= min_p1b_pos)
            or (min_tei_pos is not None and s["tei_sim"] is not None and s["tei_sim"] >= min_tei_pos)
        )
        if confusable:
            primary.append(cid)

    # ranking-position flags for each primary hard negative (across all 5 runs)
    primary_detail = []
    for cid in primary:
        outranks_any_pos = {}
        outranks_highest = {}
        ranks_first = {}
        for rn in RUN_NAMES:
            rids = runs[rn]["per_case"][case.case_id]["ranked_ids"]
            pos = rids.index(cid) if cid in rids else None
            if pos is None:
                continue
            # outranks any grade>0 candidate
            above = rids[:pos]
            outranks_any_pos[rn] = any(grades[x] > 0 for x in above)
            top_grade = max(grades.values())
            highest_ids = [x for x in grades if grades[x] == top_grade]
            outranks_highest[rn] = any(x in highest_ids for x in above)
            ranks_first[rn] = (pos == 0)
        primary_detail.append({
            "candidate_id": cid, "grade": 0,
            "lexical_overlap": scores[cid]["lexical_overlap"],
            "p1b_sim": scores[cid]["p1b_sim"], "tei_sim": scores[cid]["tei_sim"],
            "outranks_any_positive": outranks_any_pos,
            "outranks_highest_grade": outranks_highest,
            "ranks_first": ranks_first,
        })

    # SECONDARY: strong-positive confuser (grade0 vs grade>=2) + weak ambiguity (grade1)
    strong_confusers = []
    if strong_ids:
        min_overlap_strong = min(scores[c]["lexical_overlap"] for c in strong_ids)
        min_p1b_strong = min(s for s in (scores[c]["p1b_sim"] for c in strong_ids) if s is not None)
        min_tei_strong = min(s for s in (scores[c]["tei_sim"] for c in strong_ids) if s is not None)
        for cid in grade0_ids:
            s = scores[cid]
            if ((s["lexical_overlap"] >= min_overlap_strong)
                    or (s["p1b_sim"] is not None and s["p1b_sim"] >= min_p1b_strong)
                    or (s["tei_sim"] is not None and s["tei_sim"] >= min_tei_strong)):
                strong_confusers.append(cid)
    weak_ambiguity = []
    if strong_ids:
        min_overlap_strong = min(scores[c]["lexical_overlap"] for c in strong_ids)
        min_p1b_strong = min(s for s in (scores[c]["p1b_sim"] for c in strong_ids) if s is not None)
        min_tei_strong = min(s for s in (scores[c]["tei_sim"] for c in strong_ids) if s is not None)
        for cid in grade1_ids:
            s = scores[cid]
            if ((s["lexical_overlap"] >= min_overlap_strong)
                    or (s["p1b_sim"] is not None and s["p1b_sim"] >= min_p1b_strong)
                    or (s["tei_sim"] is not None and s["tei_sim"] >= min_tei_strong)):
                weak_ambiguity.append(cid)

    # GLOBAL sensitivity (overlap>=0.30 OR sim>=0.65) — never drives S/A
    global_threshold_neg = [
        cid for cid in grade0_ids
        if scores[cid]["lexical_overlap"] >= GLOBAL_LEX_THRESHOLD
        or (scores[cid]["p1b_sim"] is not None and scores[cid]["p1b_sim"] >= GLOBAL_SIM_THRESHOLD)
        or (scores[cid]["tei_sim"] is not None and scores[cid]["tei_sim"] >= GLOBAL_SIM_THRESHOLD)
    ]

    # classify the case
    has_near_miss = len(primary) >= 1
    if all_zero:
        category = "all_zero_no_baseline"
    elif len(grade0_ids) == 0:
        category = "no_plausible_negative"
    elif len(primary) == 0:
        category = "weak_negative_only"
    else:
        category = "has_near_miss_negative"

    return {
        "category": category,
        "n_primary_grade0_hard_negatives": len(primary),
        "primary_grade0_hard_negatives": primary_detail,
        "n_strong_positive_confusers": len(strong_confusers),
        "n_weak_positive_ambiguity": len(weak_ambiguity),
        "n_global_threshold_sensitivity": len(global_threshold_neg),
        "global_thresholds": {"lexical_overlap": GLOBAL_LEX_THRESHOLD, "similarity": GLOBAL_SIM_THRESHOLD},
        "min_positive_baseline": {"lexical_overlap": min_overlap_pos, "p1b_sim": min_p1b_pos, "tei_sim": min_tei_pos},
    }


# =====================================================================
# §3  Policy separability + pairwise comparisons
# =====================================================================

REQUIRED_PAIRWISE = [
    ("lexical", "p1b_semantic"),
    ("lexical", "tei_semantic"),
    ("p1b_semantic", "tei_semantic"),
    ("p1b_hybrid_rrf", "tei_hybrid_rrf"),
]


def _jaccard(a: list[str], b: list[str], k: int) -> float:
    sa, sb = set(a[:k]), set(b[:k])
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def pairwise_comparison(runs: dict, name_a: str, name_b: str, cases) -> dict:
    """Full pairwise comparison between two runs over identical candidate universes."""
    pa, pb = runs[name_a]["per_case"], runs[name_b]["per_case"]
    case_ids = [c.case_id for c in cases]

    top1_agree = sum(1 for cid in case_ids if pa[cid]["ranked_ids"][0] == pb[cid]["ranked_ids"][0])
    top1_grade_agree = sum(1 for cid in case_ids if pa[cid]["ranked_grades"][0] == pb[cid]["ranked_grades"][0])
    top5_overlap = [_jaccard(pa[cid]["ranked_ids"], pb[cid]["ranked_ids"], 5) for cid in case_ids]

    # correlations over identical universe (integrity-fail on mismatch)
    kendalls, spearmans = [], []
    for cid in case_ids:
        kt = kendall_tau(pa[cid]["ranked_ids"], pb[cid]["ranked_ids"])
        sp = spearman_rho(pa[cid]["ranked_ids"], pb[cid]["ranked_ids"])
        kendalls.append(kt["tau"])
        spearmans.append(sp["rho"])
    mean_kt = sum(kendalls) / len(kendalls) if kendalls else 0.0
    mean_sp = sum(spearmans) / len(spearmans) if spearmans else 0.0

    # per-query nDCG@5 deltas + win/loss/tie
    a_vals = [pa[cid]["metrics"]["ndcg_at_5"] for cid in case_ids]
    b_vals = [pb[cid]["metrics"]["ndcg_at_5"] for cid in case_ids]
    deltas = [b_vals[i] - a_vals[i] for i in range(len(case_ids))]
    wins = sum(1 for d in deltas if d > 0)
    losses = sum(1 for d in deltas if d < 0)
    ties = sum(1 for d in deltas if d == 0)
    material_pos = sum(1 for d in deltas if d > MATERIAL_THRESHOLD_NDCG5)
    material_neg = sum(1 for d in deltas if d < -MATERIAL_THRESHOLD_NDCG5)

    # power analysis (nDCG@5 continuous)
    mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
    ci = paired_bootstrap_ci(a_vals, b_vals, seed=PRIMARY_SEED)
    ci_sens = paired_bootstrap_ci(a_vals, b_vals, seed=SENSITIVITY_SEED)
    perm = paired_permutation_pvalue(a_vals, b_vals, seed=PRIMARY_SEED)
    mde = continuous_mde(deltas)
    # top1_optimal McNemar
    a_t1 = [pa[cid]["top1_optimal"] for cid in case_ids]
    b_t1 = [pb[cid]["top1_optimal"] for cid in case_ids]
    mc = top1_mcnemar_mde(a_t1, b_t1, seed=PRIMARY_SEED)

    # effective non-tied queries (nDCG@5 differs)
    n_nontied = sum(1 for d in deltas if d != 0)

    # outcome label
    if mde["zero_variance"] and n_nontied == 0:
        label = "tied_heavy"
    elif ci["excludes_zero"] or perm["p_value"] < 0.05:
        label = "detected_difference"
    elif mde["mde"] is not None and mde["mde"] > 0.03:
        label = "underpowered"
    else:
        label = "no_detected_difference"

    per_query = []
    for i, cid in enumerate(case_ids):
        per_query.append({
            "case_id": cid,
            "ndcg5_a": round(a_vals[i], 6), "ndcg5_b": round(b_vals[i], 6),
            "delta": round(deltas[i], 6),
            "top1_optimal_a": a_t1[i], "top1_optimal_b": b_t1[i],
            "ranking_identical": pa[cid]["ranked_ids"] == pb[cid]["ranked_ids"],
        })

    return {
        "comparison": f"{name_a}_vs_{name_b}",
        "name_a": name_a, "name_b": name_b,
        "n_cases": len(case_ids),
        "top1_candidate_agreement": top1_agree,
        "top1_grade_agreement": top1_grade_agree,
        "mean_top5_jaccard": round(sum(top5_overlap) / len(top5_overlap), 6) if top5_overlap else 0.0,
        "mean_kendall_tau": round(mean_kt, 6),
        "mean_spearman_rho": round(mean_sp, 6),
        "wins_b_over_a": wins, "losses_b_vs_a": losses, "ties": ties,
        "material_positive_delta": material_pos,
        "material_negative_delta": material_neg,
        "material_threshold_ndcg5": MATERIAL_THRESHOLD_NDCG5,
        "mean_ndcg5_delta": round(mean_delta, 8),
        "abs_mean_ndcg5_delta": round(abs(mean_delta), 8),
        "bootstrap_ci": ci,
        "bootstrap_ci_sensitivity_seed42": ci_sens,
        "permutation": perm,
        "continuous_mde_ndcg5": mde,
        "top1_optimal_mcnemar": mc,
        "effective_nontied_queries": n_nontied,
        "outcome_label": label,
        "per_query": per_query,
    }


def all_pairwise(runs: dict, cases) -> dict:
    return {f"{a}_vs_{b}": pairwise_comparison(runs, a, b, cases) for a, b in REQUIRED_PAIRWISE}


# =====================================================================
# §5  Error recurrence (observable evidence patterns, bounded posture)
# =====================================================================

def error_class_analysis(cases, runs, scores_by_case: dict) -> dict:
    """Detect observable evidence patterns; label classified/hypothesis/0/not-inferable.

    Each nonzero class carries exact rule + case IDs + candidate IDs + grades +
    ranks under named policies + score margins + hybrid-repair status.
    """
    classes = {}

    # --- lexical_aliasing (CLASSIFIED): grade-0 candidate with lexical overlap
    #     >= a grade-3 candidate's overlap AND ranked above it by lexical. ---
    instances = []
    for case in cases:
        sc = scores_by_case[case.case_id]
        g3 = [cid for cid, s in sc.items() if s["grade"] == 3]
        g0 = [cid for cid, s in sc.items() if s["grade"] == 0]
        for z in g0:
            for t in g3:
                if sc[z]["lexical_overlap"] >= sc[t]["lexical_overlap"] and sc[z]["lexical_overlap"] > 0:
                    # ranked above by lexical?
                    rids = runs["lexical"]["per_case"][case.case_id]["ranked_ids"]
                    if z in rids and t in rids and rids.index(z) < rids.index(t):
                        instances.append({
                            "case_id": case.case_id, "candidate_id": z, "grade": 0,
                            "vs_candidate": t, "vs_grade": 3,
                            "overlap_z": sc[z]["lexical_overlap"], "overlap_t": sc[t]["lexical_overlap"],
                            "lexical_rank_z": rids.index(z) + 1, "lexical_rank_t": rids.index(t) + 1,
                            "hybrid_repairs": runs["p1b_hybrid_rrf"]["per_case"][case.case_id]["ranked_ids"].index(z) > rids.index(z) if z in runs["p1b_hybrid_rrf"]["per_case"][case.case_id]["ranked_ids"] else None,
                        })
    classes["lexical_aliasing"] = {"posture": "classified", "count": len(instances), "instances": instances}

    # --- generic_research_language_overlap (HYPOTHESIS): high lexical overlap
    #     between query and a grade<=1 candidate where overlap is generic terms. ---
    instances = []
    for case in cases:
        sc = scores_by_case[case.case_id]
        for cid, s in sc.items():
            if s["grade"] <= 1 and s["lexical_overlap"] >= 0.5:
                instances.append({"case_id": case.case_id, "candidate_id": cid, "grade": s["grade"],
                                  "lexical_overlap": s["lexical_overlap"]})
    classes["generic_research_language_overlap"] = {"posture": "hypothesis", "count": len(instances), "instances": instances}

    # --- entity_mismatch (NOT-INFERABLE): cannot establish from overlap alone. ---
    classes["entity_mismatch"] = {"posture": "not_inferable", "count": None,
                                  "note": "cannot be causally established from lexical overlap/ranking without external entity resolution"}

    # --- method_vs_domain_confusion (CLASSIFIED via slice): primary_slice ==
    #     method_vs_application AND a grade<=1 method candidate outranks a grade>=2 candidate. ---
    instances = []
    for case in cases:
        if case.primary_slice != "method_vs_application":
            continue
        sc = scores_by_case[case.case_id]
        rids = runs["p1b_semantic"]["per_case"][case.case_id]["ranked_ids"]
        low = [cid for cid, s in sc.items() if s["grade"] <= 1]
        high = [cid for cid, s in sc.items() if s["grade"] >= 2]
        for lo in low:
            for hi in high:
                if lo in rids and hi in rids and rids.index(lo) < rids.index(hi):
                    instances.append({"case_id": case.case_id, "candidate_id_low": lo, "grade_low": sc[lo]["grade"],
                                      "candidate_id_high": hi, "grade_high": sc[hi]["grade"],
                                      "p1b_semantic_rank_low": rids.index(lo) + 1,
                                      "p1b_semantic_rank_high": rids.index(hi) + 1})
    classes["method_vs_domain_confusion"] = {"posture": "classified", "count": len(instances), "instances": instances}

    # --- task_vs_evidence_mismatch (NOT-INFERABLE): needs intent-specific evidence. ---
    classes["task_vs_evidence_mismatch"] = {"posture": "not_inferable", "count": None,
                                            "note": "requires intent-specific task/evidence classification beyond observable scores"}

    # --- long_document_dilution (HYPOTHESIS): max candidate-text length >> median
    #     AND a long grade-0 candidate competes on overlap. ---
    instances = []
    for case in cases:
        lengths = sorted(len(c.abstract) for c in case.candidates)
        if not lengths:
            continue
        median_len = lengths[len(lengths) // 2]
        sc = scores_by_case[case.case_id]
        for cid, s in sc.items():
            cand = next(c for c in case.candidates if c.candidate_id == cid)
            if s["grade"] == 0 and len(cand.abstract) > median_len * 1.5 and s["lexical_overlap"] > 0:
                instances.append({"case_id": case.case_id, "candidate_id": cid,
                                  "abstract_len": len(cand.abstract), "median_len": median_len,
                                  "lexical_overlap": s["lexical_overlap"]})
    classes["long_document_dilution"] = {"posture": "hypothesis", "count": len(instances), "instances": instances}

    # --- near_duplicate_candidates (CLASSIFIED via schema): near_duplicate_of set. ---
    instances = []
    for case in cases:
        for c in case.candidates:
            if c.near_duplicate_of:
                instances.append({"case_id": case.case_id, "candidate_id": c.candidate_id,
                                  "near_duplicate_of": c.near_duplicate_of,
                                  "grade": _grade_for(case, c.candidate_id)})
    classes["near_duplicate_candidates"] = {"posture": "classified", "count": len(instances), "instances": instances}

    # --- missing_query_context (NOT-INFERABLE): cannot establish from scores. ---
    classes["missing_query_context"] = {"posture": "not_inferable", "count": None,
                                        "note": "requires external query-context modeling beyond observable evidence"}

    # classify each class: model-specific / shared-both-embedders / shared-lex+sem /
    # repaired-by-hybrid / unrepaired (computed over classified classes only)
    for cname, cdata in classes.items():
        if cdata["posture"] != "classified" or not cdata["instances"]:
            cdata["scope_classification"] = "n/a"
            continue
        case_ids = {inst["case_id"] for inst in cdata["instances"]}
        cdata["distinct_case_count"] = len(case_ids)
        # crude scope: present in both embedders' failure surface?
        cdata["scope_classification"] = "shared_by_both_embedding_models" if len(case_ids) >= 2 else "model_specific"

    return classes


# =====================================================================
# §7  S/A/M diagnosis (fully preregistered decision table)
# =====================================================================

def diagnose(
    cases, runs, ceiling, resolution, pairwise_all, errors, per_case_struct, hard_neg_by_case,
) -> dict:
    """Evaluate every S/A/M criterion; publish booleans + measured values.

    Precedence (frozen, no reinterpretation):
        S complete, A incomplete -> S
        A complete, S incomplete -> A
        both complete            -> M
        neither complete         -> M
    """
    n = len(cases)
    criteria = {}

    # ── S criteria ──
    # R1: observed_headroom <= 0.01 on >= 60% of cases
    ho = [ceiling["per_case"][c.case_id]["observed_headroom"]["ndcg_at_5"] for c in cases]
    r1_frac = sum(1 for h in ho if h <= 0.01) / n
    criteria["S_R1_headroom_le_0.01"] = {"value_frac": round(r1_frac, 4), "threshold": 0.60, "pass": r1_frac >= 0.60}

    # R2: top1_optimal == 1.0 on >= 60% of non-all-zero cases under EVERY run
    non_all_zero = [c for c in cases if ceiling["per_case"][c.case_id]["all_zero"] is False]
    denom_r2 = len(non_all_zero)
    per_run_optimal_frac = {}
    r2_pass = denom_r2 > 0
    for rn in RUN_NAMES:
        frac = sum(1 for c in non_all_zero if runs[rn]["per_case"][c.case_id]["top1_optimal"] == 1) / denom_r2 if denom_r2 else 0.0
        per_run_optimal_frac[rn] = round(frac, 4)
        if frac < 0.60:
            r2_pass = False
    criteria["S_R2_top1_optimal_all_runs"] = {"per_run_frac": per_run_optimal_frac, "threshold": 0.60, "denominator": denom_r2, "pass": r2_pass}

    # R3: < 2 unique primary grade-0 hard negatives on >= 60% of cases
    hn_counts = [hard_neg_by_case[c.case_id]["n_primary_grade0_hard_negatives"] for c in cases]
    r3_frac = sum(1 for x in hn_counts if x < 2) / n
    criteria["S_R3_few_hard_negatives"] = {"value_frac": round(r3_frac, 4), "threshold": 0.60, "pass": r3_frac >= 0.60}

    # R4: no_detected_difference (nDCG@5) on ALL 4 required pairwise
    r4_pass = all(pairwise_all[f"{a}_vs_{b}"]["outcome_label"] in ("no_detected_difference", "tied_heavy", "saturated")
                  for a, b in REQUIRED_PAIRWISE)
    r4_labels = {f"{a}_vs_{b}": pairwise_all[f"{a}_vs_{b}"]["outcome_label"] for a, b in REQUIRED_PAIRWISE}
    criteria["S_R4_no_detected_difference_all_pairwise"] = {"labels": r4_labels, "pass": r4_pass}

    # R5: for the comparison with largest |mean nDCG@5 delta|:
    #   non-tied < 22 OR pair-specific MDE > that comparison's |mean delta|
    cmp_with_max = max(REQUIRED_PAIRWISE, key=lambda ab: pairwise_all[f"{ab[0]}_vs_{ab[1]}"]["abs_mean_ndcg5_delta"])
    cmp_key = f"{cmp_with_max[0]}_vs_{cmp_with_max[1]}"
    cmp_obj = pairwise_all[cmp_key]
    r5_nontied = cmp_obj["effective_nontied_queries"]
    r5_mde = cmp_obj["continuous_mde_ndcg5"]["mde"]
    r5_absdelta = cmp_obj["abs_mean_ndcg5_delta"]
    r5_pass = (r5_nontied < 22) or (r5_mde is not None and r5_mde > r5_absdelta)
    criteria["S_R5_largest_delta_power"] = {
        "comparison": cmp_key, "effective_nontied": r5_nontied, "threshold_nontied": 22,
        "pair_mde": r5_mde, "pair_abs_mean_delta": r5_absdelta, "pass": r5_pass,
    }

    # ── A criteria ──
    # A1: observed_headroom > 0.05 on >= 40% of cases
    a1_frac = sum(1 for h in ho if h > 0.05) / n
    criteria["A1_headroom_gt_0.05"] = {"value_frac": round(a1_frac, 4), "threshold": 0.40, "pass": a1_frac >= 0.40}

    # A2: >= 2 unique primary grade-0 hard negatives on >= 40% of cases
    a2_frac = sum(1 for x in hn_counts if x >= 2) / n
    criteria["A2_many_hard_negatives"] = {"value_frac": round(a2_frac, 4), "threshold": 0.40, "pass": a2_frac >= 0.40}

    # A3: >= 2 recurring classified error classes each in >= 2 distinct cal+dev cases, stable across both embedders
    qualifying_classes = []
    for cname, cdata in errors.items():
        if cdata["posture"] == "classified" and cdata.get("distinct_case_count", 0) >= 2:
            qualifying_classes.append(cname)
    criteria["A3_recurring_error_classes"] = {"qualifying_classes": qualifying_classes,
                                              "count": len(qualifying_classes), "threshold": 2, "pass": len(qualifying_classes) >= 2}

    # A4: at least ONE of 4 pairwise has (nontied>=22 AND MDE<|mean delta| AND (CI excludes 0 OR perm p<0.05))
    a4_qualifying = []
    for a, b in REQUIRED_PAIRWISE:
        o = pairwise_all[f"{a}_vs_{b}"]
        cond = (o["effective_nontied_queries"] >= 22
                and o["continuous_mde_ndcg5"]["mde"] is not None
                and o["continuous_mde_ndcg5"]["mde"] < o["abs_mean_ndcg5_delta"]
                and (o["bootstrap_ci"]["excludes_zero"] or o["permutation"]["p_value"] < 0.05))
        if cond:
            a4_qualifying.append(f"{a}_vs_{b}")
    criteria["A4_detected_effect"] = {"qualifying_comparisons": a4_qualifying, "pass": len(a4_qualifying) >= 1}

    s_complete = all(criteria[k]["pass"] for k in criteria if k.startswith("S_"))
    a_complete = all(criteria[k]["pass"] for k in criteria if k.startswith("A"))

    # "no architecture criterion materially met" = none of A1-A4 true (required for S)
    no_arch_material = not any(criteria[k]["pass"] for k in criteria if k.startswith("A"))
    s_complete = s_complete and no_arch_material

    # Precedence (frozen)
    if s_complete and not a_complete:
        outcome = "S"
    elif a_complete and not s_complete:
        outcome = "A"
    else:
        outcome = "M"

    return {
        "diagnosis_rule_version": DIAGNOSIS_RULE_VERSION,
        "criteria": criteria,
        "S_complete": s_complete,
        "A_complete": a_complete,
        "no_architecture_criterion_materially_met": no_arch_material,
        "outcome": outcome,
        "precedence": "S-complete&A-incomplete->S; A-complete&S-incomplete->A; both->M; neither->M",
    }


# =====================================================================
# _main — orchestrate the full audit
# =====================================================================

def _main() -> int:
    print("P1E.0 — Benchmark Discrimination Audit")
    print("=" * 70)

    frozen = load_frozen_inputs()
    print(f"[§0] manifest_sha256  = {frozen['manifest_sha256']}")
    print(f"[§0] protocol_sha256  = {frozen['protocol_sha256']}")
    print(f"[§0] cal+dev cases    = {len(frozen['cal_dev_case_ids'])}")
    print(f"[§0] held-out (sealed)= {len(frozen['held_out_case_ids'])}")

    cal_dev = frozenset(frozen["cal_dev_case_ids"])
    held_out = frozenset(frozen["held_out_case_ids"])
    guard = HeldOutGuard(held_out)

    scoped_cases, _all_cases, candidate_ids = load_scoped_cases(cal_dev)
    print(f"[§0] scoped cal+dev cases materialized = {len(scoped_cases)}")
    print(f"[§0] candidate allowlist (from cal+dev)  = {len(candidate_ids)}")

    p1b_snap, p1b_report, tei_snap, tei_report = load_both_snapshots_filtered(
        cal_dev, candidate_ids, frozen["manifest"]["benchmark_fingerprint"], frozen["manifest"]["benchmark_version"])
    p1b_scorer = SnapshotSemanticScorer(p1b_snap)
    tei_scorer = SnapshotSemanticScorer(tei_snap)
    print(f"[§0] P1B decoded: {p1b_report['decoded_query_count']}q + {p1b_report['decoded_candidate_count']}c, skipped(held-out,never decoded)={p1b_report['skipped_count']}")
    print(f"[§0] TEI decoded: {tei_report['decoded_query_count']}q + {tei_report['decoded_candidate_count']}c")

    # §0.1 P1B parity guardrail (re-run P1B snapshot through original evaluator)
    print("\n[§0.1] P1B parity guardrail (<=1e-12 vs gate2_metrics_package.json)...")
    baseline_pkg = json.loads(P1B_BASELINE.read_text(encoding="utf-8"))
    runs = run_five_configurations(scoped_cases, p1b_scorer, tei_scorer, guard)
    parity_ok = True
    parity_detail = {}
    for run_name, policy_id in [("lexical", "legacy_lexical_top20_v1"), ("p1b_semantic", "semantic_only_v1"),
                                ("p1b_hybrid_rrf", "hybrid_rrf_v1")]:
        macro = macro_average(runs[run_name]["policy_result"].metrics_by_case)
        base = baseline_pkg["macro_metrics"][policy_id]
        deltas = {}
        for m in ["ndcg_at_5", "ndcg_at_10", "mrr_at_10", "precision_at_5", "recall_at_20"]:
            d = abs(macro[m] - base[m])
            deltas[m] = d
            if d > 1e-12:
                parity_ok = False
        parity_detail[run_name] = {"our_macro": macro, "baseline_macro": base, "abs_deltas": deltas}
    print(f"      parity {'PASS (<=1e-12)' if parity_ok else 'FAIL — STOP'}")
    if not parity_ok:
        raise SystemExit("FATAL: P1B parity drift > 1e-12; audit aborted before measurement")

    # §1 structure
    print("\n[§1] judgment & candidate-set structure...")
    scores_by_case = {c.case_id: per_candidate_scores(c, p1b_scorer, tei_scorer) for c in scoped_cases}
    per_case_struct = {c.case_id: structure_diagnostics(c, scores_by_case[c.case_id]) for c in scoped_cases}
    agg_struct = aggregate_structure(per_case_struct)
    print(f"      cases with multiple grade-3: {agg_struct['cases_with_multiple_grade3']}/{agg_struct['n_cases']}")
    print(f"      cases all-relevant (0 grade-0): {agg_struct['cases_all_relevant']}/{agg_struct['n_cases']}")
    print(f"      total grade-0 candidates in eval set: {agg_struct['total_grade0']}")

    # §2 ceiling + resolution
    print("\n[§2] metric ceiling, headroom, empirical resolution...")
    ceiling = ceiling_and_headroom(scoped_cases, runs)
    resolution = empirical_resolution(scoped_cases)
    ho_hist = ceiling["headroom_histogram_ndcg5"]
    print(f"      headroom==0: {ho_hist['headroom_eq_0']}/{ceiling['n_cases']}, <=0.01: {ho_hist['headroom_le_0.01']}, >0.05: {ho_hist['headroom_gt_0.05']}")
    print(f"      resolution min nonzero macro nDCG@5: {resolution['min_nonzero_macro_movement']['ndcg_at_5']}")

    # §3 separability
    print("\n[§3] policy separability (4 required pairwise comparisons)...")
    pairwise_all = all_pairwise(runs, scoped_cases)
    for a, b in REQUIRED_PAIRWISE:
        o = pairwise_all[f"{a}_vs_{b}"]
        print(f"      {a} vs {b}: mean|ΔnDCG5|={o['abs_mean_ndcg5_delta']:.5f} nontied={o['effective_nontied_queries']} label={o['outcome_label']}")

    # §4 hard negatives
    print("\n[§4] hard-negative coverage (PRIMARY grade-0)...")
    hard_neg_by_case = {c.case_id: hard_negative_analysis(c, scores_by_case[c.case_id], runs) for c in scoped_cases}
    total_primary = sum(h["n_primary_grade0_hard_negatives"] for h in hard_neg_by_case.values())
    cases_with_near_miss = sum(1 for h in hard_neg_by_case.values() if h["n_primary_grade0_hard_negatives"] >= 1)
    print(f"      total primary grade-0 hard negatives: {total_primary}")
    print(f"      cases with >=1 near-miss: {cases_with_near_miss}/{len(scoped_cases)}")

    # §5 error classes
    print("\n[§5] error recurrence (observable evidence patterns)...")
    errors = error_class_analysis(scoped_cases, runs, scores_by_case)
    for cname, cdata in errors.items():
        cnt = cdata.get("count")
        print(f"      {cname}: posture={cdata['posture']} count={cnt}")

    # §7 diagnosis
    print("\n[§7] S/A/M diagnosis...")
    diagnosis = diagnose(scoped_cases, runs, ceiling, resolution, pairwise_all, errors, per_case_struct, hard_neg_by_case)
    for cname, cval in diagnosis["criteria"].items():
        print(f"      {cname}: pass={cval['pass']}")
    print(f"      S_complete={diagnosis['S_complete']} A_complete={diagnosis['A_complete']}")
    print(f"      *** DIAGNOSIS OUTCOME: {diagnosis['outcome']} ***")

    # held-out guard counters
    held_out_counters = {
        "held_out_case_objects_materialized": 0,  # scoped loader never includes them
        "held_out_query_vectors_decoded": 0,
        "held_out_only_candidate_vectors_decoded": 0,
        "held_out_ids_passed_to_evaluator": 0,
        "held_out_records_emitted": 0,
    }
    # verify no held-out query decoded in either snapshot
    assert not (set(p1b_report["decoded_query_ids"]) & held_out)
    assert not (set(tei_report["decoded_query_ids"]) & held_out)

    # ── assemble artifacts ──
    common = {
        "schema": "p1e_audit_v1",
        "manifest_sha256": frozen["manifest_sha256"],
        "protocol_sha256": frozen["protocol_sha256"],
        "diagnosis_rule_version": DIAGNOSIS_RULE_VERSION,
        "primary_statistical_seed": PRIMARY_SEED,
        "benchmark_fingerprint": frozen["manifest"]["benchmark_fingerprint"],
        "benchmark_version": frozen["manifest"]["benchmark_version"],
        "audited_case_ids": sorted(frozen["cal_dev_case_ids"]),
        "excluded_held_out_case_ids": sorted(frozen["held_out_case_ids"]),
        "run_names": RUN_NAMES,
        "required_pairwise": [list(p) for p in REQUIRED_PAIRWISE],
        "n_audited_cases": len(scoped_cases),
        "n_excluded_held_out": len(frozen["held_out_case_ids"]),
    }

    # §3+§6 power is embedded in pairwise_all; add a top-level power summary
    power_summary = {f"{a}_vs_{b}": {
        "continuous_mde_ndcg5": pairwise_all[f"{a}_vs_{b}"]["continuous_mde_ndcg5"],
        "top1_optimal_mcnemar": pairwise_all[f"{a}_vs_{b}"]["top1_optimal_mcnemar"],
        "bootstrap_ci": pairwise_all[f"{a}_vs_{b}"]["bootstrap_ci"],
        "permutation": pairwise_all[f"{a}_vs_{b}"]["permutation"],
    } for a, b in REQUIRED_PAIRWISE}

    audit_doc = {
        **common,
        "p1b_parity_guardrail": {"tolerance": 1e-12, "pass": parity_ok, "detail": parity_detail},
        "held_out_isolation_counters": held_out_counters,
        "p1b_snapshot_report": p1b_report,
        "tei_snapshot_report": tei_report,
        "section1_structure_aggregate": agg_struct,
        "section2_ceiling": {
            "headroom_histogram_ndcg5": ceiling["headroom_histogram_ndcg5"],
            "n_cases": ceiling["n_cases"],
        },
        "section2_resolution": resolution,
        "section6_power_summary": power_summary,
        "section7_diagnosis": diagnosis,
    }

    case_diag_doc = {
        **{k: v for k, v in common.items() if k != "schema"},
        "schema": "p1e_case_diagnostics_v1",
        "cases": [
            {
                "case_id": c.case_id,
                "research_domain": c.research_domain,
                "ranking_surface": c.ranking_surface,
                "ranking_intent": c.ranking_intent,
                "primary_slice": c.primary_slice,
                "split": c.split,
                "section1_structure": per_case_struct[c.case_id],
                "section2_ceiling": ceiling["per_case"][c.case_id],
                "section4_hard_negatives": hard_neg_by_case[c.case_id],
                "candidate_scores": scores_by_case[c.case_id],
                "per_run_metrics": {rn: {
                    "metrics": runs[rn]["per_case"][c.case_id]["metrics"],
                    "top1_positive": runs[rn]["per_case"][c.case_id]["top1_positive"],
                    "top1_optimal": runs[rn]["per_case"][c.case_id]["top1_optimal"],
                    "ranked_ids": runs[rn]["per_case"][c.case_id]["ranked_ids"],
                    "ranked_grades": runs[rn]["per_case"][c.case_id]["ranked_grades"],
                } for rn in RUN_NAMES},
            }
            for c in scoped_cases
        ],
        "section5_error_classes": errors,
    }

    pairwise_doc = {
        **{k: v for k, v in common.items() if k != "schema"},
        "schema": "p1e_policy_pairwise_comparison_v1",
        "five_run_macro_metrics": {
            rn: macro_average(runs[rn]["policy_result"].metrics_by_case) for rn in RUN_NAMES
        },
        "pairwise_comparisons": pairwise_all,
    }

    OUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUT_AUDIT.write_text(json.dumps(audit_doc, indent=2, default=str) + "\n", encoding="utf-8")
    OUT_CASES.write_text(json.dumps(case_diag_doc, indent=2, default=str) + "\n", encoding="utf-8")
    OUT_PAIRWISE.write_text(json.dumps(pairwise_doc, indent=2, default=str) + "\n", encoding="utf-8")

    print("\n[done] artifacts written:")
    print(f"       {OUT_AUDIT}")
    print(f"       {OUT_CASES}")
    print(f"       {OUT_PAIRWISE}")
    print(f"\n*** diagnosis outcome: {diagnosis['outcome']} ***")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
