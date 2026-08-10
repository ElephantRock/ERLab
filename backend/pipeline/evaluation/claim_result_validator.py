"""Phase 10 / correction B — claim-to-result semantic validation.

Distinguishes:
  marker exists              (mechanical integrity)
  marker value is unchanged  (frozen evidence)
  marker role matches claim  (semantic validation)
  marker metric matches claim (semantic validation)

Blocks mismatches such as:
  "The model achieved [RESULT-1]"
  RESULT-1.role == baseline

This closes the false-ready defect where a baseline marker is credited
to the comparison model.

Numeric value-fidelity gate (2026-08-10): additionally blocks when the
number rendered beside a [RESULT-N] marker differs from that marker's
persisted ``observed_value``. This catches the revision-15 defect where
``966667 [RESULT-3]`` was released beside a persisted value of
``0.966667``. The check fails closed: any adjacent number that does not
match within tolerance is a block, and unmodeled unit/scale transforms
(for example ``96.6667%`` against ``0.966667``) are NOT accepted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ClaimResultMismatch:
    """A semantic mismatch between a claim and its cited RESULT marker."""

    section: str
    claim_text: str
    marker: str
    marker_role: str  # baseline | comparison | derived
    marker_metric: str
    claimed_subject: str  # model | baseline | method | unknown
    reason: str


# Patterns that indicate the claim is about the comparison model
_MODEL_SUBJECT_PATTERNS = [
    r'(?i)\b(?:our|the)\s+(?:model|method|approach|proposed)\b',
    r'(?i)\boutperformed?\b',
    r'(?i)\bdemonstrates?\s+(?:that\s+)?(?:our|the)\s+(?:model|method|approach)\b',
    r'(?i)\bwe\s+(?:show|demonstrate|find|observe|report)\b',
    r'(?i)\bachieved\b',
]

# Patterns that indicate the claim is about the baseline — checked FIRST
_BASELINE_SUBJECT_PATTERNS = [
    r'(?i)\bbaseline\b',
    r'(?i)\bmajority.class\b',
    r'(?i)\bmean\s+predictor\b',
    r'(?i)\bpredeclared\s+\w+\s+(?:baseline|predictor)\b',
]


def _infer_claim_subject(claim_text: str) -> str:
    """Infer whether a claim is about the model, baseline, or unknown.

    Baseline patterns are checked FIRST so that deterministic baseline
    sentences like "The predeclared baseline achieved..." are correctly
    classified as baseline claims, not model claims.
    """
    for pattern in _BASELINE_SUBJECT_PATTERNS:
        if re.search(pattern, claim_text):
            return "baseline"
    for pattern in _MODEL_SUBJECT_PATTERNS:
        if re.search(pattern, claim_text):
            return "model"
    return "unknown"


# ── Numeric value-fidelity gate (2026-08-10) ───────────────────────────
#
# Matches a decimal number that sits immediately beside a [RESULT-N]
# marker, tolerating markdown emphasis and whitespace. Examples caught:
#   0.966667 [RESULT-3]      (correct)
#   966667 [RESULT-3]        (dropped leading 0. — the revision-15 defect)
#   333333** [RESULT-1]      (bolded, no leading 0.)
#   [RESULT-3] of 0.966667   (number after the marker)
# A marker with no adjacent number is referential prose and is skipped.

# Number before the marker: digits with optional decimal point, optional
# trailing markdown emphasis (** or *), optional '%'.
_NUM_BEFORE_RE = re.compile(
    r'(?P<num>\d+\.?\d*)\s*%?\s*(?:\*\*|\*)?\s*\[RESULT-\d+\]'
)
# Number after the marker: [RESULT-N] then optional prose-joiner then number.
_NUM_AFTER_RE = re.compile(
    r'\[RESULT-\d+\]\s*(?:of|=|:)?\s*(?P<num>\d+\.?\d*)\s*%?'
)


def _extract_adjacent_numbers(paper_md: str, bracket_marker: str) -> list[float]:
    """Return every numeric value rendered immediately beside ``bracket_marker``.

    Scans a window around each occurrence of ``bracket_marker`` (for example
    ``[RESULT-3]``) and returns the numbers found directly before or after
    it. A referential citation (``see [RESULT-3]``) with no adjacent number
    contributes nothing, which is the intended behavior: the gate compares
    rendered numbers, not their absence.
    """
    numbers: list[float] = []
    marker_index = int(re.search(r'\d+', bracket_marker).group()) if bracket_marker else 0
    if marker_index == 0:
        return numbers

    # Numbers appearing immediately before any [RESULT-N] occurrence.
    for m in _NUM_BEFORE_RE.finditer(paper_md):
        if f"[RESULT-{marker_index}]" in m.group(0):
            try:
                numbers.append(float(m.group("num")))
            except ValueError:
                pass

    # Numbers appearing immediately after this specific marker.
    after_pattern = re.compile(
        r'\[RESULT-' + str(marker_index) + r'\]\s*(?:of|=|:)?\s*(?P<num>\d+\.?\d*)\s*%?'
    )
    for m in after_pattern.finditer(paper_md):
        try:
            numbers.append(float(m.group("num")))
        except ValueError:
            pass

    return numbers


def _values_agree(rendered: float, persisted: float,
                  tolerance: float = 1e-6) -> bool:
    """Return True iff ``rendered`` equals ``persisted`` within tolerance.

    The tolerance is tight on purpose. These values are the same decimal
    possibly with trailing-zero stripping (``0.966667`` vs ``0.9666670``),
    so a tight tolerance accepts that and nothing more. A unit/scale
    transform (``0.966667`` vs ``96.6667``) fails, which is the intended
    fail-closed behavior: the validator does not model transforms.
    """
    return abs(rendered - persisted) <= tolerance


def validate_claim_result_alignment(
    paper_md: str,
    result_markers: list,  # list of ResultMarker objects
) -> list[ClaimResultMismatch]:
    """Validate that every RESULT marker citation in the paper is semantically
    consistent with the claim it supports.

    Returns a list of mismatches (empty if all consistent).
    """
    # Build marker lookup
    marker_info: dict[str, dict] = {}
    for m in result_markers:
        bracket = f"[{m.marker}]"
        marker_info[bracket] = {
            "role": getattr(m, "role", ""),
            "metric": getattr(m, "metric_name", ""),
            "value": getattr(m, "observed_value", 0),
        }

    if not marker_info:
        return []

    # Split paper into sentences and check each RESULT citation
    # Focus on conclusion and abstract sections where claims are made
    import re as _re
    # Split on sentence boundaries AND newlines to avoid cross-section merging
    sentences = _re.split(r'(?<=[.!?])\s+|\n+', paper_md)

    mismatches: list[ClaimResultMismatch] = []

    for sentence in sentences:
        # Find RESULT markers in this sentence
        cited_markers = _re.findall(r'\[RESULT-\d+\]', sentence)
        if not cited_markers:
            continue

        # Infer what the sentence is about
        subject = _infer_claim_subject(sentence)

        for marker in cited_markers:
            info = marker_info.get(marker)
            if not info:
                continue  # unknown marker — handled by invariant checker

            # Check: if the claim is about the MODEL, the marker should NOT
            # be a baseline marker
            if subject == "model" and info["role"] == "baseline":
                mismatches.append(ClaimResultMismatch(
                    section="conclusion_or_abstract",
                    claim_text=sentence.strip()[:200],
                    marker=marker,
                    marker_role=info["role"],
                    marker_metric=info["metric"],
                    claimed_subject=subject,
                    reason=(
                        f"Claim credits {marker} (role=baseline, metric={info['metric']}) "
                        f"to the comparison model. A baseline marker should not be "
                        f"attributed to the model's performance."
                    ),
                ))

    # ── Numeric value-fidelity gate (2026-08-10) ───────────────────────
    # For each registered marker, find every number rendered immediately
    # beside it anywhere in the paper and compare against the persisted
    # observed_value. One corrupted attribution blocks. A marker used with
    # no adjacent number (referential prose) is skipped, not failed. The
    # comparison fails closed on unit/scale transforms (no guessing).
    for bracket, info in marker_info.items():
        persisted_value = info["value"]
        rendered_numbers = _extract_adjacent_numbers(paper_md, bracket)
        for rendered in rendered_numbers:
            if not _values_agree(rendered, persisted_value):
                mismatches.append(ClaimResultMismatch(
                    section="numeric_fidelity",
                    claim_text=f"rendered {rendered} beside {bracket}",
                    marker=bracket,
                    marker_role=info["role"],
                    marker_metric=info["metric"],
                    claimed_subject="numeric",
                    reason=(
                        f"Numeric value-fidelity mismatch: {bracket} is rendered "
                        f"as {rendered} but persisted observed_value is "
                        f"{persisted_value}. The number adjacent to a RESULT "
                        f"marker must equal its registered value."
                    ),
                ))

    return mismatches
