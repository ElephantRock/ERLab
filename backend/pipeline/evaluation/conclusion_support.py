"""Productive-1 R6 — canonical conclusion-support semantics (shared rule).

R6 frozen charter (owner, 2026-08-31): screening and authoritative
evaluation must use ONE extraction implementation and ONE empirical-
claim rule. This module IS that rule: it reproduces the pre-R6
authoritative stage behavior (``PaperSynthesisStage._classify_conclusion``)
verbatim — full-section Abstract extraction, Conclusion/Discussion
extraction, the four empirical-assertion patterns, the ±200-character
[RESULT-N] backing search, the result_markers/has_empirical_results
handling, and the forced ``overstated`` outcome for unmapped empirical
claims. Nothing is weakened and nothing is added beyond the structured
claim positions that deterministic R-REMOVE targeting needs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_RESULT_MARKER_RE = re.compile(r"\[RESULT-(\d+)\]")

# The canonical empirical-assertion patterns (order preserved from the
# pre-R6 stage implementation).
EMPIRICAL_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bwe\s+demonstrate\b", "we demonstrate"),
    (r"\bdemonstrates?\s+that\b", "demonstrates that"),
    (r"\bexperimental\s+results?\b.{0,40}\b(show|indicate)\b", "experimental results show"),
    (r"\bresults?\s+(show|indicate)\s+that\b", "results show that"),
)


@dataclass
class EmpiricalClaim:
    """One empirical-assertion pattern match, with its position.

    ``start``/``end`` are offsets in the joined abstract+conclusion text
    this assessment was computed from; ``backed`` records whether a
    [RESULT-N] marker sits within ±200 characters of the match.
    """

    label: str
    matched_text: str
    start: int
    end: int
    backed: bool


@dataclass
class ConclusionSupportAssessment:
    classification: str
    reason: str
    indicators: list[str]
    abstract: str
    conclusion: str
    unmapped_claims: list[EmpiricalClaim] = field(default_factory=list)
    mapped_claims: list[EmpiricalClaim] = field(default_factory=list)

    def as_result(self):
        """The pre-R6 ConclusionSupportResult shape, for existing callers."""
        from backend.pipeline.evaluation.conclusion_checker import (
            ConclusionSupportResult,
        )

        return ConclusionSupportResult(
            classification=self.classification,
            reason=self.reason,
            indicators=self.indicators,
        )

    @property
    def joined_text(self) -> str:
        return f"{self.abstract}\n{self.conclusion}"


def extract_abstract_and_conclusion(paper_md: str) -> tuple[str, str]:
    """Full-section extraction, verbatim from the pre-R6 stage behavior."""
    abstract = ""
    conclusion = ""
    if paper_md:
        lines = paper_md.splitlines()
        # Abstract block.
        abs_lines: list[str] = []
        in_section = False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "abstract" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                abs_lines.append(s)
        abstract = " ".join(abs_lines)
        # Conclusion block (Discussion headings count as conclusion).
        conc_lines: list[str] = []
        in_section = False
        for ln in lines:
            s = ln.strip()
            low = s.lower()
            if s.startswith("#"):
                if "conclusion" in low or "discussion" in low:
                    in_section = True
                    continue
                if in_section:
                    in_section = False
                continue
            if in_section and s:
                conc_lines.append(s)
        conclusion = " ".join(conc_lines)
    return abstract, conclusion


def _infer_has_results(paper_md: str) -> bool:
    """has_empirical_results heading inference, verbatim from the stage."""
    has_results = False
    if paper_md:
        lower = paper_md.lower()
        has_results_heading = any(
            h in lower for h in ("## results", "# results")
        )
        has_expected_results = "expected results" in lower
        has_experiments_heading = any(
            h in lower for h in ("## experiments", "# experiments",
                                 "## experimental setup", "# experimental setup")
        )
        has_results = (
            has_results_heading and not has_expected_results
        ) or has_experiments_heading
    return has_results


def evaluate_conclusion_support(
    paper_md: str, result_markers=None,
) -> ConclusionSupportAssessment:
    """The canonical shared rule — behaviorally identical to the pre-R6
    authoritative stage classification, with structured claim positions.

    ``result_markers`` is a list of ResultMarker objects (or None). When
    markers exist, empirical assertions in abstract/conclusion must carry
    a [RESULT-N] within ±200 characters or the classification is forced
    to ``overstated``.
    """
    from backend.pipeline.evaluation.conclusion_checker import (
        classify_conclusion_support,
    )

    abstract, conclusion = extract_abstract_and_conclusion(paper_md)
    has_results = _infer_has_results(paper_md)

    result_backed = False
    unmapped: list[EmpiricalClaim] = []
    mapped: list[EmpiricalClaim] = []
    if result_markers:
        cited_markers = set(_RESULT_MARKER_RE.findall(paper_md or ""))
        available_markers = {str(m.marker_index) for m in result_markers}
        if cited_markers & available_markers:
            result_backed = True  # at least one empirical claim is backed

        text = f"{abstract}\n{conclusion}"
        for pattern, label in EMPIRICAL_CLAIM_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                start = max(0, m.start() - 200)
                end = min(len(text), m.end() + 200)
                context = text[start:end]
                claim = EmpiricalClaim(
                    label=label,
                    matched_text=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    backed=bool(_RESULT_MARKER_RE.search(context)),
                )
                (mapped if claim.backed else unmapped).append(claim)

    if result_markers:
        has_empirical = result_backed
    elif has_results:
        has_empirical = True
    else:
        has_empirical = None  # let the checker infer

    result = classify_conclusion_support(
        abstract=abstract,
        conclusion=conclusion,
        has_empirical_results=has_empirical,
    )

    if result_markers and unmapped:
        unmapped_labels = [
            f"empirical claim '{c.label}' without [RESULT-N] backing"
            for c in unmapped
        ]
        return ConclusionSupportAssessment(
            classification="overstated",
            reason=(
                f"Experiment succeeded but {len(unmapped_labels)} empirical claim(s) "
                f"lack [RESULT-N] backing: {'; '.join(unmapped_labels[:3])}"
            ),
            indicators=unmapped_labels,
            abstract=abstract,
            conclusion=conclusion,
            unmapped_claims=unmapped,
            mapped_claims=mapped,
        )

    return ConclusionSupportAssessment(
        classification=result.classification,
        reason=result.reason,
        indicators=list(result.indicators or []),
        abstract=abstract,
        conclusion=conclusion,
        unmapped_claims=unmapped,
        mapped_claims=mapped,
    )
