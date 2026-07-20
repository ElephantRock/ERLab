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
    JudgmentProvenance,
    REQUIRED_ADVERSARIAL_SLICES,
    RESEARCH_UTILITY_RUBRIC_V1,
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
    """Frozen fingerprint of the v2 benchmark (post-Gate-1).

    Computed over the FROZEN adjudicated view: same candidate pools / splits /
    queries as the provisional v2, but with each judgment's grade set to the
    adjudicated final grade from the blind adjudication pass.

    REQUIRES that the frozen-adjudication module covers every judgment.
    Raises ``RuntimeError`` otherwise.
    """
    if not is_gate1_complete():
        raise RuntimeError(
            "cannot freeze v2 fingerprint: frozen adjudication module does not "
            "cover every v2 judgment. Run the blind adjudication pass and "
            "regenerate benchmark_v2_frozen_adjudication.py."
        )
    frozen = frozen_v2_cases()
    payload = [_case_fingerprint_payload(c, use_final_grade=True) for c in frozen]
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


# ── Frozen adjudicated view ──────────────────────────────────────────
#
# After Gate 1 blind adjudication, the authoritative evaluation view is
# the FROZEN set of cases: same candidate pools / splits / queries as the
# provisional v2 cases, but with each JudgmentProvenance carrying the full
# annotation trail (initial + blind second-pass + adjudicated grade).
#
# Source of truth: backend/ranking/benchmark_v2_frozen_adjudication.py
# (generated from the SHA-256-verified adjudication package).

from backend.ranking.benchmark_v2_frozen_adjudication import (  # noqa: E402
    get_frozen_adjudication,
    frozen_provenance_count,
)


def _frozen_judgment(case_id: str, candidate_id: str, initial_prov) -> JudgmentProvenance | None:
    """Overlay the frozen second-pass + adjudicated grade onto an initial pass."""
    frozen = get_frozen_adjudication(case_id, candidate_id)
    if frozen is None:
        return None
    second_pass, adjudicated_grade, disagreement_status = frozen
    # adjudicated_confidence: use the second-pass confidence; the adjudicator
    # confirmed the grade and did not revise confidence separately.
    return JudgmentProvenance(
        initial=initial_prov.initial,
        second_pass=second_pass,
        adjudicated_grade=adjudicated_grade,
        adjudicated_confidence=second_pass.annotation_confidence,
        disagreement_status=disagreement_status,
    )


def frozen_v2_cases() -> tuple[BenchmarkCaseV2, ...]:
    """Return v2 cases overlaid with frozen adjudication provenance.

    Each case is reconstructed with full JudgmentProvenance (initial + blind
    second-pass + adjudicated grade). Raises if any case/candidate lacks a
    frozen record (which would indicate the adjudication package is incomplete
    or the registry drifted from the frozen module).
    """
    from backend.ranking.benchmark_v2_schema import BenchmarkCaseV2 as _C
    frozen_cases: list[BenchmarkCaseV2] = []
    for case in ALL_V2_CASES:
        new_judgments = {}
        for cid, prov in case.judgments.items():
            fj = _frozen_judgment(case.case_id, cid, prov)
            if fj is None:
                raise RuntimeError(
                    f"{case.case_id}/{cid}: no frozen adjudication record; "
                    f"regenerate benchmark_v2_frozen_adjudication.py"
                )
            new_judgments[cid] = fj
        frozen_cases.append(_C(
            case_id=case.case_id,
            research_domain=case.research_domain,
            ranking_surface=case.ranking_surface,
            ranking_intent=case.ranking_intent,
            query_text=case.query_text,
            candidates=case.candidates,
            judgments=new_judgments,
            split=case.split,
            primary_slice=case.primary_slice,
            secondary_slices=case.secondary_slices,
        ))
    return tuple(frozen_cases)


def frozen_v2_discovery_cases() -> tuple[BenchmarkCaseV2, ...]:
    return tuple(c for c in frozen_v2_cases() if c.ranking_surface == "discovery_ranking")


def frozen_v2_retrieval_cases() -> tuple[BenchmarkCaseV2, ...]:
    return tuple(c for c in frozen_v2_cases() if c.ranking_surface == "retrieval_ranking")


def is_gate1_complete() -> bool:
    """True iff the frozen adjudication module covers every v2 judgment.

    This is the post-Gate-1 freeze predicate. When True,
    ``compute_benchmark_v2_fingerprint()`` will succeed and the benchmark is
    ready for P1B.2 (embedding snapshot generation).
    """
    total = sum(len(c.judgments) for c in ALL_V2_CASES)
    return frozen_provenance_count() == total


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


def _deterministic_shuffle(items: list, seed: str) -> list:
    """Reproducible shuffle keyed by ``seed`` (case_id). Pure-python, no deps."""
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    items = list(items)
    n = len(items)
    for i in range(n - 1, 0, -1):
        h = (h * 6364136223846793005 + 1) & 0xFFFFFFFFFFFFFFFF
        j = h % (i + 1)
        items[i], items[j] = items[j], items[i]
    return items


