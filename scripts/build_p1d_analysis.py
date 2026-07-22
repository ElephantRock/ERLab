"""P1D.1a helper: build per-case failure analysis from frozen benchmark + gate2 diagnostic.

Revision P1D.1a corrects three defects from v1:
  - defect 2: held-out cases were counted as observed failures. Now separated:
      observed_selection_metrics vs slice_design_prior_only. Held-out observed
      categories are NULL.
  - defect 3: classifications were slice lookups presented as causal diagnoses.
      Now explicitly labeled slice-informed intervention hypotheses, with the
      slice_expected_failure_mode distinguished from any observed behavior.
  - builder hardening: fingerprint/count assertions, writes the distribution
      artifact directly (no temp file), schema-conformance check.

Outputs:
  data/retrieval/p1d_historical_failure_analysis.jsonl
  data/retrieval/p1d_failure_distribution.json

DRAFT artifact (status: draft) - NOT frozen, no gate closed.
"""
from __future__ import annotations
import sys, json
from collections import Counter
from pathlib import Path

sys.path.insert(0, '.')

from backend.ranking.benchmark_v2_discovery_cases import (
    _DISCOVERY_LEXICAL_TRAP, _DISCOVERY_SEMANTIC_PARAPHRASE, _DISCOVERY_METHOD_VS_APPLICATION,
    _DISCOVERY_REVIEW_VS_PRIMARY, _DISCOVERY_MISSING_ABSTRACT, _DISCOVERY_NEAR_DUPLICATE,
    _DISCOVERY_SOURCE_RANK_CONFLICT, _DISCOVERY_ACRONYM_VS_EXPANDED, _DISCOVERY_NEGATED_FINDINGS,
    _DISCOVERY_EXACT_IDENTIFIER, _DISCOVERY_NEUTRAL,
)
from backend.ranking.benchmark_v2_retrieval_cases import (
    _RETRIEVAL_LEXICAL_TRAP, _RETRIEVAL_SEMANTIC_PARAPHRASE, _RETRIEVAL_METHOD_VS_APPLICATION,
    _RETRIEVAL_REVIEW_VS_PRIMARY, _RETRIEVAL_MISSING_ABSTRACT, _RETRIEVAL_NEAR_DUPLICATE,
    _RETRIEVAL_SOURCE_RANK_CONFLICT, _RETRIEVAL_ACRONYM_VS_EXPANDED, _RETRIEVAL_NEGATED_FINDINGS,
    _RETRIEVAL_EXACT_IDENTIFIER, _RETRIEVAL_NEUTRAL,
)
from backend.ranking.benchmark_v2_registry import compute_benchmark_v2_fingerprint

ALL_DISC = (_DISCOVERY_LEXICAL_TRAP + _DISCOVERY_SEMANTIC_PARAPHRASE + _DISCOVERY_METHOD_VS_APPLICATION
    + _DISCOVERY_REVIEW_VS_PRIMARY + _DISCOVERY_MISSING_ABSTRACT + _DISCOVERY_NEAR_DUPLICATE
    + _DISCOVERY_SOURCE_RANK_CONFLICT + _DISCOVERY_ACRONYM_VS_EXPANDED + _DISCOVERY_NEGATED_FINDINGS
    + _DISCOVERY_EXACT_IDENTIFIER + _DISCOVERY_NEUTRAL)
ALL_RET = (_RETRIEVAL_LEXICAL_TRAP + _RETRIEVAL_SEMANTIC_PARAPHRASE + _RETRIEVAL_METHOD_VS_APPLICATION
    + _RETRIEVAL_REVIEW_VS_PRIMARY + _RETRIEVAL_MISSING_ABSTRACT + _RETRIEVAL_NEAR_DUPLICATE
    + _RETRIEVAL_SOURCE_RANK_CONFLICT + _RETRIEVAL_ACRONYM_VS_EXPANDED + _RETRIEVAL_NEGATED_FINDINGS
    + _RETRIEVAL_EXACT_IDENTIFIER + _RETRIEVAL_NEUTRAL)
ALL_CASES = ALL_DISC + ALL_RET

