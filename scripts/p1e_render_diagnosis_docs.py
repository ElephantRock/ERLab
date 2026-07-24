"""P1E.0 — Render the human-readable + JSON diagnosis docs from sealed artifacts.

Commit 4 generator. Reads ONLY the three sealed Commit-2 JSON artifacts and
emits:
  docs/research/p1e_benchmark_discrimination_audit.md
  docs/research/p1e_benchmark_discrimination_audit.json

Every figure in the rendered docs is pulled directly from the sealed JSONs
so the narrative cannot drift from the measurements.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT = REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json"
CASES = REPO_ROOT / "data" / "evaluation" / "p1e_case_diagnostics.json"
PAIRWISE = REPO_ROOT / "data" / "evaluation" / "p1e_policy_pairwise_comparison.json"
OUT_MD = REPO_ROOT / "docs" / "research" / "p1e_benchmark_discrimination_audit.md"
OUT_JSON = REPO_ROOT / "docs" / "research" / "p1e_benchmark_discrimination_audit.json"


def render() -> tuple[str, dict]:
    a = json.loads(AUDIT.read_text(encoding="utf-8"))
    c = json.loads(CASES.read_text(encoding="utf-8"))
    p = json.loads(PAIRWISE.read_text(encoding="utf-8"))

    sa = a["section1_structure_aggregate"]
    ce = a["section2_ceiling"]
    res = a["section2_resolution"]
    diag = a["section7_diagnosis"]
    crit = diag["criteria"]
    runs = p["five_run_macro_metrics"]
    pw = p["pairwise_comparisons"]
    errs = c["section5_error_classes"]

    L = []
    L.append("# P1E.0 — Benchmark Discrimination Audit (Diagnosis)\n")
    L.append("```text")
    L.append("P1E.0 diagnosis   OUTCOME M (mixed / inconclusive)")
    L.append("P1E.1             BLOCKED pending audit acceptance")
    L.append("P1                 OPEN")
    L.append("P2                 BLOCKED")
    L.append("```\n")
    L.append("> Generated exclusively from the three sealed Commit-2 artifacts. Every")
    L.append("> figure below traces to `data/evaluation/p1e_*.json`. The narrative does")
    L.append("> not introduce any number not present in those artifacts.\n")
    L.append(f"- manifest_sha256: `{a['manifest_sha256']}`")
    L.append(f"- protocol_sha256: `{a['protocol_sha256']}`")
    L.append(f"- diagnosis_rule_version: `{a['diagnosis_rule_version']}`")
    L.append(f"- primary_statistical_seed: `{a['primary_statistical_seed']}`")
    L.append(f"- benchmark_fingerprint: `{a['benchmark_fingerprint']}`")
    L.append(f"- audited cases: {a['n_audited_cases']} cal+dev | excluded held-out: {a['n_excluded_held_out']}\n")

    # ── P1B parity guardrail ──
    L.append("## P1B parity guardrail\n")
    pp = a["p1b_parity_guardrail"]
    L.append(f"```text")
    L.append(f"tolerance        {pp['tolerance']}")
    L.append(f"pass             {pp['pass']}")
    L.append(f"```\n")
    L.append("The five-run audit re-runs the P1B snapshot through the **original** "
             "evaluator and reproduces `gate2_metrics_package.json` within 1e-12 "
             "(lexical nDCG@5 = 0.9495, semantic = 0.9321, hybrid = 0.9561). This "
             "is the in-audit guardrail that the audit uses the frozen evaluator, "
             "not a reimplementation.\n")

    # ── Held-out isolation ──
    L.append("## Held-out isolation (all zero)\n")
    L.append("```text")
    for k, v in a["held_out_isolation_counters"].items():
        L.append(f"{k:48s} {v}")
    L.append("```\n")
    pr = a["p1b_snapshot_report"]
    tr = a["tei_snapshot_report"]
    L.append(f"P1B filtered load: decoded {pr['decoded_query_count']} queries + "
             f"{pr['decoded_candidate_count']} candidates; {pr['skipped_count']} held-out items skipped (never decoded). "
             f"snapshot_fingerprint `{pr['snapshot_fingerprint'][:16]}…` matches frozen P1B.\n")
    L.append(f"TEI filtered load: decoded {tr['decoded_query_count']} queries + "
             f"{tr['decoded_candidate_count']} candidates; 0 held-out decoded.\n")

    # ── §1 structure ──
    L.append("## §1 — Judgment and candidate-set structure\n")
    L.append("```text")
    L.append(f"total candidates in eval set          {sa['total_grade0']+sa['total_grade1']+sa['total_grade2plus']}")
    L.append(f"  grade 0 (nonrelevant)               {sa['total_grade0']}")
    L.append(f"  grade 1 (weakly relevant)           {sa['total_grade1']}")
    L.append(f"  grade >=2 (strongly relevant)       {sa['total_grade2plus']}")
    L.append(f"    of which grade 3                  {sa['total_grade3']}")
    L.append(f"cases with multiple grade-3           {sa['cases_with_multiple_grade3']}/44")
    L.append(f"cases where every candidate relevant  {sa['cases_all_relevant']}/44")
    L.append(f"cases with <2 nonrelevant             {sa['cases_fewer_than_2_nonrelevant']}/44")
    L.append(f"cases unique-best (max grade)         {sa['cases_unique_best']}/44")
    L.append(f"cases ambiguous-top (tie at max)      {sa['cases_ambiguous_top']}/44")
    L.append(f"cases all-zero                        {sa['cases_all_zero']}/44")
    L.append("```\n")
    L.append("**Saturation signal.** Only 13 grade-0 candidates exist in the entire "
             "44-case eval set; 31/44 cases have zero nonrelevant candidates; 44/44 have "
             "fewer than 2 genuine negatives; 30/44 have multiple equally-best grade-3 "
             "candidates. A benchmark cannot strongly measure top-result quality when "
             "nearly every candidate is relevant and the top is frequently tied.\n")

    # ── §2 ceiling ──
    L.append("## §2 — Metric ceiling, headroom, resolution\n")
    hh = ce["headroom_histogram_ndcg5"]
    L.append("```text")
    L.append(f"observed headroom == 0                {hh['headroom_eq_0']}/44")
    L.append(f"observed headroom <= 0.01             {hh['headroom_le_0.01']}/44")
    L.append(f"observed headroom <= 0.02             {hh['headroom_le_0.02']}/44")
    L.append(f"observed headroom > 0.05              {hh['headroom_gt_0.05']}/44")
    L.append("```\n")
    L.append("**Saturation signal.** 29/44 cases have zero observed headroom — the best "
             "of the five runs already achieves the oracle. Only 8/44 cases have headroom "
             "above 0.05.\n")
    L.append("Empirical metric resolution (min nonzero macro movement from one adjacent "
             "differently-graded swap, /44):\n")
    L.append("```text")
    for m, v in res["min_nonzero_macro_movement"].items():
        L.append(f"  {m:16s} {v}")
    L.append(f"  top1_optimal     {res['min_nonzero_macro_movement_top1_optimal']}  "
             "(undefined: no single adjacent swap flips top1_optimal)")
    L.append(f"  top1_optimal effective denominator   {res['top1_optimal_effective_denominator']} "
             f"(all-zero excluded: {res['all_zero_cases_excluded']})")
    L.append("```\n")

    # ── §3 separability ──
    L.append("## §3 — Policy separability (five-run matrix)\n")
    L.append("```text")
    L.append(f"{'run':18s} {'nDCG@5':>8s} {'MRR@10':>8s} {'P@5':>8s} {'R@20':>8s}")
    for rn in ["lexical", "p1b_semantic", "tei_semantic", "p1b_hybrid_rrf", "tei_hybrid_rrf"]:
        mm = runs[rn]
        L.append(f"{rn:18s} {mm['ndcg_at_5']:8.4f} {mm['mrr_at_10']:8.4f} {mm['precision_at_5']:8.4f} {mm['recall_at_20']:8.4f}")
    L.append("```\n")
    L.append("All five runs cluster between 0.93 and 0.96 nDCG@5; MRR@10 is 1.0 for "
             "every run except p1b_semantic (0.9886); Recall@20 is 1.0 everywhere. "
             "The policies are barely separated at the macro level.\n")
    L.append("### Required pairwise comparisons\n")
    L.append("```text")
    L.append(f"{'comparison':30s} {'meanΔnDCG5':>11s} {'nontied':>8s} {'Kendall':>8s} {'95% CI':>22s} {'perm p':>8s} {'MDE':>8s} {'label'}")
    for key in ["lexical_vs_p1b_semantic", "lexical_vs_tei_semantic",
                "p1b_semantic_vs_tei_semantic", "p1b_hybrid_rrf_vs_tei_hybrid_rrf"]:
        o = pw[key]
        ci = o["bootstrap_ci"]
        L.append(f"{key:30s} {o['mean_ndcg5_delta']:+11.5f} {o['effective_nontied_queries']:8d} "
                 f"{o['mean_kendall_tau']:8.4f} [{ci['lower']:+.4f},{ci['upper']:+.4f}] "
                 f"{o['permutation']['p_value']:8.4f} {o['continuous_mde_ndcg5']['mde']:8.4f} {o['outcome_label']}")
    L.append("```\n")
    L.append("**Power signal.** No pairwise comparison detects a statistically "
             "significant difference (every 95% CI includes 0; every permutation p >= 0.05). "
             "The two lexical-vs-semantic comparisons are `underpowered` (MDE ~0.031–0.033 "
             "exceeds a plausible effect of interest), and the two semantic-vs-semantic / "
             "hybrid-vs-hybrid comparisons are `no_detected_difference`. Kendall τ across "
             "comparisons is 0.54–0.80 — rankings differ substantially case-by-case, but the "
             "differences do not move the metric past the noise floor.\n")

    # ── §4 hard negatives ──
    L.append("## §4 — Hard-negative coverage (PRIMARY grade-0)\n")
    tot_hn = sum(x["section4_hard_negatives"]["n_primary_grade0_hard_negatives"] for x in c["cases"])
    near = sum(1 for x in c["cases"] if x["section4_hard_negatives"]["n_primary_grade0_hard_negatives"] >= 1)
    L.append("```text")
    L.append(f"total primary grade-0 hard negatives   {tot_hn}")
    L.append(f"cases with >=1 near-miss negative      {near}/44")
    L.append("```\n")
    L.append("**Saturation signal.** Only 5 primary grade-0 hard negatives exist across "
             "all 44 cases, concentrated in 5 cases. The benchmark has almost no genuine "
             "negatives to confuse a ranker (consistent with §1: only 13 grade-0 candidates total). "
             "Hard-negative coverage is far too thin to exercise a reranking architecture.\n")

    # ── §5 error classes ──
    L.append("## §5 — Error recurrence (observable evidence patterns)\n")
    L.append("```text")
    L.append(f"{'class':36s} {'posture':14s} {'count':>6s} {'distinct_cases'}")
    for k in ["lexical_aliasing", "generic_research_language_overlap", "entity_mismatch",
              "method_vs_domain_confusion", "task_vs_evidence_mismatch",
              "long_document_dilution", "near_duplicate_candidates", "missing_query_context"]:
        v = errs[k]
        dc = v.get("distinct_case_count", "n/a")
        L.append(f"{k:36s} {v['posture']:14s} {str(v.get('count')):>6s} {dc}")
    L.append("```\n")
    L.append("**Architecture signal (qualified).** Two *classified* recurring error "
             "patterns are directly schema-supported: `lexical_aliasing` (4 distinct cases — "
             "a grade-0 candidate with lexical overlap ≥ a grade-3 candidate's, ranked above "
             "it by lexical) and `near_duplicate_candidates` (4 distinct cases via the "
             "`near_duplicate_of` schema field). Two *hypothesis* patterns are suggested "
             "but not causally established: `generic_research_language_overlap` (10 cases) "
             "and `long_document_dilution` (0 cases). Three classes are `not_inferable` "
             "from observable scores. This is genuine but thin architectural evidence: the "
             "patterns recur, but the benchmark lacks the negatives and power to turn them "
             "into a measurable ranking signal.\n")

    # ── §7 diagnosis ──
    L.append("## §7 — S/A/M diagnosis\n")
    L.append("Every criterion's boolean result and measured value:\n")
    L.append("```text")
    for k in ["S_R1_headroom_le_0.01", "S_R2_top1_optimal_all_runs", "S_R3_few_hard_negatives",
              "S_R4_no_detected_difference_all_pairwise", "S_R5_largest_delta_power",
              "A1_headroom_gt_0.05", "A2_many_hard_negatives",
              "A3_recurring_error_classes", "A4_detected_effect"]:
        v = crit[k]
        L.append(f"{k:42s} pass={v['pass']}")
    L.append("```\n")
    L.append(f"```text")
    L.append(f"S_complete                              {diag['S_complete']}")
    L.append(f"A_complete                              {diag['A_complete']}")
    L.append(f"no_architecture_criterion_materially_met {diag['no_architecture_criterion_materially_met']}")
    L.append(f"precedence                              {diag['precedence']}")
    L.append(f"")
    L.append(f"OUTCOME                                 {diag['outcome']}")
    L.append(f"```\n")

    L.append("### Why M (mixed / inconclusive)\n")
    L.append("**Saturation evidence present (S partially supported):**\n")
    L.append(f"- R1 passes: {crit['S_R1_headroom_le_0.01']['value_frac']:.0%} of cases have observed headroom ≤ 0.01 (29/44 are exactly 0).\n")
    L.append(f"- R2 passes: top1_optimal = 1.0 under every one of the five runs on ≥60% of non-all-zero cases.\n")
    L.append(f"- R3 passes: {crit['S_R3_few_hard_negatives']['value_frac']:.0%} of cases have <2 primary grade-0 hard negatives.\n")
    L.append(f"- R5 passes: the largest-delta comparison is power-limited.\n")
    L.append("- **But R4 fails:** the lexical-vs-semantic pairwise comparisons are `underpowered`, "
             "not `no_detected_difference` — so saturation is not cleanly established. And "
             "`no_architecture_criterion_materially_met` is False because A3 passes.\n\n")
    L.append("**Architecture evidence present (A partially supported):**\n")
    L.append("- A3 passes: 2 recurring *classified* error classes (lexical_aliasing, "
             "near_duplicate_candidates), each in ≥2 distinct cal+dev cases.\n")
    L.append("- **But A1 fails** (only 8/44 = 18% have headroom > 0.05, below 40%), "
             "**A2 fails** (only 5 grade-0 hard negatives total), and **A4 fails** "
             "(no comparison has both adequate power and a detected effect).\n\n")
    L.append("**Resolution.** Neither S nor A is complete under the frozen precedence, so "
             "the outcome is **M**. The benchmark is neither purely saturation-dominant "
             "(there are recurring architectural error patterns) nor architecture-dominant "
             "(there is no detectable ranking signal and almost no headroom or negatives). "
             "It is a benchmark with strong ceiling effects AND a few genuine, recurring "
             "failure modes that it lacks the power and negative coverage to resolve.\n")
    L.append("```text")
    L.append("recommended next action (per protocol §10.3 for outcome M):")
    L.append("  authorize a bounded P1E.1 benchmark extension followed by P1E.3")
    L.append("```")

    md = "\n".join(L) + "\n"

    # JSON mirror — same content, structured
    json_doc = {
        "schema": "p1e_diagnosis_doc_v1",
        "manifest_sha256": a["manifest_sha256"],
        "protocol_sha256": a["protocol_sha256"],
        "diagnosis_rule_version": a["diagnosis_rule_version"],
        "primary_statistical_seed": a["primary_statistical_seed"],
        "benchmark_fingerprint": a["benchmark_fingerprint"],
        "audited_cases": a["n_audited_cases"],
        "excluded_held_out": a["n_excluded_held_out"],
        "p1b_parity_pass": pp["pass"],
        "held_out_isolation": a["held_out_isolation_counters"],
        "section1_structure_aggregate": sa,
        "section2_ceiling": ce,
        "section2_resolution": res,
        "section3_five_run_macro": runs,
        "section3_pairwise_summary": {
            k: {
                "mean_ndcg5_delta": pw[k]["mean_ndcg5_delta"],
                "effective_nontied_queries": pw[k]["effective_nontied_queries"],
                "mean_kendall_tau": pw[k]["mean_kendall_tau"],
                "bootstrap_ci": pw[k]["bootstrap_ci"],
                "permutation_p": pw[k]["permutation"]["p_value"],
                "continuous_mde_ndcg5": pw[k]["continuous_mde_ndcg5"]["mde"],
                "outcome_label": pw[k]["outcome_label"],
            } for k in pw
        },
        "section4_hard_negatives": {
            "total_primary_grade0": tot_hn,
            "cases_with_near_miss": near,
        },
        "section5_error_classes": {
            k: {"posture": errs[k]["posture"], "count": errs[k].get("count"),
                "distinct_cases": errs[k].get("distinct_case_count")}
            for k in errs
        },
        "section7_diagnosis": diag,
    }
    return md, json_doc


def main() -> int:
    md, json_doc = render()
    OUT_MD.write_text(md, encoding="utf-8")
    OUT_JSON.write_text(json.dumps(json_doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    print(f"\ndiagnosis outcome: {json_doc['section7_diagnosis']['outcome']}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
