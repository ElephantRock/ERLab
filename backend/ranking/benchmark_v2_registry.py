"""P1B.1: Benchmark v2 registry — aggregation, validation, fingerprint,
slice coverage, and blinded adjudication-package export.

Single source of truth for the expanded P1B benchmark.

Freeze discipline (Decision 3)
------------------------------
- ``compute_benchmark_v2_fingerprint`` is only well-defined when the benchmark
  has zero unresolved disagreements. While any judgment has
  ``disagreement_status == 'unresolved'`` (or is still single-pass pending the
  blind adjudicator), the function raises. This prevents freezing a
  fingerprint before the adjudication pass completes.
- The provisional fingerprint (pre-adjudication) is available via
  ``compute_provisional_fingerprint`` so the author's initial freeze is
  auditable, but it MUST NOT be used for policy evaluation.
- The blind adjudication package (``build_blind_adjudication_package``)
  strips grades, confidence values, rationales, and any rank/score signals.
  It exposes only the case query, candidate titles/abstracts, domain, surface,
  intent, and slice context (slice context is retained because it tells the
  adjudicator what failure mode the case is exercising; grades/scores are the
  contamination risk, not the slice label).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from backend.ranking.benchmark_v2_discovery_cases import (
    _DISCOVERY_LEXICAL_TRAP,
    _DISCOVERY_SEMANTIC_PARAPHRASE,
    _DISCOVERY_METHOD_VS_APPLICATION,
    _DISCOVERY_REVIEW_VS_PRIMARY,
    _DISCOVERY_MISSING_ABSTRACT,
    _DISCOVERY_NEAR_DUPLICATE,
    _DISCOVERY_SOURCE_RANK_CONFLICT,
    _DISCOVERY_ACRONYM_VS_EXPANDED,
    _DISCOVERY_NEGATED_FINDINGS,
    _DISCOVERY_EXACT_IDENTIFIER,
    _DISCOVERY_NEUTRAL,
)
from backend.ranking.benchmark_v2_retrieval_cases import (
    _RETRIEVAL_LEXICAL_TRAP,
    _RETRIEVAL_SEMANTIC_PARAPHRASE,
    _RETRIEVAL_METHOD_VS_APPLICATION,
    _RETRIEVAL_REVIEW_VS_PRIMARY,
    _RETRIEVAL_MISSING_ABSTRACT,
    _RETRIEVAL_NEAR_DUPLICATE,
    _RETRIEVAL_SOURCE_RANK_CONFLICT,
    _RETRIEVAL_ACRONYM_VS_EXPANDED,
    _RETRIEVAL_NEGATED_FINDINGS,
    _RETRIEVAL_EXACT_IDENTIFIER,
    _RETRIEVAL_NEUTRAL,
)
from backend.ranking.benchmark_v2_schema import (
    ALL_SLICE_TYPES,
    BenchmarkCaseV2,
    DISAGREE_NONE,
    DISAGREE_RESOLVED,
    DISAGREE_SINGLE_PASS,
    DISAGREE_UNRESOLVED,
    REQUIRED_ADVERSARIAL_SLICES,
)

BENCHMARK_V2_VERSION = "discovery_ranking_v2+retrieval_ranking_v2"
RUBRIC_V2 = "research_utility_0_to_3_v1"  # same rubric, richer provenance

ALL_DISCOVERY_V2: tuple[BenchmarkCaseV2, ...] = tuple(
    _DISCOVERY_LEXICAL_TRAP
    + _DISCOVERY_SEMANTIC_PARAPHRASE
    + _DISCOVERY_METHOD_VS_APPLICATION
    + _DISCOVERY_REVIEW_VS_PRIMARY
    + _DISCOVERY_MISSING_ABSTRACT
    + _DISCOVERY_NEAR_DUPLICATE
    + _DISCOVERY_SOURCE_RANK_CONFLICT
    + _DISCOVERY_ACRONYM_VS_EXPANDED
    + _DISCOVERY_NEGATED_FINDINGS
    + _DISCOVERY_EXACT_IDENTIFIER
    + _DISCOVERY_NEUTRAL
)

ALL_RETRIEVAL_V2: tuple[BenchmarkCaseV2, ...] = tuple(
    _RETRIEVAL_LEXICAL_TRAP
    + _RETRIEVAL_SEMANTIC_PARAPHRASE
    + _RETRIEVAL_METHOD_VS_APPLICATION
    + _RETRIEVAL_REVIEW_VS_PRIMARY
    + _RETRIEVAL_MISSING_ABSTRACT
    + _RETRIEVAL_NEAR_DUPLICATE
    + _RETRIEVAL_SOURCE_RANK_CONFLICT
    + _RETRIEVAL_ACRONYM_VS_EXPANDED
    + _RETRIEVAL_NEGATED_FINDINGS
    + _RETRIEVAL_EXACT_IDENTIFIER
    + _RETRIEVAL_NEUTRAL
)

ALL_V2_CASES: tuple[BenchmarkCaseV2, ...] = ALL_DISCOVERY_V2 + ALL_RETRIEVAL_V2

BENCHMARK_V2 = {
    "version": BENCHMARK_V2_VERSION,
    "discovery_cases": len(ALL_DISCOVERY_V2),
    "retrieval_cases": len(ALL_RETRIEVAL_V2),
    "total_cases": len(ALL_V2_CASES),
    "domains": ["machine_learning", "biomedical", "nlp"],
    "rubric_version": RUBRIC_V2,
    "splits": ["calibration", "development", "held_out"],
    "slice_vocabulary": list(ALL_SLICE_TYPES),
}


# ── Validation ───────────────────────────────────────────────────────


def validate_benchmark_v2() -> list[str]:
    """Validate the whole v2 benchmark. Returns list of errors (empty = OK)."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for case in ALL_V2_CASES:
        if case.case_id in seen_ids:
            errors.append(f"duplicate case_id: {case.case_id}")
        seen_ids.add(case.case_id)
        errors.extend(case.validate())
    # content_hash uniqueness within a case
    for case in ALL_V2_CASES:
        hashes = [c.content_hash for c in case.candidates]
        if len(hashes) != len(set(hashes)):
            errors.append(f"{case.case_id}: duplicate content_hash among candidates")
    return errors