# Expected provenance - pinned for assertion. If the benchmark changes, these
# assertions fail loudly rather than silently producing analysis on a different benchmark.
EXPECTED_BENCHMARK_FINGERPRINT = "0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4"
EXPECTED_SNAPSHOT_FINGERPRINT = "2d8b26f709c03b6bbc7d5c4ab7ca65255e0e1f8eb65aa5562b205e0602084000"
EXPECTED_TOTAL_CASES = 66
EXPECTED_SELECTION_CASES = 44
EXPECTED_HELD_OUT_CASES = 22
EXPECTED_JUDGMENTS = 270

SLICE_TO_FAMILIES = {
    "lexical_trap": (["research_gap_analysis", "paper_discovery"], ["evidence_retrieval"]),
    "semantic_paraphrase": (["paper_discovery", "evidence_retrieval"], ["research_gap_analysis"]),
    "method_vs_application": (["method_retrieval"], ["paper_discovery"]),
    "review_vs_primary": (["evidence_retrieval", "multi_paper_synthesis"], ["paper_discovery"]),
    "missing_abstract": (["paper_discovery", "evidence_retrieval"], []),
    "near_duplicate": (["multi_paper_synthesis"], ["paper_discovery"]),
    "source_rank_conflict": (["research_gap_analysis", "evidence_retrieval"], ["paper_discovery"]),
    "acronym_vs_expanded": (["research_gap_analysis", "paper_discovery"], ["evidence_retrieval"]),
    "negated_findings": (["contradiction_retrieval"], ["evidence_retrieval", "research_gap_analysis"]),
    "exact_identifier": (["paper_discovery", "research_gap_analysis"], ["method_retrieval"]),
    "neutral": (["paper_discovery"], ["method_retrieval"]),
}

# Slice -> expected failure mode (the failure the slice is DESIGNED to exercise).
# This is a design prior, NOT a measured cause. Renamed from v1's dominant_failure_category.
SLICE_EXPECTED_FAILURE_MODE = {
    "lexical_trap": ("LEXICAL_PRECISION", "Slice designed to exercise lexical traps: high token overlap with a wrong-meaning result."),
    "semantic_paraphrase": ("SEMANTIC_GENERALIZATION", "Slice designed to exercise low-overlap conceptual relevance (paraphrase)."),
    "method_vs_application": ("AGENDA_MISMATCH", "Slice designed to exercise method-vs-application discrimination."),
    "review_vs_primary": ("EVIDENCE_GRANULARITY", "Slice designed to exercise primary-vs-review evidence-granularity discrimination."),
    "missing_abstract": ("EVIDENCE_GRANULARITY", "Slice designed to exercise ranking when the evidential text is absent."),
    "near_duplicate": ("DIVERSITY", "Slice designed to exercise non-domination by near-duplicates."),
    "source_rank_conflict": ("AGENDA_MISMATCH", "Slice designed to exercise source-priority-vs-relevance conflict."),
    "acronym_vs_expanded": ("LEXICAL_PRECISION", "Slice designed to exercise acronym-collision (specialized lexical trap)."),
    "negated_findings": ("JUDGMENT_OR_BENCHMARK", "Slice designed around negated/contradicting results; benchmark measures surface relevance, not the contradiction workflow."),
    "exact_identifier": ("RANKING", "Slice designed around unambiguous entity retrieval; imperfection is ranking, not representation."),
    "neutral": ("RANKING", "Non-adversarial baseline; imperfection is ranking."),
}

INTERVENTION_HYPOTHESIS = {
    "SEMANTIC_GENERALIZATION": "candidate embedding MAY help here (the one category where representation change is a hypothesis worth testing)",
    "LEXICAL_PRECISION": "ranking/discrimination or hybrid lexical+semantic; a pure dense model typically does NOT fix lexical traps (hypothesis, not measured)",
    "AGENDA_MISMATCH": "structured/metadata/citation/multi-vector retrieval may help; does not, by itself, establish an embedding-capacity deficit",
    "EVIDENCE_GRANULARITY": "hierarchical paper->section->passage retrieval or evidence-unit construction may help; does not, by itself, establish an embedding-capacity deficit",
    "DIVERSITY": "diversity-aware ranking or source deduplication may help; does not, by itself, establish an embedding-capacity deficit",
    "RANKING": "reranking or rank-score calibration may help; does not, by itself, establish an embedding-capacity deficit",
    "JUDGMENT_OR_BENCHMARK": "benchmark revision or new product-grounded cases (P1D.2); not a retrieval-system change",
    "CANDIDATE_GENERATION": "broader candidate pool or recall expansion; representation-agnostic",
}


