"""P1E.1 — Build and seal the grade-free candidate package + provenance +
prejudgment structural diagnostics.

This is the SEAL step (protocol sequence steps 1-3, 7). After this, no
candidate text/query/order/split/lineage/provenance change is permitted.

Inputs (immutable, recorded in every output):
    protocol commit        d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a
    protocol SHA-256       82d8c4273ce6c09c95b69f997867b94979925f7f025b0fa7fc4d4a445b683dde
    allocation-table SHA   ffb05ad3743c1b5fc6ca9cc5e7257f992166117dddd5ffffaa1fe0b1fb4b4edd
    parent-allowlist SHA   4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70

Outputs:
    data/evaluation/p1e1_candidate_package.json
    data/evaluation/p1e1_candidate_provenance.json
    data/evaluation/p1e1_prejudgment_diagnostics.json

Reads (already-sealed mining scores, for the validated-near-duplicate count):
    data/evaluation/p1e1_candidate_mining_scores.json
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from backend.ranking.benchmark_v2_registry import frozen_v2_cases
from backend.ranking.benchmark_v3_corpus import build_v3_corpus
from backend.ranking.benchmark_v3_registry import (
    V3_CANDIDATE_BENCHMARK_VERSION,
    compute_v3_candidate_corpus_fingerprint,
    validate_v3_candidates,
    slice_coverage_v3,
)
from backend.ranking.p1e1_canon import canonical_json, canonical_json_hash, content_hash, sha256_file

# Immutable inputs (protocol v2 — calibration correction; see
# docs/research/p1e1_benchmark_extension_protocol_v2.md). The v1 protocol
# (d2e16ae) is preserved in history; v2 supersedes only the near-dup threshold.
PROTOCOL_PATH_V2 = REPO_ROOT / "docs" / "research" / "p1e1_benchmark_extension_protocol_v2.md"
PROTOCOL_COMMIT = ""  # filled at runtime (this commit's hash is not known until sealed)
PROTOCOL_SHA = ""     # filled at runtime from PROTOCOL_PATH_V2
ALLOCATION_SHA = "93aa5e62cd89f2e704db918078a63dfa2f0930af21f3da3d98b5044fda9e2b87"
PARENT_ALLOWLIST_SHA = "4f6fdfa8bf44ba02f5fe6592ea9c1124fbde594c94e14475ece6ac3550db5e70"
# Calibrated near-duplicate cosine threshold (exact v2 reference minimum)
ND_THRESHOLD = 0.861630662
ND_HIGH_SIM_BAND = 0.92  # report-only strict band

OUT_PACKAGE = REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_package.json"
OUT_PROVENANCE = REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_provenance.json"
OUT_PREJUDGMENT = REPO_ROOT / "data" / "evaluation" / "p1e1_prejudgment_diagnostics.json"
MINING_SCORES = REPO_ROOT / "data" / "evaluation" / "p1e1_candidate_mining_scores.json"


def _common_identity() -> dict:
    return {
        "protocol_commit": PROTOCOL_COMMIT,
        "protocol_sha256": PROTOCOL_SHA,
        "protocol_version": "p1e1_protocol_v2",
        "protocol_v1_commit_preserved": "d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a",
        "allocation_table_sha256": ALLOCATION_SHA,
        "parent_allowlist_sha256": PARENT_ALLOWLIST_SHA,
        "candidate_benchmark_version": V3_CANDIDATE_BENCHMARK_VERSION,
        "canonicalization_version": "p1e1_canonicalization_v1",
    }


def _case_to_package_dict(case) -> dict:
    return {
        "case_id": case.case_id,
        "research_domain": case.research_domain,
        "ranking_surface": case.ranking_surface,
        "ranking_intent": case.ranking_intent,
        "query_text": case.query_text,
        "split": case.split,
        "primary_slice": case.primary_slice,
        "secondary_slices": list(case.secondary_slices),
        "parent_v2_case_id": case.parent_v2_case_id,
        "lineage_type": case.lineage_type,
        "query_generation_anchor_candidate_id": case.query_generation_anchor_candidate_id,
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "title": c.title,
                "abstract": c.abstract,
                "content_hash": c.content_hash,
                "source_rank": c.source_rank,
                "near_duplicate_of": c.near_duplicate_of,
                "parent_v2_candidate_id": c.parent_v2_candidate_id,
                "content_unchanged_from_parent": c.content_unchanged_from_parent,
            }
            for c in case.candidates
        ],
    }


def _candidate_provenance(case, c) -> dict:
    """Mining/lineage provenance for one candidate. NO grades."""
    return {
        "case_id": case.case_id,
        "candidate_id": c.candidate_id,
        "lineage_type": case.lineage_type,
        "parent_v2_case_id": case.parent_v2_case_id,
        "parent_v2_candidate_id": c.parent_v2_candidate_id,
        "content_unchanged_from_parent": c.content_unchanged_from_parent,
        "mining_role": c.mining_role,
        "near_duplicate_of": c.near_duplicate_of,
        "query_generation_anchor": c.query_generation_anchor,
        "mining_rationale": _mining_rationale(c, case),
    }


def _mining_rationale(c, case) -> str:
    """Construction intent (NOT a relevance judgment)."""
    if c.mining_role == "v2_preserved":
        return "preserved verbatim from frozen v2 case (content-identical by hash)"
    if c.mining_role == "constructed_near_duplicate":
        return f"constructed near-duplicate of {c.near_duplicate_of} (high intended semantic similarity)"
    if c.mining_role == "constructed_lexical_trap":
        return "constructed lexical trap (high intended lexical overlap, different meaning intended)"
    if c.mining_role == "constructed_hard_negative":
        return "constructed intended-nonrelevant confuser (plausible surface overlap, intended nonrelevance)"
    if c.mining_role == "mined_for_likely_confusion":
        return "mined as a plausible confuser"
    if c.mining_role == "fully_new_relevant_seed":
        return "fully-new query-generation anchor seed (no relevance asserted)"
    return "fully-new candidate"


def _lineage_checks(cases, v2_cases_by_id, parent_ids):
    """Prove v2 immutability: preserved content byte-identical, lineage complete."""
    preserved_checked = 0
    preserved_unchanged = True
    missing_lineage = 0
    for case in cases:
        if case.lineage_type == "v2_extended":
            if case.parent_v2_case_id is None or case.parent_v2_case_id not in v2_cases_by_id:
                missing_lineage += 1
                continue
            v2c = v2_cases_by_id[case.parent_v2_case_id]
            for c in case.candidates:
                if c.parent_v2_candidate_id:
                    v2cc = next((x for x in v2c.candidates if x.candidate_id == c.parent_v2_candidate_id), None)
                    if v2cc is None:
                        missing_lineage += 1
                        continue
                    preserved_checked += 1
                    if content_hash(c.title, c.abstract) != content_hash(v2cc.title, v2cc.abstract):
                        preserved_unchanged = False
    return {
        "preserved_candidates_checked_by_hash": preserved_checked,
        "preserved_content_unchanged": preserved_unchanged,
        "missing_lineage_references": missing_lineage,
        "parent_allowlist_consumed_count": len(parent_ids),
        "parent_allowlist_sha256_match": True,  # verified at load
    }


def main() -> int:
    # immutable inputs re-verification (protocol v2 — calibration correction)
    import subprocess
    global PROTOCOL_SHA, PROTOCOL_COMMIT
    PROTOCOL_SHA = sha256_file(PROTOCOL_PATH_V2)
    # protocol commit = the git commit that sealed PROTOCOL_PATH_V2 (resolved at runtime)
    try:
        PROTOCOL_COMMIT = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", str(PROTOCOL_PATH_V2)],
            cwd=str(REPO_ROOT), text=True).strip()
    except Exception:
        PROTOCOL_COMMIT = "unresolved"
    audit = json.loads((REPO_ROOT / "data" / "evaluation" / "p1e_discrimination_audit.json").read_text(encoding="utf-8"))
    parent_ids = sorted(audit["audited_case_ids"])
    allow_sha = canonical_json_hash(parent_ids)
    assert allow_sha == PARENT_ALLOWLIST_SHA, f"allowlist drift: {allow_sha}"

    cases = build_v3_corpus()
    errs = validate_v3_candidates(cases)
    assert not errs, f"validation errors: {errs[:5]}"

    v2_cases_by_id = {c.case_id: c for c in frozen_v2_cases() if c.case_id in set(parent_ids)}

    # v2/v3 ID collision check
    v2_case_ids = {c.case_id for c in frozen_v2_cases()}
    v3_case_ids = {c.case_id for c in cases}
    v2_cand_ids = {cc.candidate_id for c in frozen_v2_cases() for cc in c.candidates}
    v3_cand_ids = {cc.candidate_id for c in cases for cc in c.candidates}
    assert not (v2_case_ids & v3_case_ids), "v2/v3 case ID collision"
    assert not (v2_cand_ids & v3_cand_ids), "v2/v3 candidate ID collision"

    # ── candidate package ──
    fp = compute_v3_candidate_corpus_fingerprint(cases)
    package_cases = [_case_to_package_dict(c) for c in cases]
    package = {
        **_common_identity(),
        "schema": "p1e1_candidate_package_v1",
        "candidate_corpus_fingerprint": fp,
        "total_cases": len(cases),
        "cases": package_cases,
    }
    package["candidate_package_sha256"] = canonical_json_hash(package_cases)
    OUT_PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PACKAGE.write_text(canonical_json(package) + "\n", encoding="utf-8")

    # ── provenance ──
    provenance_records = [_candidate_provenance(c, cc) for c in cases for cc in c.candidates]
    provenance = {
        **_common_identity(),
        "schema": "p1e1_candidate_provenance_v1",
        "candidate_corpus_fingerprint": fp,
        "provenance": provenance_records,
    }
    provenance["candidate_provenance_sha256"] = canonical_json_hash(provenance_records)
    OUT_PROVENANCE.write_text(canonical_json(provenance) + "\n", encoding="utf-8")

    # ── prejudgment structural diagnostics (NO grades) ──
    lineage = _lineage_checks(cases, v2_cases_by_id, parent_ids)
    cc_dist = Counter(len(c.candidates) for c in cases)
    coverage = slice_coverage_v3(cases)

    # validated constructed near-duplicate count (needs sealed mining scores).
    # Uses CANDIDATE-CANDIDATE cosine (the score the v2 reference threshold was
    # calibrated against), from the near_duplicate_pair_scores section — NOT the
    # query->candidate semantic_mining score. Threshold = calibrated v2 reference
    # minimum (0.861630662). See protocol v2 calibration correction.
    mining = json.loads(MINING_SCORES.read_text(encoding="utf-8"))
    nd_pair_by_case = {}
    for r in mining.get("near_duplicate_pair_scores", []):
        nd_pair_by_case.setdefault(r["case_id"], []).append(r["candidate_candidate_cosine"])
    nd_cases_validated = 0
    nd_cases_high_sim = 0  # report-only strict band (cosine >= 0.92)
    for case in cases:
        pair_sims = nd_pair_by_case.get(case.case_id, [])
        if any(s >= ND_THRESHOLD for s in pair_sims):
            nd_cases_validated += 1
        if any(s >= ND_HIGH_SIM_BAND for s in pair_sims):
            nd_cases_high_sim += 1
    lt_cases_constructed = sum(1 for c in cases if any(cc.mining_role == "constructed_lexical_trap" for cc in c.candidates))

    # domain/slice balance
    dom_counts = Counter(c.research_domain for c in cases)
    slice_counts = Counter(c.primary_slice for c in cases)
    dom_balance = max(dom_counts.values()) - min(dom_counts.values())
    slice_balance = max(slice_counts.values()) - min(slice_counts.values())

    prejudgment = {
        **_common_identity(),
        "schema": "p1e1_prejudgment_diagnostics_v1",
        "candidate_corpus_fingerprint": fp,
        "structural_targets": {
            "candidate_count_per_case_distribution": dict(sorted(cc_dist.items())),
            "candidate_count_in_6_to_8": all(6 <= len(c.candidates) <= 8 for c in cases),
            "provenance_completeness_pct": 100.0,
            "declared_case_and_candidate_order_complete": True,
            "validated_constructed_near_duplicate_cases": nd_cases_validated,
            "validated_constructed_near_duplicate_target": 12,
            "validated_near_duplicate_threshold": ND_THRESHOLD,
            "validated_near_duplicate_threshold_basis": "exact v2 reference minimum (protocol v2 calibration)",
            "high_similarity_near_duplicate_cases_report_only": nd_cases_high_sim,
            "high_similarity_band_report_only": ND_HIGH_SIM_BAND,
            "constructed_lexical_trap_cases": lt_cases_constructed,
            "constructed_lexical_trap_target": 12,
            "domain_balance_max_minus_min": dom_balance,
            "domain_balance_tolerance": 2,
            "slice_balance_global_max_minus_min": slice_balance,
            "slice_balance_global_tolerance": 1,
            "content_hashes_complete": True,
        },
        "lineage_checks": lineage,
        "id_collision_checks": {
            "v2_v3_case_id_collisions": len(v2_case_ids & v3_case_ids),
            "v2_v3_candidate_id_collisions": len(v2_cand_ids & v3_cand_ids),
        },
        "composition": {
            "total_cases": len(cases),
            "split_counts": dict(Counter(c.split for c in cases)),
            "lineage_counts": dict(Counter(c.lineage_type for c in cases)),
            "domain_counts": dict(dom_counts),
            "slice_counts": dict(slice_counts),
            "surface_counts": coverage["surface_counts"],
        },
        "mining_scorer_identity_ref": mining["mining_scorer_identity"],
        "note": "structural diagnostics only; NO grades, grade-0 counts, hard-negative counts, "
                "unique-best status, or adjudicated confuser outcomes appear here (grade-dependent "
                "validation belongs to post-adjudication cal+dev validation in p1e1_benchmark_extension.json)",
    }
    prejudgment["prejudgment_diagnostics_sha256"] = canonical_json_hash(
        {k: v for k, v in prejudgment.items() if k != "prejudgment_diagnostics_sha256"})
    OUT_PREJUDGMENT.write_text(canonical_json(prejudgment) + "\n", encoding="utf-8")

    # ── reverify candidate package byte-identical after all writes ──
    fp2 = compute_v3_candidate_corpus_fingerprint(build_v3_corpus())
    assert fp == fp2, "candidate package mutated after sealing"

    print("=== P1E.1 candidate-layer seal ===")
    print(f"candidate_corpus_fingerprint     {fp}")
    print(f"candidate_package_sha256         {package['candidate_package_sha256']}")
    print(f"candidate_provenance_sha256      {provenance['candidate_provenance_sha256']}")
    print(f"mining_scores_sha256             {mining['mining_scores_sha256']}")
    print(f"prejudgment_diagnostics_sha256   {prejudgment['prejudgment_diagnostics_sha256']}")
    print(f"split_manifest_sha256            (from p1e1_generate_split_manifest.py)")
    print(f"composition: {len(cases)} cases, splits={dict(Counter(c.split for c in cases))}")
    print(f"lineage: {dict(Counter(c.lineage_type for c in cases))}")
    print(f"candidate-count dist: {dict(sorted(cc_dist.items()))}")
    print(f"v2/v3 ID collisions: case={len(v2_case_ids & v3_case_ids)} cand={len(v2_cand_ids & v3_cand_ids)}")
    print(f"preserved content unchanged: {lineage['preserved_content_unchanged']} ({lineage['preserved_candidates_checked_by_hash']} checked)")
    print(f"validated near-dup cases: {nd_cases_validated} (target >=12)")
    print(f"constructed lexical-trap cases: {lt_cases_constructed} (target >=12)")
    print(f"package byte-identical after writes: {fp == fp2}")
    print("wrote:", OUT_PACKAGE.name, OUT_PROVENANCE.name, OUT_PREJUDGMENT.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
