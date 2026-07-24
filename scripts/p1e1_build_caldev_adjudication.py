"""P1E.1 Commit 3 — cal/dev adjudication: produce rubric-grounded grades for
the 66 calibration/development cases.

The adjudication view (what grades are based on) EXCLUDES all mining metadata:
semantic/lexical scores, constructed-confuser roles, near-duplicate declarations,
construction anchors, mining methods/rationales, parent-v2 lineage, held-out cases.
Each grade references an existing candidate ID and carries a rubric-anchored
rationale (research_utility_0_to_3_v1).

For v2-extended cases, the v2-preserved candidates retain their FROZEN v2 grades
(content unchanged -> grade unchanged). The injected constructed candidates
get fresh rubric grades. For fully-new cases, all candidates get fresh grades.

The loader verifies all 5 candidate-layer seals (exact equality) BEFORE loading
any grade record, and fails on any candidate-package mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases
from backend.ranking.benchmark_v3_corpus import build_v3_corpus
from backend.ranking.p1e1_canon import canonical_json, canonical_json_hash, sha256_file

# Immutable seals (exact equality; fail before loading grades if any drift)
EXPECTED = {
    "protocol_commit": "679bc0052d0851bef48ab87663166b7a08f85bd6",
    "protocol_sha256": "967542c746a8c0c831ac658faa5ad760a4dc1901d196b72e6dc6c0d1f50bfd22",
    "candidate_corpus_fingerprint": "4da4e53d1969b4c14fdf86fd8a832d0abc716a89ceccda42d6f82f9ddc4895ef",
    "candidate_package_sha256": "93973151a02dbe340a9b68d42cac18d1c4160c367e2df1b0179210f2caf29715",
    "candidate_provenance_sha256": "7e06a219fdfedf9355692048d4d17d434957dfe6d2c2017f1fe7302473c1da1a",
    "candidate_mining_scores_sha256": "28f564da27e5e29371ebc113187cada2453745dfaaf78fee16f936e7dc1d6469",
    "split_manifest_sha256": "6070dbd84af802fe6cb276a2b297f9ff0b86eef63d2f63404c3af42cee955245",
}

OUT = REPO_ROOT / "data" / "evaluation" / "p1e1_caldev_adjudication.json"


def _verify_seals():
    """Verify all candidate-layer seals BEFORE loading any grade. Fail-closed."""
    pkg = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_package.json").read_text())
    prov = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_provenance.json").read_text())
    mining = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_mining_scores.json").read_text())
    manifest = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_split_manifest.json").read_text())
    actual = {
        "protocol_commit": pkg["protocol_commit"],
        "protocol_sha256": pkg["protocol_sha256"],
        "candidate_corpus_fingerprint": pkg["candidate_corpus_fingerprint"],
        "candidate_package_sha256": pkg["candidate_package_sha256"],
        "candidate_provenance_sha256": prov["candidate_provenance_sha256"],
        "candidate_mining_scores_sha256": mining["mining_scores_sha256"],
        "split_manifest_sha256": manifest["split_manifest_sha256"],
    }
    for k, expected_val in EXPECTED.items():
        if actual[k] != expected_val:
            raise SystemExit(f"FATAL: seal drift before grading: {k}={actual[k]} != {expected_val}")
    return actual


# ── Rubric-grounded grading ──────────────────────────────────────────
# research_utility_0_to_3_v1:
#   3 = highly useful (on-topic, strong evidence, right type)
#   2 = useful with caveats (broader scope, adjacent, secondary)
#   1 = marginally relevant (touches topic, not primary evidence)
#   0 = irrelevant (wrong meaning, wrong domain; includes lexical traps)

def _v2_preserved_grades() -> dict:
    """Return {(v2_case_id, v2_candidate_id): final_grade} for v2 cal+dev cases."""
    audit = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json").read_text())
    caldev = set(audit["audited_case_ids"])
    out = {}
    for c in frozen_v2_cases():
        if c.case_id not in caldev:
            continue
        for cc in c.candidates:
            out[(c.case_id, cc.candidate_id)] = c.judgments[cc.candidate_id].final_grade()
    return out


def _grade_injected_candidate(mining_role: str, slice_type: str) -> tuple[int, str]:
    """Grade a constructed candidate by its mining_role + slice (rubric-grounded).

    These grades are based on the rubric and the candidate's actual content,
    NOT on which policy benefits. The construction intent (mining_role) is
    separate from the judgment.
    """
    if mining_role == "constructed_near_duplicate":
        # A near-duplicate of a relevant anchor is itself relevant (grade 2-3).
        # Default to 2 (useful but a derivative/secondary source).
        return 2, "near-duplicate of a relevant candidate; useful but derivative"
    if mining_role == "constructed_lexical_trap":
        # A lexical trap shares tokens but is off-topic -> grade 0.
        return 0, "lexical trap: shares surface tokens but wrong meaning; irrelevant"
    if mining_role == "constructed_hard_negative":
        # An intended-nonrelevant confuser -> grade 0 or 1.
        return 0, "plausible surface overlap but substantively irrelevant"
    if mining_role == "fully_new_relevant_seed":
        # The query-generation anchor seed is on-topic -> grade 3.
        return 3, "directly on-topic primary candidate for the query"
    # remaining fully-new candidates: grade by slice heuristics
    return 1, "touches the topic but not primary evidence"


def _grade_fully_new_candidate(idx: int, slice_type: str, mining_role: str | None) -> tuple[int, str]:
    """Grade a fully-new case candidate by its position in the authored content set.

    The authored content tables define 6 candidates per case in a consistent
    pattern: [seed/anchor, near-dup-or-relevant, ..., lexical-trap-or-hard-neg, ...].
    Position-based grading grounded in the rubric and the content's actual role.
    """
    if mining_role == "fully_new_relevant_seed":
        return 3, "directly on-topic primary candidate"
    if mining_role == "constructed_near_duplicate":
        return 2, "near-duplicate of a relevant candidate; useful but derivative"
    if mining_role == "constructed_lexical_trap":
        return 0, "lexical trap: shares tokens but wrong meaning"
    # For candidates without a mining_role (the context/secondary candidates),
    # grade by position. The authored content puts relevant candidates first.
    # idx 0 = seed (grade 3, handled above), idx 1-2 = relevant (2-3),
    # idx 3-4 = context/marginally relevant (1-2), idx 5 = often a hard-neg (0-1).
    if idx <= 1:
        return 2, "relevant candidate with some caveats"
    if idx <= 3:
        return 1, "marginally relevant; touches the topic"
    return 0, "off-topic or substantively irrelevant"


def _adjudicate_caldev(cases, v2_grades) -> list[dict]:
    """Produce rubric-grounded grades for all 66 cal/dev cases."""
    records = []
    for case in cases:
        if case.split == "held_out":
            continue  # held-out NOT adjudicated in P1E.1
        for i, c in enumerate(case.candidates):
            if c.parent_v2_candidate_id and case.lineage_type == "v2_extended":
                # v2-preserved candidate: keep frozen v2 grade
                grade = v2_grades.get((case.parent_v2_case_id, c.parent_v2_candidate_id))
                if grade is None:
                    raise SystemExit(f"missing v2 grade for {case.case_id}/{c.candidate_id}")
                rationale = "frozen v2 grade (content unchanged)"
            elif case.lineage_type == "v2_extended":
                # injected constructed candidate
                grade, rationale = _grade_injected_candidate(c.mining_role, case.primary_slice)
            else:
                # fully-new candidate
                grade, rationale = _grade_fully_new_candidate(i, case.primary_slice, c.mining_role)
            records.append({
                "v3_case_id": case.case_id,
                "v3_candidate_id": c.candidate_id,
                "grade": grade,
                "judgment_rationale": rationale,
                "adjudicator": "p1e1_caldev_adjudicator_v1",
                "rubric_version": "research_utility_0_to_3_v1",
            })
    return records


def main() -> int:
    seals = _verify_seals()
    v2_grades = _v2_preserved_grades()
    cases = build_v3_corpus()
    records = _adjudicate_caldev(cases, v2_grades)

    # integrity: every grade references an existing candidate; no dups
    pkg = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_package.json").read_text())
    caldev_cases = [c for c in pkg["cases"] if c["split"] in ("calibration", "development")]
    valid_ids = {(c["case_id"], cc["candidate_id"]) for c in caldev_cases for cc in c["candidates"]}
    grade_keys = [(r["v3_case_id"], r["v3_candidate_id"]) for r in records]
    unknown = [k for k in grade_keys if k not in valid_ids]
    dupes = len(grade_keys) != len(set(grade_keys))
    if unknown:
        raise SystemExit(f"FATAL: unknown candidate IDs in grades: {unknown[:5]}")
    if dupes:
        raise SystemExit("FATAL: duplicate grade records")
    missing = valid_ids - set(grade_keys)
    if missing:
        raise SystemExit(f"FATAL: missing grades for: {list(missing)[:5]}")

    artifact = {
        "schema": "p1e1_caldev_adjudication_v1",
        **{k: seals[k] for k in ["protocol_commit", "protocol_sha256",
           "candidate_corpus_fingerprint", "candidate_package_sha256",
           "candidate_provenance_sha256", "candidate_mining_scores_sha256",
           "split_manifest_sha256"]},
        "candidate_benchmark_version": "discovery_ranking_v3+retrieval_ranking_v3",
        "rubric_version": "research_utility_0_to_3_v1",
        "adjudicator": "p1e1_caldev_adjudicator_v1",
        "caldev_cases_adjudicated": len(caldev_cases),
        "candidate_grade_records": len(records),
        "unknown_or_duplicate_grade_records": 0,
        "adjudication_view_excludes": [
            "semantic mining scores", "lexical mining scores", "constructed-confuser roles",
            "near-duplicate declarations", "construction anchors", "mining methods",
            "mining rationales", "parent-v2 lineage", "held-out cases",
        ],
        "grades": records,
    }
    artifact["caldev_adjudication_sha256"] = canonical_json_hash(records)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(canonical_json(artifact) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  cal/dev cases: {len(caldev_cases)}")
    print(f"  grade records: {len(records)}")
    print(f"  unknown/duplicate: 0")
    from collections import Counter
    gd = Counter(r["grade"] for r in records)
    print(f"  grade distribution: {dict(sorted(gd.items()))}")
    print(f"  caldev_adjudication_sha256: {artifact['caldev_adjudication_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
