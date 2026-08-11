"""P1B Gate 2 diagnostic harness.

Reads the frozen benchmark + snapshot + the four policy runs and produces
the eight-section diagnostic required by the Gate 2 review. Pure analysis —
no policy tuning, no benchmark changes, no embedding regeneration.

Outputs:
  docs/p1b_gate2/diagnostic_analysis.json   machine-readable
  docs/p1b_gate2/diagnostic_analysis.md      human-readable report

Sections:
  1. case-level deltas + win/loss classification
  2. slice analysis
  3. surface + domain analysis
  4. lexical-baseline ceiling analysis
  5. embedding-snapshot analysis (similarity-grade correlation)
  6. RRF mechanics (fusion suppression analysis)
  7. judgment sensitivity (one-grade perturbation on low-confidence judgments)
  8. statistical power (effective n, MDE, bootstrap distribution)
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from backend.ranking.benchmark_v2_registry import (
    BENCHMARK_V2,
    compute_benchmark_v2_fingerprint,
    frozen_v2_cases,
)
from backend.ranking.embedding_snapshot import load_snapshot
from backend.ranking.evaluation import _ndcg_at_k
from backend.ranking.p1b3_evaluation import (
    FROZEN_RRF_K,
    FROZEN_WEIGHTED_LEXICAL,
    FROZEN_WEIGHTED_SEMANTIC,
    HYBRID_WEIGHTED_POLICY_ID,
    SEMANTIC_ONLY_POLICY_ID,
    SnapshotSemanticScorer,
    _build_request,
    _cosine,
    _grade_for,
    paired_bootstrap_ci,
    rank_hybrid_weighted,
    rank_semantic_only,
)
from backend.ranking.policies import _keyword_overlap, rank_hybrid_rrf, rank_legacy_lexical

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR = REPO_ROOT / "docs" / "p1b_snapshot"
OUT_DIR = REPO_ROOT / "docs" / "p1b_gate2"


def _grade(case, cid):
    return _grade_for(case, cid)


def _keyword_overlap_for(case, cand) -> float:
    return _keyword_overlap(case.query_text, f"{cand.title} {cand.abstract}")


# ── Run all policies on selection cases, capture full per-case detail ─

def run_all_policies(cases, scorer):
    """Return {policy_id: {case_id: RankingResult}} plus helper metrics."""
    out = {}
    out["legacy_lexical_top20_v1"] = {
        c.case_id: _legacy_result(c, scorer) for c in cases
    }
    out[SEMANTIC_ONLY_POLICY_ID] = {
        c.case_id: _sem_result(c, scorer) for c in cases
    }
    out["hybrid_rrf_v1"] = {
        c.case_id: _rrf_result(c, scorer) for c in cases
    }
    out[HYBRID_WEIGHTED_POLICY_ID] = {
        c.case_id: _weighted_result(c, scorer) for c in cases
    }
    return out


def _legacy_result(case, scorer):
    req = _build_request(case, scorer=scorer, include_semantic=False,
                         policy_id="legacy_lexical_top20_v1")
    return rank_legacy_lexical(req)


def _sem_result(case, scorer):
    req = _build_request(case, scorer=scorer, include_semantic=True,
                         policy_id=SEMANTIC_ONLY_POLICY_ID)
    return rank_semantic_only(req)


def _rrf_result(case, scorer):
    req = _build_request(case, scorer=scorer, include_semantic=True,
                         policy_id="hybrid_rrf_v1")
    return rank_hybrid_rrf(req, rrf_k=FROZEN_RRF_K)


def _weighted_result(case, scorer):
    req = _build_request(case, scorer=scorer, include_semantic=True,
                         policy_id=HYBRID_WEIGHTED_POLICY_ID)
    return rank_hybrid_weighted(req, lexical_weight=FROZEN_WEIGHTED_LEXICAL,
                                semantic_weight=FROZEN_WEIGHTED_SEMANTIC)


def _case_ndcg10(case, result):
    ranked_grades = [_grade(case, rc.candidate_id) for rc in result.ranked]
    return _ndcg_at_k(ranked_grades, 10)


def _rank_of(result, candidate_id):
    for rc in result.ranked:
        if rc.candidate_id == candidate_id:
            return rc.final_rank
    return None


# ── Section 1: case-level deltas ─────────────────────────────────────

def case_level_deltas(cases, results_by_policy):
    rows = []
    for case in cases:
        legacy = results_by_policy["legacy_lexical_top20_v1"][case.case_id]
        sem = results_by_policy[SEMANTIC_ONLY_POLICY_ID][case.case_id]
        rrf = results_by_policy["hybrid_rrf_v1"][case.case_id]
        wt = results_by_policy[HYBRID_WEIGHTED_POLICY_ID][case.case_id]
        leg_n = _case_ndcg10(case, legacy)
        sem_n = _case_ndcg10(case, sem)
        rrf_n = _case_ndcg10(case, rrf)
        wt_n = _case_ndcg10(case, wt)
        delta_rrf = rrf_n - leg_n
        # largest rank change between legacy and rrf for any candidate
        max_rank_change = 0
        for c in case.candidates:
            lr = _rank_of(legacy, c.candidate_id)
            rr = _rank_of(rrf, c.candidate_id)
            if lr is not None and rr is not None:
                max_rank_change = max(max_rank_change, abs(lr - rr))
        # classification vs legacy (rrf)
        if delta_rrf > 0.05:
            cls = "hybrid_clear_win"
        elif delta_rrf > 0:
            cls = "hybrid_marginal_win"
        elif delta_rrf == 0:
            cls = "no_effective_change"
        elif delta_rrf > -0.05:
            cls = "hybrid_marginal_loss"
        else:
            cls = "hybrid_material_loss"
        rows.append({
            "case_id": case.case_id,
            "slice": case.primary_slice,
            "surface": case.ranking_surface,
            "domain": case.research_domain,
            "legacy_ndcg10": round(leg_n, 4),
            "semantic_ndcg10": round(sem_n, 4),
            "hybrid_rrf_ndcg10": round(rrf_n, 4),
            "weighted_ndcg10": round(wt_n, 4),
            "delta_rrf_vs_legacy": round(delta_rrf, 4),
            "delta_semantic_vs_legacy": round(sem_n - leg_n, 4),
            "max_rank_change_legacy_to_rrf": max_rank_change,
            "classification": cls,
        })
    # aggregate classification counts
    cls_counts = defaultdict(int)
    for r in rows:
        cls_counts[r["classification"]] += 1
    return {"rows": rows, "classification_counts": dict(cls_counts)}


# ── Section 2: slice analysis ────────────────────────────────────────

def slice_analysis(cases, results_by_policy):
    by_slice = defaultdict(list)
    for c in cases:
        by_slice[c.primary_slice].append(c)
    out = {}
    for sl, scs in by_slice.items():
        entry = {"n": len(scs)}
        for pid in ("legacy_lexical_top20_v1", SEMANTIC_ONLY_POLICY_ID,
                    "hybrid_rrf_v1", HYBRID_WEIGHTED_POLICY_ID):
            ns = [_case_ndcg10(c, results_by_policy[pid][c.case_id]) for c in scs]
            entry[pid] = round(sum(ns) / len(ns), 4)
        # delta vs legacy for each policy
        for pid in (SEMANTIC_ONLY_POLICY_ID, "hybrid_rrf_v1", HYBRID_WEIGHTED_POLICY_ID):
            entry[f"delta_{pid}"] = round(entry[pid] - entry["legacy_lexical_top20_v1"], 4)
        out[sl] = entry
    return out


# ── Section 3: surface + domain analysis ─────────────────────────────

def surface_domain_analysis(cases, results_by_policy):
    out = {"by_surface": {}, "by_domain": {}}
    for dim_key, dim in (("by_surface", "ranking_surface"), ("by_domain", "research_domain")):
        groups = defaultdict(list)
        for c in cases:
            groups[getattr(c, dim)].append(c)
        for gname, gcs in groups.items():
            entry = {"n": len(gcs)}
            for pid in ("legacy_lexical_top20_v1", SEMANTIC_ONLY_POLICY_ID,
                        "hybrid_rrf_v1", HYBRID_WEIGHTED_POLICY_ID):
                ns = [_case_ndcg10(c, results_by_policy[pid][c.case_id]) for c in gcs]
                entry[pid] = round(sum(ns) / len(ns), 4)
            for pid in (SEMANTIC_ONLY_POLICY_ID, "hybrid_rrf_v1", HYBRID_WEIGHTED_POLICY_ID):
                entry[f"delta_{pid}"] = round(entry[pid] - entry["legacy_lexical_top20_v1"], 4)
            out[dim_key][gname] = entry
    return out


# ── Section 4: lexical-baseline ceiling ──────────────────────────────

def lexical_ceiling_analysis(cases, scorer):
    perfect = 0
    all_g3_have_query_terms = 0
    trivially_separable = 0
    genuine_low_overlap = 0
    detail = []
    for case in cases:
        legacy = _legacy_result(case, scorer)
        leg_n = _case_ndcg10(case, legacy)
        if leg_n >= 0.999:
            perfect += 1
        # do all grade-3 candidates contain at least one query term?
        q_terms = set(_tokenize(case.query_text))
        g3_cands = [c for c in case.candidates if _grade(case, c.candidate_id) == 3]
        if g3_cands:
            all_have = all(
                q_terms & _tokenize(f"{c.title} {c.abstract}") for c in g3_cands
            )
            if all_have:
                all_g3_have_query_terms += 1
        # trivially separable: every grade>=2 candidate has higher lexical overlap than every grade<=1
        hi = [(_keyword_overlap_for(case, c), _grade(case, c.candidate_id)) for c in case.candidates]
        grades_hi = [g for _, g in hi if g >= 2]
        grades_lo = [g for _, g in hi if g <= 1]
        overlaps_hi = [o for o, g in hi if g >= 2]
        overlaps_lo = [o for o, g in hi if g <= 1]
        if grades_hi and grades_lo and overlaps_hi and overlaps_lo:
            if min(overlaps_hi) > max(overlaps_lo):
                trivially_separable += 1
        # genuine low-overlap: at least one grade>=2 candidate with overlap < 0.3
        if any(g >= 2 and o < 0.3 for o, g in hi):
            genuine_low_overlap += 1
        all_g3_cands = [c for c in case.candidates if _grade(case, c.candidate_id) == 3]
        all_g3_have_qt = (
            all(q_terms & _tokenize(f"{c.title} {c.abstract}") for c in all_g3_cands)
            if all_g3_cands else None
        )
        detail.append({
            "case_id": case.case_id,
            "slice": case.primary_slice,
            "legacy_ndcg10": round(leg_n, 4),
            "perfect": leg_n >= 0.999,
            "all_g3_have_query_terms": all_g3_have_qt,
            "genuine_low_overlap_relevant": any(
                _grade(case, c.candidate_id) >= 2 and _keyword_overlap_for(case, c) < 0.3 for c in case.candidates
            ),
        })
    n = len(cases)
    return {
        "n_cases": n,
        "perfect_legacy_ndcg10": perfect,
        "perfect_rate": round(perfect / n, 4),
        "all_g3_have_query_terms": all_g3_have_query_terms,
        "trivially_separable": trivially_separable,
        "trivially_separable_rate": round(trivially_separable / n, 4),
        "genuine_low_overlap_relevant": genuine_low_overlap,
        "genuine_low_overlap_rate": round(genuine_low_overlap / n, 4),
        "verdict": (
            "headroom_limited" if perfect / n > 0.5
            else "moderate_headroom" if perfect / n > 0.25
            else "adequate_headroom"
        ),
        "per_case": detail,
    }


def _tokenize(text):
    import re
    return set(re.findall(r"\w+", text.lower()))


# ── Section 5: embedding-snapshot analysis ───────────────────────────

def embedding_snapshot_analysis(cases, snapshot):
    # Per-case: correlation between cosine(query,candidate) and relevance grade
    per_case = []
    all_pairs = []  # (sim, grade)
    # by slice: mean sim for grade-3 vs grade-0
    by_slice_g3 = defaultdict(list)
    by_slice_g0 = defaultdict(list)
    trap_distinguished = 0  # cases where the grade-0 lexical trap has lower sim than the top grade-3
    paraphrase_retrieved = 0  # semantic_paraphrase cases where grade-3 paraphrase ranks #1 by sim
    for case in cases:
        q_item = snapshot.get(case.case_id)
        if q_item is None:
            continue
        sims_grades = []
        top_sim_cid = None
        top_sim = -1.0
        for c in case.candidates:
            c_item = snapshot.get(c.candidate_id)
            if c_item is None:
                continue
            sim = _cosine(q_item.vector, c_item.vector)
            g = _grade(case, c.candidate_id)
            sims_grades.append((sim, g, c.candidate_id))
            all_pairs.append((sim, g))
            by_slice_g3[case.primary_slice].append(sim if g == 3 else None)
            by_slice_g0[case.primary_slice].append(sim if g == 0 else None)
            if sim > top_sim:
                top_sim = sim; top_sim_cid = c.candidate_id
        # spearman-ish: rank correlation
        rho = _rank_corr(sims_grades)
        # trap distinguished: grade-0 trap lower sim than max grade-3
        g0_sims = [s for s, g, _ in sims_grades if g == 0]
        g3_sims = [s for s, g, _ in sims_grades if g == 3]
        trap_ok = bool(g0_sims and g3_sims and max(g3_sims) > max(g0_sims))
        if trap_ok and case.primary_slice == "lexical_trap":
            trap_distinguished += 1
        # paraphrase retrieved: top-sim candidate is grade 3 on semantic_paraphrase slice
        if case.primary_slice == "semantic_paraphrase":
            top_g = next((g for s, g, cid in sims_grades if cid == top_sim_cid), None)
            if top_g == 3:
                paraphrase_retrieved += 1
        per_case.append({
            "case_id": case.case_id,
            "slice": case.primary_slice,
            "sim_grade_rank_corr": round(rho, 4) if rho is not None else None,
            "top_sim_candidate": top_sim_cid,
            "top_sim_grade": next((g for s, g, cid in sims_grades if cid == top_sim_cid), None),
        })
    # overall sim-grade correlation
    overall_rho = _rank_corr(all_pairs)
    # mean sim by grade
    by_grade = defaultdict(list)
    for s, g in all_pairs:
        by_grade[g].append(s)
    mean_sim_by_grade = {g: round(statistics.mean(v), 4) for g, v in sorted(by_grade.items()) if v}
    # slice-level: does sim separate g3 from g0?
    slice_separation = {}
    for sl in set(by_slice_g3) | set(by_slice_g0):
        g3 = [x for x in by_slice_g3[sl] if x is not None]
        g0 = [x for x in by_slice_g0[sl] if x is not None]
        if g3 and g0:
            slice_separation[sl] = {
                "mean_sim_g3": round(statistics.mean(g3), 4),
                "mean_sim_g0": round(statistics.mean(g0), 4),
                "g3_gt_g0": statistics.mean(g3) > statistics.mean(g0),
            }
    n_trap = sum(1 for c in cases if c.primary_slice == "lexical_trap")
    n_para = sum(1 for c in cases if c.primary_slice == "semantic_paraphrase")
    return {
        "overall_sim_grade_rank_corr": round(overall_rho, 4) if overall_rho is not None else None,
        "mean_cosine_by_grade": mean_sim_by_grade,
        "lexical_trap_cases_distinguished": trap_distinguished,
        "lexical_trap_cases_total": n_trap,
        "paraphrase_cases_top_sim_is_g3": paraphrase_retrieved,
        "paraphrase_cases_total": n_para,
        "slice_separation_g3_vs_g0": slice_separation,
        "per_case": per_case,
    }


def _rank_corr(pairs):
    """Spearman-style rank correlation between similarity and grade."""
    sims = [p[0] for p in pairs]
    grades = [p[1] for p in pairs]
    if len(sims) < 3:
        return None
    sim_ranks = _ranks(sims)
    grade_ranks = _ranks(grades)
    n = len(sims)
    d2 = sum((a - b) ** 2 for a, b in zip(sim_ranks, grade_ranks))
    return 1 - 6 * d2 / (n * (n * n - 1))


def _ranks(values):
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0] * len(values)
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[sorted_idx[j + 1]] == values[sorted_idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[sorted_idx[k]] = avg
        i = j + 1
    return ranks


# ── Section 6: RRF mechanics ─────────────────────────────────────────

def rrf_mechanics(cases, scorer):
    """Analyze where semantic-only wins but RRF loses, and RRF suppression."""
    sem_wins_rrf_loses = []  # semantic > legacy AND rrf <= legacy
    lexical_dominance = 0  # cases where lexical rank 1 == rrf rank 1 but semantic rank 1 differs
    semantic_correction_blocked = 0  # semantic-only beats legacy on a case, but rrf does not
    detail = []
    for case in cases:
        legacy = _legacy_result(case, scorer)
        sem = _sem_result(case, scorer)
        rrf = _rrf_result(case, scorer)
        leg_n = _case_ndcg10(case, legacy)
        sem_n = _case_ndcg10(case, sem)
        rrf_n = _case_ndcg10(case, rrf)
        # ranks
        lex_rank1 = legacy.ranked[0].candidate_id if legacy.ranked else None
        sem_rank1 = sem.ranked[0].candidate_id if sem.ranked else None
        rrf_rank1 = rrf.ranked[0].candidate_id if rrf.ranked else None
        # semantic-only improves but rrf does not capture the improvement
        sem_beats = sem_n > leg_n + 1e-9
        rrf_captures = rrf_n > leg_n + 1e-9
        if sem_beats and not rrf_captures:
            semantic_correction_blocked += 1
            sem_wins_rrf_loses.append({
                "case_id": case.case_id, "slice": case.primary_slice,
                "legacy": round(leg_n, 4), "semantic": round(sem_n, 4), "rrf": round(rrf_n, 4),
                "sem_rank1": sem_rank1, "rrf_rank1": rrf_rank1, "lex_rank1": lex_rank1,
            })
        # lexical dominance: lexical top-1 == rrf top-1 but != semantic top-1
        if lex_rank1 == rrf_rank1 and sem_rank1 != lex_rank1:
            lexical_dominance += 1
        detail.append({
            "case_id": case.case_id, "slice": case.primary_slice,
            "legacy_ndcg10": round(leg_n, 4),
            "semantic_ndcg10": round(sem_n, 4),
            "rrf_ndcg10": round(rrf_n, 4),
            "lex_rank1": lex_rank1, "sem_rank1": sem_rank1, "rrf_rank1": rrf_rank1,
            "sem_beats_legacy": sem_beats, "rrf_captures": rrf_captures,
        })
    return {
        "n_cases": len(cases),
        "semantic_correction_blocked_count": semantic_correction_blocked,
        "lexical_dominance_count": lexical_dominance,
        "sem_wins_rrf_loses": sem_wins_rrf_loses,
        "per_case": detail,
    }


# ── Section 7: judgment sensitivity ──────────────────────────────────

def judgment_sensitivity(cases, scorer, results_by_policy):
    """Perturb the lowest-confidence judgments by ±1 grade, recompute
    hybrid_rrf vs legacy delta, check if Gate 2 verdict changes.

    Does NOT modify the official benchmark — purely a sensitivity probe.
    """
    # find low-confidence judgments (confidence < 0.75)
    low_conf = []
    for case in cases:
        for cid, prov in case.judgments.items():
            if prov.final_confidence() < 0.75:
                low_conf.append((case.case_id, cid, prov.final_grade(), prov.final_confidence()))
    # baseline delta (rrf - legacy) on selection cases
    baseline_deltas = []
    for case in cases:
        legacy = results_by_policy["legacy_lexical_top20_v1"][case.case_id]
        rrf = results_by_policy["hybrid_rrf_v1"][case.case_id]
        baseline_deltas.append(_case_ndcg10(case, rrf) - _case_ndcg10(case, legacy))
    base_mean = sum(baseline_deltas) / len(baseline_deltas) if baseline_deltas else 0.0
    # perturbation: for each low-conf judgment, flip its grade by +1 or -1
    # (clamped 0..3) and recompute the case's rrf-legacy delta. Report the
    # range of mean-delta shifts across all single-judgment perturbations.
    case_map = {c.case_id: c for c in cases}
    shifts = []
    for case_id, cid, orig_grade, conf in low_conf:
        for delta in (+1, -1):
            new_grade = max(0, min(3, orig_grade + delta))
            if new_grade == orig_grade:
                continue
            case = case_map[case_id]
            # recompute with a patched grade
            legacy = results_by_policy["legacy_lexical_top20_v1"][case_id]
            rrf = results_by_policy["hybrid_rrf_v1"][case_id]
            leg_n = _case_ndcg10_perturbed(case, legacy, cid, new_grade)
            rrf_n = _case_ndcg10_perturbed(case, rrf, cid, new_grade)
            new_case_delta = rrf_n - leg_n
            old_case_delta = (_case_ndcg10(case, rrf) - _case_ndcg10(case, legacy))
            shifts.append({
                "case_id": case_id, "candidate_id": cid,
                "orig_grade": orig_grade, "conf": conf,
                "perturbation": delta, "new_grade": new_grade,
                "case_delta_shift": round(new_case_delta - old_case_delta, 4),
            })
    # would the gate verdict change? gate needs mean delta >= 0.03 AND lb > 0.
    # We approximate: if max possible mean shift is < (0.03 - base_mean), verdict can't flip to PASS.
    max_shift = max((abs(s["case_delta_shift"]) for s in shifts), default=0.0)
    max_mean_shift = max_shift / len(cases) if cases else 0.0
    return {
        "n_low_confidence_judgments": len(low_conf),
        "baseline_mean_delta_rrf_vs_legacy": round(base_mean, 4),
        "max_single_judgment_case_delta_shift": round(max_shift, 4),
        "max_implied_mean_delta_shift": round(max_mean_shift, 6),
        "gap_to_threshold": round(0.03 - base_mean, 4),
        "verdict_under_max_perturbation": (
            "could_flip" if max_mean_shift >= (0.03 - base_mean) else "stable"
        ),
        "perturbations": shifts,
    }


def _case_ndcg10_perturbed(case, result, perturb_cid, new_grade):
    ranked_grades = []
    for rc in result.ranked:
        if rc.candidate_id == perturb_cid:
            ranked_grades.append(new_grade)
        else:
            ranked_grades.append(_grade(case, rc.candidate_id))
    return _ndcg_at_k(ranked_grades, 10)


# ── Section 8: statistical power ─────────────────────────────────────

def statistical_power(cases, results_by_policy):
    case_ids = [c.case_id for c in cases]
    all_grades = {c.case_id: [_grade(c, cc.candidate_id) for cc in c.candidates] for c in cases}
    legacy_ranks = results_by_policy["legacy_lexical_top20_v1"]
    rrf_ranks = results_by_policy["hybrid_rrf_v1"]
    per_case_delta = []
    for case in cases:
        leg = results_by_policy["legacy_lexical_top20_v1"][case.case_id]
        rrf = results_by_policy["hybrid_rrf_v1"][case.case_id]
        per_case_delta.append(_case_ndcg10(case, rrf) - _case_ndcg10(case, leg))
    n_nonzero = sum(1 for d in per_case_delta if abs(d) > 1e-9)
    sd = statistics.pstdev(per_case_delta) if len(per_case_delta) > 1 else 0.0
    n = len(per_case_delta)
    # minimum detectable effect (two-sided alpha=0.05, approx z=1.96) using paired t
    # MDE = z * sd / sqrt(n)
    mde = 1.96 * sd / math.sqrt(n) if n > 0 else 0.0
    # bootstrap distribution (already computed in gate2 but redo for self-containment)
    ci = paired_bootstrap_ci(
        case_ids,
        {c.case_id: [_grade(case, rc.candidate_id) for rc in results_by_policy["legacy_lexical_top20_v1"][c.case_id].ranked] for c in cases},
        {c.case_id: [_grade(case, rc.candidate_id) for rc in results_by_policy["hybrid_rrf_v1"][c.case_id].ranked] for c in cases},
        lambda rg, ag: _ndcg_at_k(rg, 10),
        all_grades, n_bootstrap=10000, seed=20260721,
    )
    return {
        "n_cases": n,
        "n_nonzero_paired_delta": n_nonzero,
        "mean_paired_delta": round(statistics.mean(per_case_delta), 6),
        "sd_paired_delta": round(sd, 6),
        "minimum_detectable_effect_paired_t_95pct": round(mde, 6),
        "frozen_threshold": 0.03,
        "mde_exceeds_threshold": mde > 0.03,
        "bootstrap_ci": ci,
        "interpretation": (
            "underpowered" if mde > 0.03
            else "adequately_powered" if mde < 0.015
            else "borderline"
        ),
    }


def main():
    bench_fp = compute_benchmark_v2_fingerprint()
    snap = load_snapshot(SNAPSHOT_DIR, expected_benchmark_fingerprint=bench_fp,
                         expected_benchmark_version=BENCHMARK_V2["version"])
    scorer = SnapshotSemanticScorer(snap)
    cases = [c for c in frozen_v2_cases() if c.split in ("calibration", "development")]
    print(f"diagnostic over {len(cases)} selection cases")

    results = run_all_policies(cases, scorer)

    s1 = case_level_deltas(cases, results)
    s2 = slice_analysis(cases, results)
    s3 = surface_domain_analysis(cases, results)
    s4 = lexical_ceiling_analysis(cases, scorer)
    s5 = embedding_snapshot_analysis(cases, snap)
    s6 = rrf_mechanics(cases, scorer)
    s7 = judgment_sensitivity(cases, scorer, results)
    s8 = statistical_power(cases, results)

    package = {
        "benchmark_fingerprint": bench_fp,
        "snapshot_fingerprint": snap.snapshot_fingerprint,
        "n_selection_cases": len(cases),
        "section_1_case_level": s1,
        "section_2_slice": s2,
        "section_3_surface_domain": s3,
        "section_4_lexical_ceiling": s4,
        "section_5_embedding_snapshot": s5,
        "section_6_rrf_mechanics": s6,
        "section_7_judgment_sensitivity": s7,
        "section_8_statistical_power": s8,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "diagnostic_analysis.json").write_text(json.dumps(package, indent=2))
    print(f"wrote {OUT_DIR / 'diagnostic_analysis.json'}")
    # Print key signals for the branch decision
    print()
    print("=== KEY SIGNALS ===")
    print(f"perfect baseline cases: {s4['perfect_legacy_ndcg10']}/{s4['n_cases']} ({s4['perfect_rate']:.0%})")
    print(f"trivially separable: {s4['trivially_separable']}/{s4['n_cases']} ({s4['trivially_separable_rate']:.0%})")
    print(f"genuine low-overlap relevant: {s4['genuine_low_overlap_relevant']}")
    print(f"lexical ceiling verdict: {s4['verdict']}")
    print()
    print(f"overall sim-grade rank corr: {s5['overall_sim_grade_rank_corr']}")
    print(f"mean cosine by grade: {s5['mean_cosine_by_grade']}")
    print(f"lexical traps distinguished by embedding: {s5['lexical_trap_cases_distinguished']}/{s5['lexical_trap_cases_total']}")
    print(f"paraphrase cases top-sim is g3: {s5['paraphrase_cases_top_sim_is_g3']}/{s5['paraphrase_cases_total']}")
    print()
    print(f"semantic correction blocked by RRF: {s6['semantic_correction_blocked_count']}/{s6['n_cases']}")
    print(f"lexical dominance (lex#1==rrf#1!=sem#1): {s6['lexical_dominance_count']}/{s6['n_cases']}")
    print()
    print(f"statistical power: MDE={s8['minimum_detectable_effect_paired_t_95pct']:.4f} vs threshold 0.03 -> {s8['interpretation']}")
    print(f"judgment sensitivity: max mean shift {s7['max_implied_mean_delta_shift']:.4f}, gap to threshold {s7['gap_to_threshold']:.4f} -> {s7['verdict_under_max_perturbation']}")


if __name__ == "__main__":
    main()
