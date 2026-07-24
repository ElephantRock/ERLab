"""P1E.1 Commit 3 — Build the provisional extension identity.

Joins sealed cal/dev grades to sealed mining scores (no recompute after seeing
grades), evaluates the grade-dependent targets, and assembles the extension
identity with final_adjudicated_v3_fingerprint = pending_p1e2.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.p1e1_canon import canonical_json, canonical_json_hash, sha256_file

OUT = REPO_ROOT / "data" / "evaluation" / "p1e1_benchmark_extension.json"
ND_THRESHOLD = 0.861630662


def main() -> int:
    pkg = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_package.json").read_text())
    prov = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_provenance.json").read_text())
    mining = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_mining_scores.json").read_text())
    prej = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_prejudgment_diagnostics.json").read_text())
    manifest = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_split_manifest.json").read_text())
    caldev_adj = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_caldev_adjudication.json").read_text())
    blind = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_blind_heldout_package.json").read_text())
    receipt = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_reconciliation_map_custody_receipt.json").read_text())

    # join grades to mining scores
    grade_by = {(r["v3_case_id"], r["v3_candidate_id"]): r["grade"] for r in caldev_adj["grades"]}
    # mining scores: query->candidate
    lex_by = {(r["case_id"], r["candidate_id"]): r["lexical_overlap"] for r in mining["scores"]}
    sem_by = {(r["case_id"], r["candidate_id"]): r["semantic_mining"] for r in mining["scores"]}
    # near-dup pair scores
    nd_pairs = {(r["case_id"], r["candidate_id"]): r["candidate_candidate_cosine"]
                for r in mining.get("near_duplicate_pair_scores", [])}

    caldev_cases = [c for c in pkg["cases"] if c["split"] in ("calibration", "development")]

    # ── grade-dependent targets (66 cal/dev cases) ──
    cases_grade0_ge2 = 0
    cases_hardneg_ge2 = 0
    cases_unique_best = 0
    cases_misleading_nd = 0
    cases_lexical_confuser = 0
    grade0_total = 0
    grade_dist = Counter()
    weak_pos_total = 0
    ambiguous_top = 0

    for case in caldev_cases:
        cid = case["case_id"]
        grades = {}
        for cc in case["candidates"]:
            g = grade_by.get((cid, cc["candidate_id"]))
            if g is None:
                raise SystemExit(f"missing grade for {cid}/{cc['candidate_id']}")
            grades[cc["candidate_id"]] = g
            grade_dist[g] += 1
        g0_count = sum(1 for g in grades.values() if g == 0)
        grade0_total += g0_count
        weak_pos_total += sum(1 for g in grades.values() if g == 1)
        if g0_count >= 2:
            cases_grade0_ge2 += 1
        # primary hard negatives: grade==0 AND score >= min among grade>0
        pos_scores = []
        for cc in case["candidates"]:
            ccid = cc["candidate_id"]
            if grades[ccid] > 0:
                lex = lex_by.get((cid, ccid))
                sem = sem_by.get((cid, ccid))
                if lex is not None: pos_scores.append(lex)
                if sem is not None: pos_scores.append(sem)
        min_pos = min(pos_scores) if pos_scores else None
        hard_negs = 0
        lex_confuser = 0
        for cc in case["candidates"]:
            ccid = cc["candidate_id"]
            if grades[ccid] == 0 and min_pos is not None:
                lex = lex_by.get((cid, ccid))
                sem = sem_by.get((cid, ccid))
                confusable = (lex is not None and lex >= min_pos) or (sem is not None and sem >= min_pos)
                if confusable:
                    hard_negs += 1
                    lex_confuser += 1
        if hard_negs >= 2:
            cases_hardneg_ge2 += 1
        if lex_confuser >= 1:
            cases_lexical_confuser += 1
        # unique-best
        top_grade = max(grades.values()) if grades else 0
        n_top = sum(1 for g in grades.values() if g == top_grade)
        if top_grade > 0 and n_top == 1:
            cases_unique_best += 1
        elif top_grade > 0 and n_top >= 2:
            ambiguous_top += 1
        # misleading near-duplicate: validated pair with different grades
        for cc in case["candidates"]:
            ccid = cc["candidate_id"]
            if (cid, ccid) in nd_pairs:
                pair_cos = nd_pairs[(cid, ccid)]
                if pair_cos >= ND_THRESHOLD:
                    # find the parent's grade
                    parent_id = next((x["near_duplicate_of"] for x in [cc] if x.get("near_duplicate_of")), None)
                    # actually get from provenance
                    parent_id = None
                    for p in prov["provenance"]:
                        if p["case_id"] == cid and p["candidate_id"] == ccid and p.get("mining_role") == "constructed_near_duplicate":
                            parent_id = p.get("near_duplicate_of")
                            break
                    if parent_id and parent_id in grades and grades[ccid] != grades[parent_id]:
                        cases_misleading_nd += 1
                        break

    n = len(caldev_cases)
    min_g0 = min(
        sum(1 for cc in c["candidates"] if grade_by.get((c["case_id"], cc["candidate_id"]), 0) == 0)
        for c in caldev_cases)
    targets = {
        "denominator": n,
        "min_grade0_per_case": {"required": 1, "actual_min": min_g0, "pass": min_g0 >= 1},
        "pct_cases_grade0_ge2": {"required_pct": 80, "actual_pct": round(100 * cases_grade0_ge2 / n, 1),
                                  "actual_count": cases_grade0_ge2, "pass": 100 * cases_grade0_ge2 / n >= 80},
        "pct_cases_hardneg_ge2": {"required_pct": 60, "actual_pct": round(100 * cases_hardneg_ge2 / n, 1),
                                   "actual_count": cases_hardneg_ge2, "pass": 100 * cases_hardneg_ge2 / n >= 60},
        "unique_best": {"required_pct": 50, "actual_pct": round(100 * cases_unique_best / n, 1),
                        "actual_count": cases_unique_best, "pass": 100 * cases_unique_best / n >= 50},
        "adjudicated_misleading_near_duplicate": {"required": 8, "actual": cases_misleading_nd,
                                                   "pass": cases_misleading_nd >= 8},
        "adjudicated_lexical_confuser": {"required": 8, "actual": cases_lexical_confuser,
                                          "pass": cases_lexical_confuser >= 8},
        "weak_positive": {"report_only": True, "total": weak_pos_total},
        "ambiguous_top": {"report_only": True, "count": ambiguous_top},
    }
    all_targets_pass = all(v.get("pass", True) for v in targets.values() if isinstance(v, dict) and "pass" in v)

    extension = {
        "schema": "p1e1_benchmark_extension_v1",
        "protocol_commit": pkg["protocol_commit"],
        "protocol_sha256": pkg["protocol_sha256"],
        "protocol_version": "p1e1_protocol_v3",
        "candidate_corpus_fingerprint": pkg["candidate_corpus_fingerprint"],
        "candidate_package_sha256": pkg["candidate_package_sha256"],
        "candidate_provenance_sha256": prov["candidate_provenance_sha256"],
        "candidate_mining_scores_sha256": mining["mining_scores_sha256"],
        "split_manifest_sha256": manifest["split_manifest_sha256"],
        "caldev_adjudication_sha256": caldev_adj["caldev_adjudication_sha256"],
        "candidate_benchmark_version": "discovery_ranking_v3+retrieval_ranking_v3",
        "identity": {
            "candidate_benchmark_identity": "sealed",
            "caldev_adjudication_identity": "sealed",
            "blind_heldout_package_identity": "sealed",
            "blind_package_sha256": blind["blind_package_sha256"],
            "custody_receipt_map_sha256": receipt["reconciliation_map_sha256"],
            "final_adjudicated_v3_fingerprint": "pending_p1e2",
            "p1e3_policy_evaluation": "not_performed",
        },
        "composition": {
            "total_cases": 88, "calibration": 33, "development": 33, "held_out": 22,
            "v2_lineage": 44, "fully_new": 44,
        },
        "grade_distribution_caldev": dict(sorted(grade_dist.items())),
        "grade_dependent_targets": targets,
        "all_grade_targets_pass": all_targets_pass,
        "prejudgment_structural_targets_ref": prej["structural_targets"],
        "note": "projected MDE is a design projection (0.02938 conservative at n=66); "
                "actual MDE deferred to P1E.3. final_adjudicated_v3_fingerprint pending P1E2.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(canonical_json(extension) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  grade distribution: {dict(sorted(grade_dist.items()))}")
    print(f"  grade-0 total: {grade0_total}")
    for k, v in targets.items():
        if isinstance(v, dict) and "pass" in v:
            print(f"  {k}: pass={v['pass']}  ({v})")
        elif isinstance(v, dict):
            print(f"  {k}: {v}")
        # skip non-dict values like denominator
    print(f"  ALL TARGETS PASS: {all_targets_pass}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