def assert_provenance():
    """Fail loudly if the benchmark or diagnostic has changed under us."""
    errors = []
    fp = compute_benchmark_v2_fingerprint()
    if fp != EXPECTED_BENCHMARK_FINGERPRINT:
        errors.append(f"benchmark fingerprint mismatch: expected {EXPECTED_BENCHMARK_FINGERPRINT}, got {fp}")

    n_total = len(ALL_CASES)
    if n_total != EXPECTED_TOTAL_CASES:
        errors.append(f"total cases: expected {EXPECTED_TOTAL_CASES}, got {n_total}")

    n_sel = sum(1 for c in ALL_CASES if c.split in ("calibration", "development"))
    n_held = sum(1 for c in ALL_CASES if c.split == "held_out")
    if n_sel != EXPECTED_SELECTION_CASES:
        errors.append(f"selection cases: expected {EXPECTED_SELECTION_CASES}, got {n_sel}")
    if n_held != EXPECTED_HELD_OUT_CASES:
        errors.append(f"held_out cases: expected {EXPECTED_HELD_OUT_CASES}, got {n_held}")

    n_judg = sum(len(c.judgments) for c in ALL_CASES)
    if n_judg != EXPECTED_JUDGMENTS:
        errors.append(f"judgments: expected {EXPECTED_JUDGMENTS}, got {n_judg}")

    cids = [c.case_id for c in ALL_CASES]
    if len(set(cids)) != len(cids):
        errors.append(f"case_ids not unique: {len(set(cids))} unique / {len(cids)} total")

    # Diagnostic file fingerprint
    diag_path = Path("docs/p1b_gate2/diagnostic_analysis.json")
    if not diag_path.exists():
        errors.append(f"diagnostic file missing: {diag_path}")
    else:
        diag = json.loads(diag_path.read_text(encoding="utf-8"))
        if diag.get("benchmark_fingerprint") != EXPECTED_BENCHMARK_FINGERPRINT:
            errors.append(f"diagnostic benchmark_fingerprint mismatch: expected {EXPECTED_BENCHMARK_FINGERPRINT}, got {diag.get('benchmark_fingerprint')}")
        if diag.get("snapshot_fingerprint") != EXPECTED_SNAPSHOT_FINGERPRINT:
            errors.append(f"diagnostic snapshot_fingerprint mismatch: expected {EXPECTED_SNAPSHOT_FINGERPRINT}, got {diag.get('snapshot_fingerprint')}")
        if diag.get("n_selection_cases") != EXPECTED_SELECTION_CASES:
            errors.append(f"diagnostic n_selection_cases: expected {EXPECTED_SELECTION_CASES}, got {diag.get('n_selection_cases')}")

    if errors:
        print("PROVENANCE ASSERTION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("Provenance assertions passed.")


def classify_observed(metrics, ceiling):
    """For SELECTION cases only: classify OBSERVED behavior from real metrics.

    Returns (observed_baseline_status, observed_failure_category_or_None, observed_rationale).
    observed_failure_category is NULL when the case is at ceiling (no failure observed)
    OR when metrics are unavailable (held-out).
    """
    legacy = metrics.get('legacy_ndcg10')
    perfect = ceiling.get('perfect')

    if legacy is None or perfect is None:
        return ("unavailable", None, "No per-policy metrics available (held_out case). Observed category cannot be assigned.")

    if perfect or (legacy is not None and legacy >= 0.999):
        return ("ceiling", None, f"lexical nDCG@10 = {legacy:.3f} (at ceiling). No observed baseline failure.")

    return ("non_ceiling", "SLICE_DESIGN_HYPOTHESIS_ONLY",
            "Non-ceiling selection case. The OBSERVED fact is that lexical is imperfect; the CAUSE is not measured per-case in the gate2 diagnostic. See slice_expected_failure_mode for the design hypothesis.")


def build_rows():
    diag = json.load(open('docs/p1b_gate2/diagnostic_analysis.json', encoding='utf-8'))
    ceiling_per_case = {r['case_id']: r for r in diag['section_4_lexical_ceiling']['per_case']}
    case_level = {r['case_id']: r for r in diag['section_1_case_level']['rows']}
    embed_per_case = {r['case_id']: r for r in diag['section_5_embedding_snapshot']['per_case']}

    rows = []
    for c in ALL_CASES:
        cid = c.case_id
        metrics = case_level.get(cid, {})
        ceiling = ceiling_per_case.get(cid, {})
        embed = embed_per_case.get(cid, {})
        in_selection = cid in case_level

        primary_fams, secondary_fams = SLICE_TO_FAMILIES.get(c.primary_slice, ([], []))
        slice_mode, slice_rationale = SLICE_EXPECTED_FAILURE_MODE[c.primary_slice]

        obs_status, obs_cat, obs_rationale = classify_observed(metrics, ceiling)

        row = {
            "case_id": cid,
            "slice": c.primary_slice,
            "secondary_slices": list(c.secondary_slices),
            "surface": c.ranking_surface,
            "domain": c.research_domain,
            "intent": c.ranking_intent,
            "split": c.split,
            "query_text": c.query_text,
            "task_families_primary": primary_fams,
            "task_families_secondary": secondary_fams,
            "n_candidates": len(c.candidates),
            "n_judgments": len(c.judgments),
            # classification basis (defect 2 fix)
            "classification_basis": "observed_selection_metrics" if in_selection else "slice_design_prior_only",
            "candidate_policy_metrics_available": in_selection,
            "observed_baseline_status": obs_status,
            "observed_failure_category": obs_cat,
            "observed_rationale": obs_rationale,
            # slice design prior (defect 3 fix - explicitly a hypothesis, not a measured cause)
            "slice_expected_failure_mode": slice_mode,
            "slice_design_rationale": slice_rationale,
            "intervention_hypothesis": INTERVENTION_HYPOTHESIS[slice_mode],
            # observed metrics (null for held-out)
            "legacy_ndcg10": metrics.get('legacy_ndcg10'),
            "semantic_only_ndcg10": metrics.get('semantic_ndcg10'),
            "hybrid_rrf_ndcg10": metrics.get('hybrid_rrf_ndcg10'),
            "hybrid_weighted_ndcg10": metrics.get('weighted_ndcg10'),
            "delta_semantic_vs_legacy": metrics.get('delta_semantic_vs_legacy'),
            "delta_rrf_vs_legacy": metrics.get('delta_rrf_vs_legacy'),
            "case_classification": metrics.get('classification'),
            "lexical_ceiling_perfect": ceiling.get('perfect'),
            "genuine_low_overlap_relevant": ceiling.get('genuine_low_overlap_relevant'),
            "embedding_sim_grade_rank_corr": embed.get('sim_grade_rank_corr'),
            "embedding_top_sim_grade": embed.get('top_sim_grade'),
        }
        rows.append(row)
    return rows, diag


def assert_schema(rows):
    """Every row conforms to the expected schema. Held-out observed categories are null."""
    required_keys = {
        "case_id", "slice", "classification_basis", "candidate_policy_metrics_available",
        "observed_baseline_status", "observed_failure_category", "slice_expected_failure_mode",
        "intervention_hypothesis",
    }
    errors = []
    for r in rows:
        missing = required_keys - set(r)
        if missing:
            errors.append(f"{r.get('case_id')}: missing keys {missing}")
        # defect 2 invariant: held-out cases MUST have null observed_failure_category
        if not r["candidate_policy_metrics_available"]:
            if r["observed_failure_category"] is not None:
                errors.append(f"{r['case_id']}: held-out case has non-null observed_failure_category '{r['observed_failure_category']}'")
            if r["observed_baseline_status"] != "unavailable":
                errors.append(f"{r['case_id']}: held-out case observed_baseline_status is '{r['observed_baseline_status']}', expected 'unavailable'")
    if errors:
        print("SCHEMA ASSERTION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)
    print("Schema assertions passed (held-out observed categories are null).")


def build_distribution(rows, diag):
    """Two SEPARATE distributions: observed (selection44) and case_design (all66).
    Never combine them (defect 2 fix)."""
    sel_rows = [r for r in rows if r["candidate_policy_metrics_available"]]
    held_rows = [r for r in rows if not r["candidate_policy_metrics_available"]]

    # OBSERVED distribution: only selection cases, split by ceiling vs non-ceiling.
    n_sel = len(sel_rows)
    n_ceiling = sum(1 for r in sel_rows if r["observed_baseline_status"] == "ceiling")
    n_non_ceiling = sum(1 for r in sel_rows if r["observed_baseline_status"] == "non_ceiling")
    # Of non-ceiling, how many have SEMANTIC_GENERALIZATION as their slice design hypothesis
    n_non_ceiling_semantic = sum(1 for r in sel_rows if r["observed_baseline_status"] == "non_ceiling" and r["slice_expected_failure_mode"] == "SEMANTIC_GENERALIZATION")

    # CASE-DESIGN distribution: all 66, by slice_expected_failure_mode (a design prior, not observed)
    design_counts = Counter(r["slice_expected_failure_mode"] for r in rows)

    fam_counts = Counter()
    for r in rows:
        for fam in r["task_families_primary"]:
            fam_counts[fam] += 1

    # Saturation arithmetic (defect 1 fix)
    legacy_macro = 0.9495
    gate_threshold = 0.03
    max_possible_gain = round(1.0 - legacy_macro, 4)
    non_ceiling_avg = round((legacy_macro - 0.5) / 0.5, 4)  # = 0.899
    needed_non_ceiling_for_gate = round(((legacy_macro + gate_threshold) - 0.5) / 0.5, 4)  # = 0.959
    required_improvement_non_ceiling = round(needed_non_ceiling_for_gate - non_ceiling_avg, 4)  # = +0.060

    dist = {
        "distribution_version": "p1d_failure_distribution_v1_1",
        "status": "draft",
        "revision": "P1D.1a - separates observed selection analysis from held-out design attribution; corrects 44-imperfect accounting; replaces causal claims with slice-informed hypotheses; corrects saturation arithmetic and wording per external review",
        "created": "2026-07-22",
        "authority": "P1D.1 - draft for user review. NOT frozen. No gate closed.",
        "source_data": {
            "benchmark_fingerprint": diag["benchmark_fingerprint"],
            "snapshot_fingerprint": diag["snapshot_fingerprint"],
            "n_cases_total": len(rows),
            "n_cases_selection_split": n_sel,
            "n_cases_held_out": len(held_rows),
            "per_case_observed_source": "docs/p1b_gate2/diagnostic_analysis.json sections 1,4,5 (selection split ONLY)",
        },
        "critical_separation_invariant": "observed_selection44 and case_design_all66 are reported SEPARATELY and never combined. The v1 '4/44 imperfect' aggregate is retracted: 2 of those 4 SEMANTIC_GENERALIZATION cases are held-out with no observed metrics.",
        "headline_metrics": {
            "lexical_macro_ndcg10_selection": legacy_macro,
            "lexical_recall20_selection": 1.0,
            "lexical_perfect_rate_selection_split": round(n_ceiling / n_sel, 4),
            "n_cases_lexical_perfect_selection": n_ceiling,
            "n_cases_lexical_non_ceiling_selection": n_non_ceiling,
            "semantic_only_macro_ndcg10_selection": 0.9321,
            "hybrid_rrf_macro_ndcg10_selection": 0.9561,
            "best_candidate_delta_vs_legacy": 0.0066,
            "frozen_gate_threshold": gate_threshold,
            "gate_verdict": "NO POLICY PASSES",
        },
        "saturation_arithmetic_corrected": {
            "claim_retracted": "v1 said the gate was 'arithmetically impossible' / the benchmark was at 'ceiling'. This was too strong.",
            "correct_arithmetic": {
                "max_mathematically_possible_macro_gain": max_possible_gain,
                "max_gain_interpretation": f"A candidate that scored perfectly on all 22 non-ceiling cases could reach at most +{max_possible_gain} macro. The +{gate_threshold} gate is therefore NOT arithmetically impossible.",
                "non_ceiling_selection_avg_legacy_ndcg10": non_ceiling_avg,
                "non_ceiling_avg_needed_for_+0.030_gate": needed_non_ceiling_for_gate,
                "required_improvement_on_non_ceiling_half": required_improvement_non_ceiling,
                "correct_wording": f"The benchmark is PARTIALLY saturated and gives the frozen macro gate limited power to detect improvements concentrated in a subset of workflows. A +{gate_threshold} gain remains mathematically possible but requires an average +{required_improvement_non_ceiling} improvement across the non-ceiling half without regression on the ceiling half.",
            }
        },
        "observed_failure_distribution_selection44": {
            "description": "OBSERVED behavior on the 44 selection cases ONLY. Held-out is excluded (no per-policy metrics).",
            "n_total": n_sel,
            "n_at_ceiling": n_ceiling,
            "n_non_ceiling": n_non_ceiling,
            "ceiling_rate": round(n_ceiling / n_sel, 4),
            "non_ceiling_semantic_generalization_design_hypothesis": n_non_ceiling_semantic,
            "non_ceiling_semantic_fraction": round(n_non_ceiling_semantic / n_non_ceiling, 4) if n_non_ceiling else None,
            "important_caveat": "For non-ceiling cases, the OBSERVED fact is that lexical is imperfect. The CAUSE is not measured per-case; slice_expected_failure_mode is a DESIGN HYPOTHESIS, not a measured diagnosis. 'Semantic generalization' here means 'the slice was designed to test semantic generalization AND lexical was observed imperfect on it' - it does NOT prove the imperfection was caused by a representation deficit.",
        },
        "case_design_distribution_all66": {
            "description": "CASE-DESIGN attribution for ALL 66 cases, by slice_expected_failure_mode. This is a design prior (what each slice was built to exercise), NOT an observed measurement of cause. Held-out cases appear here by design; their observed behavior is unknown.",
            "n_total": len(rows),
            "counts_by_expected_failure_mode": dict(design_counts.most_common()),
        },
        "embedding_relevance_signal_SOFTENED": {
            "v1_claim_retracted": "v1 said the other 91% of imperfect cases were 'failures none of which a larger embedding addresses'. This was too strong: a better embedding COULD affect ranking or agenda discrimination.",
            "correct_claim": "The current evidence establishes only that the non-SEMANTIC_GENERALIZATION categories do not, BY THEMSELVES, establish an embedding-capacity deficit. They do not rule out that an embedding could help indirectly (e.g., via ranking or agenda discrimination). The honest reading: the historical data does not isolate embedding capacity as the DOMINANT bottleneck, but does not exonerate it either.",
            "semantic_generalization_design_hypothesis_count_selection_non_ceiling": n_non_ceiling_semantic,
            "fraction_of_non_ceiling_selection": round(n_non_ceiling_semantic / n_non_ceiling, 4) if n_non_ceiling else None,
        },
        "task_family_coverage_all66": dict(sorted(fam_counts.items(), key=lambda x: -x[1])),
    }
    return dist


def main():
    assert_provenance()
    rows, diag = build_rows()
    assert_schema(rows)

    out_jsonl = Path("data/retrieval/p1d_historical_failure_analysis.jsonl")
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with open(out_jsonl, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f"Wrote {len(rows)} cases to {out_jsonl}")

    dist = build_distribution(rows, diag)
    out_dist = Path("data/retrieval/p1d_failure_distribution.json")
    with open(out_dist, 'w', encoding='utf-8') as f:
        json.dump(dist, f, indent=2, ensure_ascii=False)
    print(f"Wrote distribution to {out_dist}")

    # Summary
    sel = [r for r in rows if r["candidate_policy_metrics_available"]]
    n_non_ceiling = sum(1 for r in sel if r["observed_baseline_status"] == "non_ceiling")
    n_sem = sum(1 for r in sel if r["observed_baseline_status"] == "non_ceiling" and r["slice_expected_failure_mode"] == "SEMANTIC_GENERALIZATION")
    print()
    print("=== OBSERVED selection44 (defect 2 fix) ===")
    print(f"  selection cases: {len(sel)}")
    print(f"  at ceiling (no observed failure): {sum(1 for r in sel if r['observed_baseline_status']=='ceiling')}")
    print(f"  non-ceiling (lexical imperfect): {n_non_ceiling}")
    print(f"  of non-ceiling, SEMANTIC_GENERALIZATION design hypothesis: {n_sem}")
    print(f"  fraction: {n_sem}/{n_non_ceiling} = {n_sem/n_non_ceiling:.3f}")
    print()
    print("=== CASE-DESIGN all66 (defect 3 fix - design priors, not measured causes) ===")
    design = Counter(r["slice_expected_failure_mode"] for r in rows)
    for cat, n in design.most_common():
        print(f"  {cat}: {n}")


if __name__ == '__main__':
    main()
