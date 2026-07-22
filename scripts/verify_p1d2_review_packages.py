"""P1D.2d-prep: verify reviewer packages exclude author grades and policy outputs.

Checks that the blinded reviewer packages contain no answer-revealing content.
"""
from __future__ import annotations
import json, sys, hashlib
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs" / "retrieval"


def run():
    failures = []
    passed = 0

    def chk(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failures.append((label, detail))

    for pkg in ["A", "B"]:
        records = [json.loads(l) for l in (DOCS / f"p1d2_reviewer_package_{pkg}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        chk(f"package {pkg}: 30 cases", len(records) == 30)

        for rec in records:
            # Must NOT contain author grades or rationales
            rec_str = json.dumps(rec)
            chk(f"{pkg}/{rec['case_id']}: no research_utility_grade", "research_utility_grade" not in rec_str)
            chk(f"{pkg}/{rec['case_id']}: no positive_passage_ids", "positive_passage_ids" not in rec_str)
            chk(f"{pkg}/{rec['case_id']}: no hard_topical_negatives", "hard_topical_negatives" not in rec_str)
            chk(f"{pkg}/{rec['case_id']}: no negative_failed_dimensions", "negative_failed_dimensions" not in rec_str)
            chk(f"{pkg}/{rec['case_id']}: no annotation_rationale", "annotation_rationale" not in rec_str)
            chk(f"{pkg}/{rec['case_id']}: no false_support_negatives", "false_support_negatives" not in rec_str)

            # Neutral IDs must not contain role-revealing content
            for u in rec["candidate_pool"]["units"]:
                nid = u["neutral_unit_id"]
                chk(f"{pkg}/{rec['case_id']}: neutral id {nid} has no role info",
                    not any(x in nid.lower() for x in ["positive", "negative", "false", "support", "trap", "distractor", "qualifier", "contradict"]))

            # Must contain passage text
            has_text = all(u.get("passage_text", "") != "[UNAVAILABLE]" for u in rec["candidate_pool"]["units"])
            chk(f"{pkg}/{rec['case_id']}: all units have passage text", has_text)

            # Must contain rubric
            chk(f"{pkg}/{rec['case_id']}: has rubric", "rubric" in rec)

    # Assignment manifest checks
    am = json.loads((DOCS / "p1d2_review_assignment_manifest.json").read_text(encoding="utf-8"))
    chk("assignment: blinding attested", all(am.get("blinding_attestations", {}).values()))
    chk("assignment: 81 judgments requiring review", am.get("total_judgments_requiring_review") == 81)
    chk("assignment: identity_map NOT embedded", am.get("identity_map_embedded") is False)
    chk("assignment: no neutral_id_map key in public manifest", "neutral_id_map" not in am,
        "neutral_id_map found in reviewer-accessible manifest")
    chk("assignment: identity_map_sha256 present", len(am.get("identity_map_sha256", "")) == 64)
    chk("assignment: identity_map_access_policy is coordinator_only", am.get("identity_map_access_policy") == "coordinator_only")

    # Verify the coordinator identity map exists and its hash matches the public reference
    coord_map_path = Path(__file__).resolve().parent.parent / "coordinator" / "p1d2_review_identity_map.json"
    chk("coordinator identity map exists", coord_map_path.exists())
    if coord_map_path.exists():
        live_hash = hashlib.sha256(coord_map_path.read_bytes()).hexdigest()
        chk("coordinator map hash matches public manifest", live_hash == am.get("identity_map_sha256"),
            f"live={live_hash[:16]} manifest={am.get('identity_map_sha256','?')[:16]}")

    # Package manifest checks
    pm = json.loads((DOCS / "p1d2_review_package_manifest.json").read_text(encoding="utf-8"))
    chk("package manifest: exclusions verified", all(pm.get("exclusions_verified", {}).values()))
    chk("package manifest: content included", all(pm.get("content_included", {}).values()))

    print("P1D.2d reviewer package verification")
    print("=" * 50)
    if failures:
        print(f"FAIL: {len(failures)} check(s) failed, {passed} passed")
        for label, detail in failures[:10]:
            print(f"  - {label}" + (f": {detail}" if detail else ""))
        sys.exit(1)
    else:
        print(f"PASS: all checks passed ({passed})")
        sys.exit(0)


if __name__ == "__main__":
    run()