# Per-case adjudication context. Tells the adjudicator what the case is
# asking about without revealing author identity, splits, or judgments.
_CONTEXT_BY_SURFACE_INTENT = {
    ("discovery_ranking", "general_research_relevance"): (
        "Discovery surface: a researcher is exploring the literature for an "
        "open-ended research question. Rank by how useful each candidate is "
        "as a starting point."
    ),
    ("discovery_ranking", "method_relevance"): (
        "Discovery surface: the researcher wants METHODS or ALGORITHMS, not "
        "applications or surveys. Penalize reviews and downstream "
        "application papers unless they introduce a method."
    ),
    ("discovery_ranking", "evidence_support"): (
        "Discovery surface: the researcher wants PRIMARY EVIDENCE (empirical "
        "results, RCTs, measured outcomes). Reviews and editorials are lower "
        "utility unless they directly synthesize the requested evidence."
    ),
    ("discovery_ranking", "literature_mapping"): (
        "Discovery surface: the researcher wants to map the literature around "
        "a specific named entity (paper, model, gene, drug). Canonical and "
        "directly-named works rank highest."
    ),
    ("retrieval_ranking", "general_research_relevance"): (
        "Retrieval surface: short keyword-style query against a candidate "
        "pool. Rank by topical + evidence utility."
    ),
    ("retrieval_ranking", "evidence_support"): (
        "Retrieval surface: rank by strength of primary evidence."
    ),
    ("retrieval_ranking", "method_relevance"): (
        "Retrieval surface: rank by method/algorithm relevance."
    ),
    ("retrieval_ranking", "literature_mapping"): (
        "Retrieval surface: rank by directness of match to the named entity."
    ),
}


def _research_question(case: BenchmarkCaseV2) -> str:
    """Frame the query as a research question for the adjudicator."""
    return case.query_text


def build_blind_adjudication_package_v2() -> dict[str, Any]:
    """Protocol-compliant blind adjudication package (Gate 1 v2).

    Compliant with the frozen Gate 1 contract:

    Includes per case:
      - case_id
      - ranking_surface
      - research_question (the query text)
      - ranking_intent (frames what kind of match is wanted)
      - adjudication_context (rubric-anchored guidance for the surface+intent)
      - domain (research domain)
      - relevance rubric reference
      - candidates with: candidate_id, title, abstract (canonical text),
        content_hash, source_rank, near_duplicate_of
      - candidates are DETERMINISTICALLY SHUFFLED per case (seeded by case_id)
        so order does not leak provisional/baseline rank

    Excludes per the contract:
      - provisional relevance grades
      - provisional confidence
      - provisional rationales
      - policy scores / semantic scores
      - baseline ranks / candidate policy ranks
      - split labels (could bias judgment toward held-out caution)
      - author identity / provenance
      - primary_slice / secondary_slices are RETAINED because they describe
        what failure mode the case exercises (this is context, not a grade);
        the contract excludes grades/scores/ranks, not slice labels.
    """
    rubric = RESEARCH_UTILITY_RUBRIC_V1
    cases_payload = []
    for case in ALL_V2_CASES:
        candidates = [
            {
                "candidate_id": c.candidate_id,
                "title": c.title,
                "abstract": c.abstract,  # canonical assessment text
                "content_hash": c.content_hash,
                "source_rank": c.source_rank,
                "near_duplicate_of": c.near_duplicate_of,
            }
            for c in case.candidates
        ]
        # Deterministic shuffle so candidate order does not leak author rank.
        shuffled = _deterministic_shuffle(candidates, seed=case.case_id)
        context = _CONTEXT_BY_SURFACE_INTENT.get(
            (case.ranking_surface, case.ranking_intent),
            f"{case.ranking_surface} / {case.ranking_intent}: rank by research utility.",
        )
        cases_payload.append({
            "case_id": case.case_id,
            "ranking_surface": case.ranking_surface,
            "research_question": _research_question(case),
            "ranking_intent": case.ranking_intent,
            "adjudication_context": context,
            "domain": case.research_domain,
            "relevance_rubric_version": rubric["rubric_version"],
            # Slice labels retained as context (describe failure mode, not a grade).
            "primary_slice": case.primary_slice,
            "secondary_slices": list(case.secondary_slices),
            "candidates": shuffled,
            # Excluded deliberately: split, judgments, grades, confidence,
            # rationales, author provenance, policy scores, ranks.
        })
    return {
        "package_version": "blind_adjudication_v2",
        "package_compliance": {
            "includes": [
                "case_id", "ranking_surface", "research_question",
                "ranking_intent", "adjudication_context", "domain",
                "relevance_rubric_version", "primary_slice (context only)",
                "secondary_slices (context only)", "candidates with id/title/"
                "abstract/content_hash/source_rank/near_duplicate_of",
            ],
            "excludes": [
                "provisional relevance grades", "provisional confidence",
                "provisional rationales", "policy scores", "semantic scores",
                "baseline ranks", "candidate policy ranks",
                "split labels (biasing)", "author identity / provenance",
            ],
            "candidate_ordering": (
                "deterministically shuffled per case (seeded by case_id, "
                "sha256-derived LCG) so order does not leak provisional rank"
            ),
        },
        "benchmark_version": BENCHMARK_V2_VERSION,
        "rubric": rubric,
        "instructions": (
            "For each (case_id, candidate_id), independently assign: "
            "(1) relevance grade 0-3 per the rubric; (2) annotation "
            "confidence 0.0-1.0; (3) a brief rubric-referenced rationale; "
            "(4) specialist_review_needed (true if the candidate requires "
            "specialist knowledge you cannot reliably judge). Do NOT consult "
            "any provisional judgment, policy score, semantic score, or "
            "rank while annotating. Return the populated package with a "
            "'judgments' object per case: {candidate_id: {grade, confidence, "
            "rationale, specialist_review_needed}}."
        ),
        "output_schema_example": {
            "<case_id>": {
                "<candidate_id>": {
                    "grade": "0|1|2|3",
                    "confidence": "0.0-1.0",
                    "rationale": "short rubric-referenced reason",
                    "specialist_review_needed": "true|false",
                }
            }
        },
        "cases": cases_payload,
    }