def unresolved_disagreements() -> list[tuple[str, str]]:
    """List (case_id, candidate_id) with unresolved or pending-single-pass status.

    While the blind adjudicator has not yet run, every judgment is
    ``single_pass`` — this is expected at Gate 1, NOT a defect.
    """
    out: list[tuple[str, str]] = []
    for case in ALL_V2_CASES:
        for cid, prov in case.judgments.items():
            if prov.disagreement_status in (DISAGREE_UNRESOLVED, DISAGREE_SINGLE_PASS):
                out.append((case.case_id, cid))
    return out


def is_frozen() -> bool:
    """True only when every judgment has been adjudicated (none/resolved)."""
    return len(unresolved_disagreements()) == 0


# ── Fingerprints ─────────────────────────────────────────────────────


def _case_fingerprint_payload(case: BenchmarkCaseV2, use_final_grade: bool) -> dict[str, Any]:
    """Build the dict that contributes to the benchmark fingerprint.

    When ``use_final_grade`` is True, uses the adjudicated final grade; this
    is the value used for the post-adjudication frozen fingerprint. When
    False, uses the initial provisional grade (provisional fingerprint only).
    """
    judgments_payload = {}
    for cid, prov in case.judgments.items():
        grade = prov.final_grade() if use_final_grade else prov.initial.grade
        judgments_payload[cid] = {
            "grade": grade,
            "disagreement_status": prov.disagreement_status,
        }
    return {
        "case_id": case.case_id,
        "domain": case.research_domain,
        "surface": case.ranking_surface,
        "intent": case.ranking_intent,
        "query": case.query_text,
        "candidates": [c.candidate_id for c in case.candidates],
        "content_hashes": [c.content_hash for c in case.candidates],
        "primary_slice": case.primary_slice,
        "secondary_slices": list(case.secondary_slices),
        "split": case.split,
        "judgments": judgments_payload,
    }


