"""P1B.1: Helpers for constructing v2 benchmark cases compactly.

Keeps the authored case tables readable while enforcing the v2 schema
invariants (content hashes, provenance fields, slice vocabulary).
"""

from __future__ import annotations

import hashlib

from backend.ranking.benchmark_v2_schema import (
    ALL_SLICE_TYPES,
    ANNOTATOR_INITIAL,
    DISAGREE_SINGLE_PASS,
    AnnotationPass,
    BenchmarkCandidateV2,
    BenchmarkCaseV2,
    JudgmentProvenance,
)


def _content_hash(title: str, abstract: str) -> str:
    return hashlib.sha256(f"{title}\n\n{abstract}".encode()).hexdigest()


def candidate(
    cid: str,
    title: str,
    abstract: str,
    *,
    source_rank: int | None = None,
    near_duplicate_of: str | None = None,
    **extra,
) -> BenchmarkCandidateV2:
    """Build a v2 candidate. ``abstract=""`` is allowed for the missing-abstract slice."""
    return BenchmarkCandidateV2(
        candidate_id=cid,
        title=title,
        abstract=abstract,
        content_hash=_content_hash(title, abstract),
        source_rank=source_rank,
        near_duplicate_of=near_duplicate_of,
        metadata=extra or {},
    )


def initial_pass(
    grade: int,
    *,
    topical: int | None = None,
    evidence: int | None = None,
    method: int | None = None,
    confidence: float = 0.9,
    rationale: str,
) -> AnnotationPass:
    """First-pass (provisional) annotation by the synthetic author."""
    return AnnotationPass(
        annotator=ANNOTATOR_INITIAL,
        grade=grade,
        topical_relevance=topical if topical is not None else grade,
        evidence_utility=evidence if evidence is not None else grade,
        methodological_fit=method if method is not None else grade,
        annotation_confidence=confidence,
        rationale=rationale,
    )


def provenance(
    grade: int,
    *,
    topical: int | None = None,
    evidence: int | None = None,
    method: int | None = None,
    confidence: float = 0.9,
    rationale: str,
) -> JudgmentProvenance:
    """Convenience: a single-pass provenance (second_pass=None, adjudicated=None).

    Used for the provisional benchmark freeze. The blind adjudicator fills in
    ``second_pass``; disagreements are then resolved into ``adjudicated_grade``.
    """
    return JudgmentProvenance(
        initial=initial_pass(
            grade, topical=topical, evidence=evidence, method=method,
            confidence=confidence, rationale=rationale,
        ),
        second_pass=None,
        adjudicated_grade=None,
        adjudicated_confidence=None,
        disagreement_status=DISAGREE_SINGLE_PASS,
    )


def case(
    case_id: str,
    domain: str,
    surface: str,
    intent: str,
    query: str,
    candidates: tuple[BenchmarkCandidateV2, ...],
    judgments: dict[str, JudgmentProvenance],
    split: str,
    primary_slice: str,
    secondary_slices: tuple[str, ...] = (),
) -> BenchmarkCaseV2:
    if primary_slice not in ALL_SLICE_TYPES:
        raise ValueError(f"unknown slice {primary_slice!r} for {case_id}")
    for s in secondary_slices:
        if s not in ALL_SLICE_TYPES:
            raise ValueError(f"unknown secondary slice {s!r} for {case_id}")
    return BenchmarkCaseV2(
        case_id=case_id,
        research_domain=domain,
        ranking_surface=surface,
        ranking_intent=intent,
        query_text=query,
        candidates=candidates,
        judgments=judgments,
        split=split,
        primary_slice=primary_slice,
        secondary_slices=secondary_slices,
    )
