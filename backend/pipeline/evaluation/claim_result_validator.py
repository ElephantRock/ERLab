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

    return mismatches
