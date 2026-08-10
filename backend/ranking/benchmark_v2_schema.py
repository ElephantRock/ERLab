"""P1B.1: Benchmark schema v2 — richer provenance for blind adjudication.

Extends the v1 benchmark schema (in benchmark_cases.py) with:

- adversarial slice classification (one of the 10 required slice types)
- annotation provenance: initial, second-pass, adjudicated annotations
- disagreement tracking
- short criterion-based rationale per judgment
- a separately-versioned fingerprint that includes the new fields

Design notes
------------
- v1 cases and ``compute_benchmark_fingerprint`` are intentionally left
  untouched so the frozen v1 baseline fingerprint and its tests stay stable.
- v2 judgment provenance is OPTIONAL on the dataclass so v1 cases can still
  be constructed without modification, but the v2 fingerprint requires the
  provenance fields to be populated.
- Slice vocabulary is a closed, frozen tuple. A case's ``primary_slice``
  names the dominant failure mode the case is designed to exercise; a case
  may also carry ``secondary_slices`` when multiple failure modes apply.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

# ── Adversarial slice vocabulary (closed) ────────────────────────────

SLICE_LEXICAL_TRAP = "lexical_trap"
SLICE_SEMANTIC_PARAPHRASE = "semantic_paraphrase"
SLICE_METHOD_VS_APPLICATION = "method_vs_application"
SLICE_REVIEW_VS_PRIMARY = "review_vs_primary"
SLICE_MISSING_ABSTRACT = "missing_abstract"
SLICE_NEAR_DUPLICATE = "near_duplicate"
SLICE_SOURCE_RANK_CONFLICT = "source_rank_conflict"
SLICE_ACRONYM_VS_EXPANDED = "acronym_vs_expanded"
SLICE_NEGATED_FINDINGS = "negated_findings"
SLICE_EXACT_IDENTIFIER = "exact_identifier"
SLICE_NEUTRAL = "neutral"  # non-adversarial baseline case

REQUIRED_ADVERSARIAL_SLICES: tuple[str, ...] = (
    SLICE_LEXICAL_TRAP,
    SLICE_SEMANTIC_PARAPHRASE,
    SLICE_METHOD_VS_APPLICATION,
    SLICE_REVIEW_VS_PRIMARY,
    SLICE_MISSING_ABSTRACT,
    SLICE_NEAR_DUPLICATE,
    SLICE_SOURCE_RANK_CONFLICT,
    SLICE_ACRONYM_VS_EXPANDED,
    SLICE_NEGATED_FINDINGS,
    SLICE_EXACT_IDENTIFIER,
)

ALL_SLICE_TYPES: tuple[str, ...] = REQUIRED_ADVERSARIAL_SLICES + (SLICE_NEUTRAL,)


# ── Disagreement status (closed) ─────────────────────────────────────

DISAGREE_NONE = "none"                       # both passes agreed
DISAGREE_RESOLVED = "resolved"               # disagreement, adjudicated
DISAGREE_UNRESOLVED = "unresolved"           # blocks benchmark freeze
DISAGREE_SINGLE_PASS = "single_pass"         # only one pass run so far


# ── Annotation provenance ────────────────────────────────────────────

ANNOTATOR_INITIAL = "initial_synthetic_author"
ANNOTATOR_SECOND_PASS = "blind_adjudicator"
ANNOTATOR_ADJUDICATOR = "adjudicator"


# ── Rubric definition (research_utility_0_to_3_v1) ───────────────────
#
# Explicit, criterion-anchored definition of the grading rubric so that
# every annotator (initial author, blind adjudicator, final adjudicator)
# applies the same criteria. The holistic 0-3 grade is the primary key;
# the three sub-dimensions are evidence that anchors the holistic grade.

RESEARCH_UTILITY_RUBRIC_V1 = {
    "rubric_version": "research_utility_0_to_3_v1",
    "primary_grade_scale": "0-3 holistic research utility",
    "criteria": {
        "topical_relevance": (
            "Does the candidate address the same research question / intent "
            "as the query? (0 = unrelated topic, 3 = directly on-topic)"
        ),
        "evidence_utility": (
            "Would a researcher asking this query find this candidate useful "
            "as evidence? (0 = not useful, 3 = highly useful)"
        ),
        "methodological_fit": (
        "Does the candidate's method or study type match what the query is "
            "asking for (method, application, review, primary study)? "
            "(0 = wrong type, 3 = exactly the right type)"
        ),
    },
    "grade_anchors": {
        "3": "Highly useful: directly on-topic, strong evidence, right type.",
        "2": "Useful: relevant but with caveats (broader scope, adjacent "
             "method, secondary source, partial match).",
        "1": "Marginally relevant: touches the topic but is not useful as "
             "primary evidence for the query.",
        "0": "Irrelevant: wrong meaning, wrong domain, or unrelated topic. "
             "Includes lexical traps (high token overlap, wrong meaning) "
             "and acronym collisions.",
    },
    "missing_abstract_policy": (
        "When a candidate has no abstract, base the grade on the title and "
        "domain context only, and lower annotation_confidence accordingly. "
        "Do NOT assume relevance from the title alone if it is ambiguous."
    ),
    "specialist_review_flag_policy": (
        "If the candidate requires specialist domain knowledge that the "
        "annotator cannot reliably judge, set specialist_review_needed=true "
        "rather than forcing a grade. Such candidates are excluded from "
        "policy evaluation or routed for external review."
    ),
}


@dataclass(frozen=True)
class AnnotationPass:
    """One annotation pass for one (case, candidate) judgment.

    Carries the grade + sub-dimensions + short rubric rationale recorded in a
    single pass. ``rationale`` MUST be criterion-based and short — it is audit
    evidence, not a free-form essay.
    """

    annotator: str
    grade: int                  # 0-3
    topical_relevance: int      # 0-3
    evidence_utility: int       # 0-3
    methodological_fit: int     # 0-3
    annotation_confidence: float  # 0.0-1.0
    rationale: str              # short, rubric-referenced reason


@dataclass(frozen=True)
class JudgmentProvenance:
    """Full annotation trail for one (case, candidate) judgment.

    - ``initial``: the provisional first-pass annotation by the benchmark author.
    - ``second_pass``: the blind adjudicator's annotation, or None before the
      blind pass is run.
    - ``adjudicated``: the frozen final grade used for evaluation. Equals
      ``initial.grade`` when ``second_pass`` is None and no disagreement exists;
      equals the adjudicator's decision when a disagreement was resolved.
    - ``disagreement_status``: closed vocabulary from the DISAGREE_* constants.
    """

    initial: AnnotationPass
    second_pass: AnnotationPass | None = None
    adjudicated_grade: int | None = None
    adjudicated_confidence: float | None = None
    disagreement_status: str = DISAGREE_SINGLE_PASS

    def final_grade(self) -> int:
        """The grade used for evaluation."""
        if self.adjudicated_grade is not None:
            return self.adjudicated_grade
        return self.initial.grade

    def final_confidence(self) -> float:
        if self.adjudicated_confidence is not None:
            return self.adjudicated_confidence
        return self.initial.annotation_confidence

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.disagreement_status not in (
            DISAGREE_NONE, DISAGREE_RESOLVED, DISAGREE_UNRESOLVED, DISAGREE_SINGLE_PASS,
        ):
            errors.append(f"invalid disagreement_status: {self.disagreement_status}")
        if self.disagreement_status == DISAGREE_UNRESOLVED:
            errors.append("unresolved disagreement blocks benchmark freeze")
        if self.disagreement_status == DISAGREE_NONE and self.second_pass is not None:
            if self.second_pass.grade != self.initial.grade and self.adjudicated_grade is None:
                errors.append("passes differ but adjudicated_grade is None")
        for label, ap in (("initial", self.initial), ("second_pass", self.second_pass)):
            if ap is None:
                continue
            if not (0 <= ap.grade <= 3):
                errors.append(f"{label}: grade {ap.grade} out of range")
            for dim_name, dim in (
                ("topical", ap.topical_relevance),
                ("evidence", ap.evidence_utility),
                ("methodological", ap.methodological_fit),
            ):
                if not (0 <= dim <= 3):
                    errors.append(f"{label}: {dim_name} {dim} out of range")
            if not (0.0 <= ap.annotation_confidence <= 1.0):
                errors.append(f"{label}: confidence {ap.annotation_confidence} out of range")
            if not ap.rationale or not ap.rationale.strip():
                errors.append(f"{label}: empty rationale")
        return errors


# ── v2 candidate ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class BenchmarkCandidateV2:
    """v2 benchmark candidate.

    ``source_rank`` is the synthetic upstream source priority (1 = highest)
    used to exercise the source-rank-conflict slice. ``None`` when not
    applicable. ``near_duplicate_of`` names another candidate_id in the same
    case when this candidate is a near-duplicate; ``None`` otherwise.
    """

    candidate_id: str
    title: str
    abstract: str                # may be "" for missing-abstract slice
    content_hash: str
    source_rank: int | None = None
    near_duplicate_of: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict, hash=False)


# ── v2 case ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BenchmarkCaseV2:
    """One benchmark case with full annotation provenance."""

    case_id: str
    research_domain: str
    ranking_surface: str          # discovery_ranking | retrieval_ranking
    ranking_intent: str
    query_text: str
    candidates: tuple[BenchmarkCandidateV2, ...]
    judgments: Mapping[str, JudgmentProvenance]  # candidate_id -> provenance
    split: str                    # calibration | development | held_out
    primary_slice: str            # one of ALL_SLICE_TYPES
    secondary_slices: tuple[str, ...] = ()

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.primary_slice not in ALL_SLICE_TYPES:
            errors.append(f"{self.case_id}: invalid primary_slice {self.primary_slice}")
        for s in self.secondary_slices:
            if s not in ALL_SLICE_TYPES:
                errors.append(f"{self.case_id}: invalid secondary_slice {s}")
        cand_ids = {c.candidate_id for c in self.candidates}
        judg_ids = set(self.judgments)
        missing = cand_ids - judg_ids
        if missing:
            errors.append(f"{self.case_id}: missing judgments for {missing}")
        extra = judg_ids - cand_ids
        if extra:
            errors.append(f"{self.case_id}: extra judgments for {extra}")
        for cid, prov in self.judgments.items():
            for e in prov.validate():
                errors.append(f"{self.case_id}/{cid}: {e}")
        if self.split not in ("calibration", "development", "held_out"):
            errors.append(f"{self.case_id}: invalid split {self.split}")
        return errors
