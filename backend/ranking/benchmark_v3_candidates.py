"""P1E.1 — Grade-free v3 candidate schema and corpus.

A SEPARATE collection from the frozen P1B v2 (`ALL_V2_CASES`). Importing this
module does NOT touch v2; v2 stays 100% immutable (its fingerprint
`0ffbfdb1…` is load-bearing for the P1E.0 manifest runtime gate).

Candidate-layer purity (protocol §4 of the Commit-2 gate): the candidate layer
recursively EXCLUDES all judgment-bearing fields:

    grade, relevance, expected_grade, gold, label, judgment, judgment_rationale,
    is_relevant, is_hard_negative, weak_positive, adjudicated

Construction metadata expresses ONLY provenance and intent:

    constructed_near_duplicate, constructed_lexical_trap,
    query_generation_anchor_candidate_id, mining_method, mining_rationale,
    near_duplicate_of (parent candidate_id, construction provenance only)

Lineage is explicit and version-prefixed: every v3 case/candidate has a
distinct ID namespace (`v3_…`) so v2/v3 ID collisions are impossible by
construction. For v2-derived content, `parent_v2_*` records the origin and
`content_unchanged` is proven by hash equality, not by label.

Composition (frozen in the sealed protocol d2e16ae):
    total v3 cases          88
    calibration             33   (22 v2-lineage + 11 fully-new)
    development             33   (22 v2-lineage + 11 fully-new)
    held_out                22   (22 fully-new; 0 v2 held-out lineage)
    v2-lineage (extended)   44
    fully-new               44
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from backend.ranking.p1e1_canon import content_hash

# ── Grade-free candidate schema ──────────────────────────────────────


@dataclass(frozen=True)
class V3Candidate:
    """A grade-free v3 benchmark candidate.

    No field may assert a relevance grade or judgment. ``mining_role`` and
    ``near_duplicate_of`` are construction provenance/intent only.
    """

    candidate_id: str                       # v3-prefixed, collision-proof
    title: str
    abstract: str                           # may be "" for missing-abstract slice
    content_hash: str                       # sha256(canonical "{title}\n\n{abstract}")
    source_rank: int | None = None          # synthetic upstream priority (slice exercise)
    near_duplicate_of: str | None = None    # parent candidate_id (construction provenance)
    mining_role: str | None = None          # construction intent ONLY (see allowed set)
    query_generation_anchor: bool = False   # construction-only anchor; carries NO grade
    parent_v2_candidate_id: str | None = None  # lineage (None for fully-new candidates)
    content_unchanged_from_parent: bool = False
    metadata: Mapping[str, object] = field(default_factory=dict, hash=False)


ALLOWED_MINING_ROLES = frozenset({
    "constructed_lexical_trap",
    "constructed_near_duplicate",
    "constructed_hard_negative",   # intended nonrelevant confuser (pre-adjudication)
    "mined_for_likely_confusion",
    "v2_preserved",
    "fully_new_relevant_seed",     # construction anchor for query generation
})


def v3_candidate(
    candidate_id: str,
    title: str,
    abstract: str,
    *,
    source_rank: int | None = None,
    near_duplicate_of: str | None = None,
    mining_role: str | None = None,
    query_generation_anchor: bool = False,
    parent_v2_candidate_id: str | None = None,
    content_unchanged_from_parent: bool = False,
    **extra,
) -> V3Candidate:
    """Construct a grade-free v3 candidate. Validates mining_role purity."""
    if mining_role is not None and mining_role not in ALLOWED_MINING_ROLES:
        raise ValueError(f"disallowed mining_role {mining_role!r}; use one of {sorted(ALLOWED_MINING_ROLES)}")
    return V3Candidate(
        candidate_id=candidate_id,
        title=title,
        abstract=abstract,
        content_hash=content_hash(title, abstract),
        source_rank=source_rank,
        near_duplicate_of=near_duplicate_of,
        mining_role=mining_role,
        query_generation_anchor=query_generation_anchor,
        parent_v2_candidate_id=parent_v2_candidate_id,
        content_unchanged_from_parent=content_unchanged_from_parent,
        metadata=extra or {},
    )


@dataclass(frozen=True)
class V3CandidateCase:
    """A grade-free v3 benchmark case (a query + its candidate pool)."""

    case_id: str                            # v3-prefixed
    research_domain: str                    # machine_learning | biomedical | nlp
    ranking_surface: str                    # discovery_ranking | retrieval_ranking
    ranking_intent: str
    query_text: str
    candidates: tuple[V3Candidate, ...]     # DECLARED order (frozen; part of identity)
    split: str                              # calibration | development | held_out
    primary_slice: str
    secondary_slices: tuple[str, ...] = ()
    parent_v2_case_id: str | None = None    # lineage (None for fully-new cases)
    lineage_type: str = "fully_new"         # fully_new | v2_extended
    # The query-generation anchor candidate for this case (construction-only;
    # no grade). Used only by the constructed-lexical-trap rule.
    query_generation_anchor_candidate_id: str | None = None


def v3_case(
    case_id: str,
    domain: str,
    surface: str,
    intent: str,
    query: str,
    candidates: tuple[V3Candidate, ...],
    split: str,
    primary_slice: str,
    *,
    secondary_slices: tuple[str, ...] = (),
    parent_v2_case_id: str | None = None,
    lineage_type: str = "fully_new",
    query_generation_anchor_candidate_id: str | None = None,
) -> V3CandidateCase:
    return V3CandidateCase(
        case_id=case_id,
        research_domain=domain,
        ranking_surface=surface,
        ranking_intent=intent,
        query_text=query,
        candidates=candidates,
        split=split,
        primary_slice=primary_slice,
        secondary_slices=secondary_slices,
        parent_v2_case_id=parent_v2_case_id,
        lineage_type=lineage_type,
        query_generation_anchor_candidate_id=query_generation_anchor_candidate_id,
    )


# The corpus itself is populated by `benchmark_v3_corpus.py` (a separate module
# that holds the 88 case definitions) to keep schema and data separate.
# Importing this module does NOT execute the corpus construction.