def compute_benchmark_v2_fingerprint() -> str:
    """Frozen fingerprint of the v2 benchmark.

    REQUIRES that all judgments are adjudicated (no single-pass / unresolved).
    Raises ``RuntimeError`` if any judgment is still pending — this prevents
    freezing the benchmark before adjudication completes.
    """
    pending = unresolved_disagreements()
    if pending:
        raise RuntimeError(
            f"cannot freeze v2 fingerprint: {len(pending)} judgments still "
            f"pending adjudication (first: {pending[0]}). Run the blind "
            f"adjudication pass first, or use compute_provisional_fingerprint()."
        )
    payload = [_case_fingerprint_payload(c, use_final_grade=True) for c in ALL_V2_CASES]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def compute_provisional_fingerprint() -> str:
    """Provisional fingerprint over initial (single-pass) judgments.

    This is auditable evidence of the author's initial freeze. It MUST NOT be
    used for policy evaluation — use ``compute_benchmark_v2_fingerprint`` after
    adjudication.
    """
    payload = [_case_fingerprint_payload(c, use_final_grade=False) for c in ALL_V2_CASES]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


# ── Coverage report ──────────────────────────────────────────────────


def slice_coverage_report() -> dict[str, Any]:
    """Report slice × surface × domain coverage for the benchmark."""
    report: dict[str, Any] = {"by_slice": {}, "missing_required_slices": []}
    for slice_type in ALL_SLICE_TYPES:
        entry = {"discovery": 0, "retrieval": 0, "domains": set(), "splits": set()}
        for case in ALL_V2_CASES:
            matches = case.primary_slice == slice_type or slice_type in case.secondary_slices
            if not matches:
                continue
            surface_key = "discovery" if case.ranking_surface == "discovery_ranking" else "retrieval"
            entry[surface_key] += 1
            entry["domains"].add(case.research_domain)
            entry["splits"].add(case.split)
        entry["domains"] = sorted(entry["domains"])
        entry["splits"] = sorted(entry["splits"])
        report["by_slice"][slice_type] = entry
    for required in REQUIRED_ADVERSARIAL_SLICES:
        e = report["by_slice"].get(required, {})
        if e.get("discovery", 0) < 1 or e.get("retrieval", 0) < 1:
            report["missing_required_slices"].append(required)
    # split balance
    from collections import Counter
    report["split_counts"] = dict(Counter(c.split for c in ALL_V2_CASES))
    report["domain_counts"] = dict(Counter(c.research_domain for c in ALL_V2_CASES))
    report["surface_counts"] = {
        "discovery": sum(1 for c in ALL_V2_CASES if c.ranking_surface == "discovery_ranking"),
        "retrieval": sum(1 for c in ALL_V2_CASES if c.ranking_surface == "retrieval_ranking"),
    }
    return report


# ── Blinded adjudication package ─────────────────────────────────────


def build_blind_adjudication_package() -> dict[str, Any]:
    """Build the blinded package for second-pass annotation.

    Strips from each judgment: grade, confidence, rationale, and any
    disagreement status. Retains: case metadata (domain, surface, intent,
    slice context), query text, candidate titles+abstracts, content hashes,
    and candidate_id (so the adjudicator can reference candidates).

    The adjudicator receives this package and returns grades+confidence for
    each (case_id, candidate_id). Those are reconciled into JudgmentProvenance
    via ``adjudicate_benchmark`` after the blind pass.
    """
    cases_payload = []
    for case in ALL_V2_CASES:
        candidates_payload = []
        for c in case.candidates:
            candidates_payload.append({
                "candidate_id": c.candidate_id,
                "title": c.title,
                "abstract": c.abstract,
                "content_hash": c.content_hash,
                "source_rank": c.source_rank,
                "near_duplicate_of": c.near_duplicate_of,
            })
        cases_payload.append({
            "case_id": case.case_id,
            "domain": case.research_domain,
            "surface": case.ranking_surface,
            "intent": case.ranking_intent,
            "primary_slice": case.primary_slice,
            "secondary_slices": list(case.secondary_slices),
            "split": case.split,
            "query_text": case.query_text,
            "candidates": candidates_payload,
            # Deliberately omit: judgments (grade/confidence/rationale/disagreement).
        })
    return {
        "package_version": "blind_adjudication_v1",
        "benchmark_version": BENCHMARK_V2_VERSION,
        "rubric_version": RUBRIC_V2,
        "instructions": (
            "For each (case_id, candidate_id), assign a relevance grade 0-3 "
            "(0=irrelevant, 3=highly useful) and an annotation confidence "
            "0.0-1.0, plus a short rubric-based rationale. Do NOT consult "
            "any policy output, score, or rank while annotating. Return the "
            "same JSON shape populated under 'judgments'."
        ),
        "cases": cases_payload,
    }
