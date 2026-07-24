"""P1E.1 — v3 candidate-corpus registry (fingerprint, validation, coverage).

Separate from the v2 registry. Does NOT touch `ALL_V2_CASES` or the v2
fingerprint. Provides the provisional candidate-corpus identity used by the
Commit-2 seal (the final adjudicated v3 fingerprint is pending P1E.2).

Identity (protocol §11):
    candidate_corpus_fingerprint covers:
      ordered case IDs
      ordered candidate IDs per case (declared order)
      normalized query + candidate content hashes
      lineage references (parent_v2_case_id, parent_v2_candidate_id)
      candidate order
      benchmark candidate version
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from backend.ranking.benchmark_v3_candidates import V3CandidateCase
from backend.ranking.p1e1_canon import canonical_json_hash

V3_CANDIDATE_BENCHMARK_VERSION = "discovery_ranking_v3+retrieval_ranking_v3"


def _case_fingerprint_payload(case: V3CandidateCase) -> dict[str, Any]:
    """Deterministic per-case payload for the candidate-corpus fingerprint.

    Covers query content hash, ordered candidate IDs, each candidate's content
    hash + lineage, and the case's lineage/slice/split metadata. Excludes any
    judgment field by construction (the candidate schema has none).
    """
    return {
        "case_id": case.case_id,
        "domain": case.research_domain,
        "surface": case.ranking_surface,
        "intent": case.ranking_intent,
        "query_content_hash": __import__("backend.ranking.p1e1_canon", fromlist=["content_hash"]).content_hash(case.query_text, ""),
        "candidates": [
            {
                "candidate_id": c.candidate_id,
                "content_hash": c.content_hash,
                "source_rank": c.source_rank,
                "near_duplicate_of": c.near_duplicate_of,
                "parent_v2_candidate_id": c.parent_v2_candidate_id,
                "content_unchanged_from_parent": c.content_unchanged_from_parent,
            }
            for c in case.candidates
        ],
        "split": case.split,
        "primary_slice": case.primary_slice,
        "secondary_slices": list(case.secondary_slices),
        "parent_v2_case_id": case.parent_v2_case_id,
        "lineage_type": case.lineage_type,
        "query_generation_anchor_candidate_id": case.query_generation_anchor_candidate_id,
    }


def compute_v3_candidate_corpus_fingerprint(cases) -> str:
    """SHA-256 over the canonical JSON of the ordered per-case payload list.

    Case order is the DECLARED order in `cases` (the canonical case order);
    candidate order within each case is the declared order. This is the
    provisional candidate-corpus identity (final adjudicated fingerprint is
    pending P1E.2).
    """
    payload = [_case_fingerprint_payload(c) for c in cases]
    return canonical_json_hash({"version": V3_CANDIDATE_BENCHMARK_VERSION, "cases": payload})


def validate_v3_candidates(cases) -> list[str]:
    """Validate the v3 candidate corpus. Returns list of errors (empty = OK)."""
    from backend.ranking.benchmark_v2_schema import ALL_SLICE_TYPES
    from backend.ranking.benchmark_v3_candidates import ALLOWED_MINING_ROLES

    errors: list[str] = []
    seen_cases: set[str] = set()
    seen_candidates: set[str] = set()
    for case in cases:
        if case.case_id in seen_cases:
            errors.append(f"duplicate case_id: {case.case_id}")
        seen_cases.add(case.case_id)
        if case.primary_slice not in ALL_SLICE_TYPES:
            errors.append(f"{case.case_id}: invalid primary_slice {case.primary_slice}")
        for s in case.secondary_slices:
            if s not in ALL_SLICE_TYPES:
                errors.append(f"{case.case_id}: invalid secondary_slice {s}")
        if case.split not in ("calibration", "development", "held_out"):
            errors.append(f"{case.case_id}: invalid split {case.split}")
        if case.lineage_type not in ("fully_new", "v2_extended"):
            errors.append(f"{case.case_id}: invalid lineage_type {case.lineage_type}")
        cand_ids = [c.candidate_id for c in case.candidates]
        if len(cand_ids) != len(set(cand_ids)):
            errors.append(f"{case.case_id}: duplicate candidate_id within case")
        for cid in cand_ids:
            if cid in seen_candidates:
                errors.append(f"{case.case_id}: candidate_id collision across cases: {cid}")
            seen_candidates.add(cid)
        # candidate count 6-8
        if not (6 <= len(case.candidates) <= 8):
            errors.append(f"{case.case_id}: candidate count {len(case.candidates)} outside 6-8")
        for c in case.candidates:
            if c.mining_role is not None and c.mining_role not in ALLOWED_MINING_ROLES:
                errors.append(f"{case.case_id}/{c.candidate_id}: disallowed mining_role {c.mining_role}")
        # anchor must reference a real candidate in the case
        if case.query_generation_anchor_candidate_id is not None:
            if case.query_generation_anchor_candidate_id not in cand_ids:
                errors.append(f"{case.case_id}: anchor {case.query_generation_anchor_candidate_id} not in candidates")
    return errors


def slice_coverage_v3(cases) -> dict[str, Any]:
    """Report slice × surface × domain × split coverage for the v3 corpus."""
    report: dict[str, Any] = {"by_slice": {}, "split_counts": {}, "domain_counts": {}, "surface_counts": {}}
    for slice_type in set(c.primary_slice for c in cases):
        entry = {"discovery": 0, "retrieval": 0, "domains": set(), "splits": set()}
        for case in cases:
            if case.primary_slice != slice_type:
                continue
            sk = "discovery" if case.ranking_surface == "discovery_ranking" else "retrieval"
            entry[sk] += 1
            entry["domains"].add(case.research_domain)
            entry["splits"].add(case.split)
        entry["domains"] = sorted(entry["domains"])
        entry["splits"] = sorted(entry["splits"])
        report["by_slice"][slice_type] = entry
    report["split_counts"] = dict(Counter(c.split for c in cases))
    report["domain_counts"] = dict(Counter(c.research_domain for c in cases))
    report["surface_counts"] = {
        "discovery": sum(1 for c in cases if c.ranking_surface == "discovery_ranking"),
        "retrieval": sum(1 for c in cases if c.ranking_surface == "retrieval_ranking"),
    }
    return report
