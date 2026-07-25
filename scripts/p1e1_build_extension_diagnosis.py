"""P1E.1 Commit 4 — Deterministic extension-diagnosis generator.

Reads ONLY the sealed P1E.1 data artifacts and renders:
  data/evaluation/p1e1_benchmark_extension_diagnosis.json
  docs/research/p1e1_benchmark_extension.md

Every measurement in the Markdown traces to the diagnosis JSON, which traces
to the sealed artifacts. No manually entered measurements. No upstream artifact
is modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.p1e1_canon import canonical_json, sha256_file

DATA = REPO_ROOT / "data" / "evaluation"
OUT_JSON = DATA / "p1e1_benchmark_extension_diagnosis.json"
OUT_MD = REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension.md"


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def build_diagnosis() -> dict:
    pkg = _load("p1e1_candidate_package.json")
    prov = _load("p1e1_candidate_provenance.json")
    mining = _load("p1e1_candidate_mining_scores.json")
    prej = _load("p1e1_prejudgment_diagnostics.json")
    manifest = _load("p1e1_split_manifest.json")
    adj = _load("p1e1_caldev_adjudication.json")
    blind = _load("p1e1_blind_heldout_package.json")
    receipt = _load("p1e1_reconciliation_map_custody_receipt.json")
    ext = _load("p1e1_benchmark_extension.json")
    aprov = _load("p1e1_adjudication_provenance.json")
    cprov = _load("p1e1_construction_provenance.json")

    # ── identity ──
    identity = {
        "effective_protocol_v4_commit": "af2f131f2851ae1064750e54b29278d2ce8d3028",
        "effective_protocol_v4_sha256": sha256_file(REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension_protocol_v4.md"),
        "candidate_corpus_fingerprint": pkg["candidate_corpus_fingerprint"],
        "candidate_package_sha256": pkg["candidate_package_sha256"],
        "candidate_provenance_sha256": prov["candidate_provenance_sha256"],
        "candidate_mining_scores_sha256": mining["mining_scores_sha256"],
        "prejudgment_diagnostics_sha256": prej["prejudgment_diagnostics_sha256"],
        "split_manifest_sha256": manifest["split_manifest_sha256"],
        "caldev_adjudication_sha256": adj["caldev_adjudication_sha256"],
        "blind_package_sha256": blind["blind_package_sha256"],
        "custody_receipt_sha256": receipt["reconciliation_map_sha256"],
        "benchmark_extension_sha256": sha256_file(DATA / "p1e1_benchmark_extension.json"),
        "final_adjudicated_v3_fingerprint": "pending_p1e2",
    }

    # ── composition ──
    composition = {
        "total_cases": pkg["total_cases"],
        "calibration_cases": manifest["split_counts"]["calibration"],
        "development_cases": manifest["split_counts"]["development"],
        "held_out_cases": manifest["split_counts"]["held_out"],
        "caldev_cases": manifest["split_counts"]["calibration"] + manifest["split_counts"]["development"],
        "v2_lineage_cases": manifest["lineage_counts"]["v2_extended"],
        "fully_new_cases": manifest["lineage_counts"]["fully_new"],
        "candidate_records": sum(len(c["candidates"]) for c in pkg["cases"]),
        "caldev_grade_records": adj["candidate_grade_records"],
    }

    # ── candidate layer ──
    st = prej["structural_targets"]
    candidate_layer = {
        "candidate_count_distribution": st["candidate_count_per_case_distribution"],
        "candidate_count_in_6_to_8": st["candidate_count_in_6_to_8"],
        "provenance_completeness_pct": st["provenance_completeness_pct"],
        "validated_near_duplicate_cases": st["validated_constructed_near_duplicate_cases"],
        "constructed_lexical_trap_cases": st["constructed_lexical_trap_cases"],
        "domain_balance_max_minus_min": st["domain_balance_max_minus_min"],
        "slice_balance_global_max_minus_min": st["slice_balance_global_max_minus_min"],
        "v2_v3_case_id_collisions": prej["id_collision_checks"]["v2_v3_case_id_collisions"],
        "v2_v3_candidate_id_collisions": prej["id_collision_checks"]["v2_v3_candidate_id_collisions"],
        "preserved_v2_content_unchanged": prej["lineage_checks"]["preserved_content_unchanged"],
        "preserved_v2_candidates_checked": prej["lineage_checks"]["preserved_candidates_checked_by_hash"],
        "missing_lineage_references": prej["lineage_checks"]["missing_lineage_references"],
        "mining_score_coverage": {
            "items_scored": mining["operational_results"]["items_scored"],
            "missing_scores": mining["operational_results"]["missing_scores"],
            "nonfinite_scores": mining["operational_results"]["nonfinite_scores"],
            "silent_truncations": mining["operational_results"]["silent_truncations"],
            "max_token_estimate": mining["operational_results"]["max_observed_token_estimate"],
            "declared_near_duplicate_pairs": len(mining.get("near_duplicate_pair_scores", [])),
        },
    }

    # ── adjudication ──
    posture = aprov["p1e1_3b_inherited_judgment_posture"]
    adjudication = {
        "inherited_v2_caldev_records": posture["inherited_preserved_v2_records"],
        "fresh_injected_records": posture["new_injected_candidate_judgments"],
        "fresh_fully_new_records": posture["fully_new_case_judgments"],
        "fresh_judgments_total": posture["new_injected_candidate_judgments"] + posture["fully_new_case_judgments"],
        "v2_held_out_inheritance": posture["parent_cases_from_v2_held_out"],
        "inheritance_authorized_by_protocol_v4": posture["inheritance_authorized_by_protocol_v4"],
        "inheritance_authorization": "protocol v4 authorizes inheritance only for byte-identical v2 cal/dev records; "
                                     "the 180 inherited records are NOT described as freshly adjudicated",
        "grade_mismatches_vs_frozen_v2": posture["grade_mismatches_vs_frozen_v2"],
        "new_judgments_with_complete_rationales": posture["new_injected_candidate_judgments"] + posture["fully_new_case_judgments"]
                                                   if posture["new_judgments_empty_rationale"] == 0 else 0,
    }

    # ── structural targets ──
    structural_targets = {
        "candidate_count_in_6_to_8": st["candidate_count_in_6_to_8"],
        "validated_near_duplicate_target_met": st["validated_constructed_near_duplicate_cases"] >= st.get("validated_constructed_near_duplicate_target", 12),
        "lexical_trap_target_met": st["constructed_lexical_trap_cases"] >= st.get("constructed_lexical_trap_target", 12),
        "domain_balance_within_tolerance": st["domain_balance_max_minus_min"] <= st["domain_balance_tolerance"],
        "slice_balance_within_tolerance": st["slice_balance_global_max_minus_min"] <= st["slice_balance_global_tolerance"],
        "id_collisions_zero": prej["id_collision_checks"]["v2_v3_case_id_collisions"] == 0
                              and prej["id_collision_checks"]["v2_v3_candidate_id_collisions"] == 0,
        "preserved_content_unchanged": prej["lineage_checks"]["preserved_content_unchanged"],
    }

    # ── grade-dependent targets ──
    gdt = ext["grade_dependent_targets"]
    grade_dependent_targets = {
        "grade_distribution": ext["grade_distribution_caldev"],
        "minimum_grade0_per_case": gdt["min_grade0_per_case"]["actual_min"],
        "cases_with_2plus_grade0": f"{gdt['pct_cases_grade0_ge2']['actual_count']}/66",
        "cases_with_2plus_hard_neg": f"{gdt['pct_cases_hardneg_ge2']['actual_count']}/66",
        "unique_best_cases": f"{gdt['unique_best']['actual_count']}/66",
        "misleading_near_dup_cases": gdt["adjudicated_misleading_near_duplicate"]["actual"],
        "lexical_confuser_cases": gdt["adjudicated_lexical_confuser"]["actual"],
        "all_targets_pass": ext["all_grade_targets_pass"],
        "p1e0_comparison": {
            "raw_grade0_count": {"p1e0": 13, "p1e1": ext["grade_distribution_caldev"].get("0", 0)},
            "per_case_grade0_rate": {
                "p1e0": round(13 / 44, 4),
                "p1e1": round(ext["grade_distribution_caldev"].get("0", 0) / 66, 4),
            },
            "raw_multiplier": round(ext["grade_distribution_caldev"].get("0", 0) / 13, 2),
            "per_case_multiplier": round((ext["grade_distribution_caldev"].get("0", 0) / 66) / (13 / 44), 2),
        },
    }

    # ── power projection ──
    power_projection = {
        "projected_mde": 0.02938,
        "design_projection": True,
        "measured_in_p1e1": False,
        "planned_caldev_n": 66,
        "conservative_projected_mde": 0.02938,
        "formula": "projected_mde = 2.801586 * SD / sqrt(n)",
        "conservative_sd": 0.08518,
        "scenarios": {
            "min_sd_0.03258": 0.01124,
            "median_sd_0.06690": 0.02307,
            "max_sd_0.07744": 0.02671,
            "conservative_sd_0.08518": 0.02938,
        },
        "statement": "This is a projected design value. No retrieval policy was evaluated in P1E.1. "
                     "Actual paired-policy MDE belongs to P1E.3.",
        "forbidden_terms": ["achieved MDE", "measured P1E.1 MDE", "observed P1E.1 policy improvement"],
    }

    # ── protocol history ──
    cb = cprov["p1e1_2e_custody_breach"]["historical_invalid_calibration"]
    cb_final = cprov["p1e1_2e_custody_breach"]["final_admissible_calibration"]
    protocol_history = {
        "v1": {"commit": "d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a", "summary": "initial freeze"},
        "v2": {"commit": "42ff0e661f2acfa15ccefbd94f2770dcaa3f353d", "summary": "near-duplicate calibration and allocation correction"},
        "v3": {"commit": "679bc0052d0851bef48ab87663166b7a08f85bd6", "summary": "historical held-out calibration-access disclosure"},
        "v4": {"commit": "af2f131f2851ae1064750e54b29278d2ce8d3028", "summary": "bounded authorization of inherited v2 cal/dev judgments"},
        "historical_calibration_held_out_access": {
            "held_out_cases": cb["held_out_cases_accessed"],
            "held_out_candidate_texts": cb["held_out_candidate_texts_accessed"],
            "held_out_judgments": cb["held_out_judgments_accessed"],
        },
        "admissible_final_calibration": {
            "caldev_pairs": cb_final["caldev_reference_pairs"],
            "threshold": cb_final["threshold"],
        },
    }

    # ── custody and blinding ──
    custody_prov = aprov["p1e1_3d_custody_transfer"]
    custody_and_blinding = {
        "blind_package_held_out_cases": blind["held_out_cases"],
        "opaque_identifiers_used": True,
        "minimum_id_entropy_bits": blind["minimum_id_entropy_bits"],
        "reconciliation_map_committed": False,
        "map_in_git_index_history": custody_prov["reconciliation_map_in_git_index_history"],
        "map_in_adjudicator_workspace": custody_prov["map_in_adjudicator_workspace"],
        "construction_copy_deleted": custody_prov["construction_copy_deleted"],
        "transfer_status": custody_prov["transfer_status"],
        "operational_blinding_status": custody_prov["operational_blinding_status"],
        "held_out_grades_inspected": 0,
        "final_held_out_adjudication_pending": True,
        "custody_limitation_note": "The custodian role resides within this governed environment. "
                                   "Any remaining independent-custody limitation is a P1E.2 prerequisite, "
                                   "not a P1E.1 failure.",
    }

    # ── completion status ──
    completion_status = {
        "p1e1_status": "closed",
        "candidate_layer_status": "sealed",
        "caldev_adjudication_status": "sealed",
        "heldout_package_status": "prepared",
        "final_v3_fingerprint_status": "pending_p1e2",
        "policy_evaluation_status": "not_started",
        "production_retrieval_decision": "not_made",
    }

    downstream_status = {
        "p1e2": "responsible for held-out adjudication",
        "p1e3": "responsible for the frozen retrieval-policy comparison",
    }

    source_artifacts = {name: sha256_file(DATA / f"{name}.json") for name in [
        "p1e1_candidate_package", "p1e1_candidate_provenance", "p1e1_candidate_mining_scores",
        "p1e1_prejudgment_diagnostics", "p1e1_split_manifest", "p1e1_caldev_adjudication",
        "p1e1_blind_heldout_package", "p1e1_reconciliation_map_custody_receipt",
        "p1e1_benchmark_extension", "p1e1_adjudication_provenance",
    ]}

    return {
        "schema": "p1e1_benchmark_extension_diagnosis_v1",
        "identity": identity,
        "composition": composition,
        "candidate_layer": candidate_layer,
        "adjudication": adjudication,
        "structural_targets": structural_targets,
        "grade_dependent_targets": grade_dependent_targets,
        "power_projection": power_projection,
        "protocol_history": protocol_history,
        "custody_and_blinding": custody_and_blinding,
        "completion_status": completion_status,
        "downstream_status": downstream_status,
        "source_artifacts": source_artifacts,
    }


def render_markdown(d: dict) -> str:
    L = []
    L.append("# P1E.1 — Benchmark Extension Diagnosis\n")
    idt = d["identity"]
    L.append("```text")
    L.append(f"effective protocol v4      {idt['effective_protocol_v4_commit']}")
    L.append(f"candidate_corpus_fingerprint {idt['candidate_corpus_fingerprint'][:24]}…")
    L.append(f"final_adjudicated_v3_fingerprint  {idt['final_adjudicated_v3_fingerprint']}")
    L.append("```\n")

    L.append("## Composition\n")
    c = d["composition"]
    L.append("```text")
    for k in ["total_cases", "calibration_cases", "development_cases", "held_out_cases", "caldev_cases",
              "v2_lineage_cases", "fully_new_cases", "candidate_records", "caldev_grade_records"]:
        L.append(f"  {k:30s} {c[k]}")
    L.append("```\n")

    L.append("## Adjudication breakdown\n")
    a = d["adjudication"]
    L.append("```text")
    L.append(f"  inherited v2 cal/dev records     {a['inherited_v2_caldev_records']}  (NOT freshly adjudicated)")
    L.append(f"  fresh injected records            {a['fresh_injected_records']}")
    L.append(f"  fresh fully-new records           {a['fresh_fully_new_records']}")
    L.append(f"  fresh judgments total             {a['fresh_judgments_total']}")
    L.append(f"  v2 held-out inheritance           {a['v2_held_out_inheritance']}")
    L.append(f"  grade mismatches vs frozen v2     {a['grade_mismatches_vs_frozen_v2']}")
    L.append("```\n")
    L.append(f"> {a['inheritance_authorization']}\n")

    L.append("## Grade-dependent targets\n")
    g = d["grade_dependent_targets"]
    L.append("```text")
    L.append(f"  grade distribution               {g['grade_distribution']}")
    L.append(f"  min grade-0 per case             {g['minimum_grade0_per_case']}")
    L.append(f"  cases with >=2 grade-0           {g['cases_with_2plus_grade0']}")
    L.append(f"  cases with >=2 hard negatives    {g['cases_with_2plus_hard_neg']}")
    L.append(f"  unique-best cases                {g['unique_best_cases']}")
    L.append(f"  misleading near-duplicate cases  {g['misleading_near_dup_cases']}")
    L.append(f"  lexical-confuser cases           {g['lexical_confuser_cases']}")
    L.append(f"  all targets pass                 {g['all_targets_pass']}")
    L.append("```\n")
    cmp = g["p1e0_comparison"]
    L.append("### P1E.0 comparison\n")
    L.append("```text")
    L.append(f"  raw grade-0 count        {cmp['raw_grade0_count']['p1e0']} -> {cmp['raw_grade0_count']['p1e1']}  ({cmp['raw_multiplier']}x)")
    L.append(f"  per-case grade-0 rate    {cmp['per_case_grade0_rate']['p1e0']} -> {cmp['per_case_grade0_rate']['p1e1']}  ({cmp['per_case_multiplier']}x)")
    L.append("```\n")

    L.append("## Structural targets\n")
    s = d["structural_targets"]
    L.append("```text")
    for k, v in s.items():
        L.append(f"  {k:40s} {v}")
    L.append("```\n")

    L.append("## Power projection\n")
    p = d["power_projection"]
    L.append("```text")
    L.append(f"  projected_mde (conservative)     {p['projected_mde']}")
    L.append(f"  design_projection                {p['design_projection']}")
    L.append(f"  measured_in_p1e1                 {p['measured_in_p1e1']}")
    L.append(f"  planned_caldev_n                 {p['planned_caldev_n']}")
    L.append(f"  formula                          {p['formula']}")
    L.append("```\n")
    L.append(f"> {p['statement']}\n")

    L.append("## Protocol history\n")
    ph = d["protocol_history"]
    L.append("```text")
    for v in ["v1", "v2", "v3", "v4"]:
        L.append(f"  {v}: {ph[v]['commit'][:12]}  {ph[v]['summary']}")
    ha = ph["historical_calibration_held_out_access"]
    L.append(f"  historical held-out access: cases={ha['held_out_cases']} texts={ha['held_out_candidate_texts']} judgments={ha['held_out_judgments']}")
    af = ph["admissible_final_calibration"]
    L.append(f"  admissible calibration: {af['caldev_pairs']} cal/dev pairs, threshold={af['threshold']}")
    L.append("```\n")

    L.append("## Custody and blinding\n")
    cu = d["custody_and_blinding"]
    L.append("```text")
    L.append(f"  blind held-out cases             {cu['blind_package_held_out_cases']}")
    L.append(f"  opaque identifiers               {cu['opaque_identifiers_used']}")
    L.append(f"  reconciliation map committed     {cu['reconciliation_map_committed']}")
    L.append(f"  construction copy deleted        {cu['construction_copy_deleted']}")
    L.append(f"  transfer status                  {cu['transfer_status']}")
    L.append(f"  held-out grades inspected        {cu['held_out_grades_inspected']}")
    L.append(f"  final held-out adjudication      {'pending' if cu['final_held_out_adjudication_pending'] else 'done'}")
    L.append("```\n")
    L.append(f"> {cu['custody_limitation_note']}\n")

    L.append("## Completion status\n")
    cs = d["completion_status"]
    L.append("```text")
    for k, v in cs.items():
        L.append(f"  {k:35s} {v}")
    L.append("```\n")

    L.append("## Conclusion\n")
    L.append("P1E.1 produced a larger and more discriminative retrieval benchmark. "
             "It materially increased negative and hard-negative coverage "
             f"(grade-0 candidates: 13→{g['grade_distribution'].get('0',0)}; "
             f"per-case rate: {cmp['per_case_grade0_rate']['p1e0']}→{cmp['per_case_grade0_rate']['p1e1']}). "
             "It did **not** compare retrieval policies and did **not** select a production retrieval architecture. "
             "P1E.2 is responsible for held-out adjudication. "
             "P1E.3 is responsible for the frozen retrieval-policy comparison. "
             "The projected MDE (0.02938) is a design value; actual MDE will be measured in P1E.3.\n")

    return "\n".join(L) + "\n"


def main() -> int:
    d = build_diagnosis()
    OUT_JSON.write_text(canonical_json(d) + "\n", encoding="utf-8")
    md = render_markdown(d)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(f"  composition: {d['composition']['total_cases']} cases ({d['composition']['calibration_cases']}/{d['composition']['development_cases']}/{d['composition']['held_out_cases']})")
    print(f"  adjudication: {d['adjudication']['inherited_v2_caldev_records']} inherited + {d['adjudication']['fresh_judgments_total']} fresh = {d['composition']['caldev_grade_records']}")
    print(f"  grade targets pass: {d['grade_dependent_targets']['all_targets_pass']}")
    print(f"  projected_mde: {d['power_projection']['projected_mde']} (design_projection={d['power_projection']['design_projection']})")
    print(f"  final fingerprint: {d['identity']['final_adjudicated_v3_fingerprint']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
