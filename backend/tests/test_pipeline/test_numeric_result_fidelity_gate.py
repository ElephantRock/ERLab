"""Regression contract for the numeric result-fidelity gate.

Freezes the contract BEFORE implementation so the gate's behavior is
fixed by tests, not by the implementation. Every case below mirrors a
row in the acceptance directive (2026-08-10).

The defect this gate closes: revision 15 of the acceptance run rendered
``966667 [RESULT-3]`` next to a persisted ``observed_value`` of
``0.966667``, and the paper still became ``ready``. The persisted value
already reaches ``claim_result_validator.py`` at line 86, but the
validator never compared it to the number rendered beside the marker.

These tests pin the comparison's semantics:

1. ``0.966667 [RESULT-3]`` against ``0.966667``  -> PASS
2. ``966667 [RESULT-3]`` against ``0.966667``    -> BLOCK
3. ``0.333333 [RESULT-1]``                       -> PASS
4. ``333333 [RESULT-1]``                         -> BLOCK
5. one corrupted occurrence among several        -> BLOCK (every attribution must agree)
6. referential prose with no adjacent number     -> not a numeric failure
7. ``96.6667%`` against ``0.966667``             -> BLOCK (fail closed on unit/scale transform)

The existing role-attribution cases at the bottom must remain unchanged
and passing — the numeric gate is additive, not a replacement.
"""

from dataclasses import dataclass

from backend.pipeline.evaluation.claim_result_validator import (
    ClaimResultMismatch,
    validate_claim_result_alignment,
)


@dataclass
class MarkerStub:
    """Mirrors the subset of ResultMarker fields the validator reads."""

    marker: str
    metric_name: str
    observed_value: float
    role: str = "comparison"
    direction: str = "higher_is_better"


# ── Case 1: correctly rendered value passes ─────────────────────────────


def test_case1_correct_decimal_passes():
    markers = [MarkerStub(marker="RESULT-3", metric_name="model_accuracy",
                          observed_value=0.966667)]
    paper = "Our model achieved an accuracy of 0.966667 [RESULT-3] on the test set."

    mismatches = validate_claim_result_alignment(paper, markers)

    assert mismatches == []


# ── Case 2: corrupted value (dropped leading 0.) blocks ─────────────────
# This is the exact defect found in revision 15 of run_65bfb602f9fb.


def test_case2_dropped_leading_zero_blocks():
    markers = [MarkerStub(marker="RESULT-3", metric_name="model_accuracy",
                          observed_value=0.966667)]
    paper = "Our model achieved an accuracy of 966667 [RESULT-3] on the test set."

    mismatches = validate_claim_result_alignment(paper, markers)

    numeric = [m for m in mismatches if "numeric" in m.reason.lower()
               or "value" in m.reason.lower()]
    assert len(numeric) == 1, (
        f"Expected one numeric-fidelity mismatch for '966667' vs 0.966667, "
        f"got: {mismatches}"
    )
    assert numeric[0].marker == "[RESULT-3]"


# ── Case 3 + 4: RESULT-1 (baseline) correct vs corrupted ────────────────


def test_case3_correct_baseline_decimal_passes():
    markers = [MarkerStub(marker="RESULT-1", metric_name="baseline_accuracy",
                          observed_value=0.333333, role="baseline")]
    paper = "The majority-class baseline accuracy of 0.333333 [RESULT-1] was low."

    mismatches = validate_claim_result_alignment(paper, markers)

    assert mismatches == []


def test_case4_corrupted_baseline_decimal_blocks():
    markers = [MarkerStub(marker="RESULT-1", metric_name="baseline_accuracy",
                          observed_value=0.333333, role="baseline")]
    # Observed-Results style: "**333333** [RESULT-1]" — bolded, no leading 0.
    paper = "Baseline accuracy stood at 333333** [RESULT-1], consistent across folds."

    mismatches = validate_claim_result_alignment(paper, markers)

    numeric = [m for m in mismatches if "numeric" in m.reason.lower()
               or "value" in m.reason.lower()]
    assert len(numeric) == 1, (
        f"Expected one numeric-fidelity mismatch for '333333' vs 0.333333, "
        f"got: {mismatches}"
    )


# ── Case 5: one corrupted occurrence among several blocks ───────────────
# Every numeric attribution must agree. A single corrupted instance is a
# block, because the released bytes contain the corruption regardless of
# how many correct instances also appear. This mirrors revision 15, where
# RESULT-1 appeared correctly three times and corrupted once.


def test_case5_one_corruption_among_many_blocks():
    markers = [MarkerStub(marker="RESULT-1", metric_name="baseline_accuracy",
                          observed_value=0.333333, role="baseline")]
    paper = (
        "The baseline was 0.333333 [RESULT-1]. "
        "We note again 0.333333 [RESULT-1]. "
        "Frozen Iris split. 333333** [RESULT-1], consistent across folds. "
        "Restated: 0.333333 [RESULT-1]."
    )

    mismatches = validate_claim_result_alignment(paper, markers)

    numeric = [m for m in mismatches if "numeric" in m.reason.lower()
               or "value" in m.reason.lower()]
    assert len(numeric) >= 1, (
        "One corrupted attribution among several must still block. "
        f"Got: {mismatches}"
    )


# ── Case 6: referential prose with no adjacent number is not a failure ──
# A marker used purely as a reference ("see [RESULT-3]") with no number
# beside it must not trigger the numeric gate. The gate compares rendered
# numbers, not their absence.


def test_case6_referential_prose_without_number_passes():
    markers = [MarkerStub(marker="RESULT-3", metric_name="model_accuracy",
                          observed_value=0.966667)]
    paper = (
        "As shown by the registered experiment [RESULT-3], the approach "
        "generalizes. Detailed numbers appear in the metrics artifact."
    )

    mismatches = validate_claim_result_alignment(paper, markers)

    numeric = [m for m in mismatches if "numeric" in m.reason.lower()
               or "value" in m.reason.lower()]
    assert numeric == [], (
        "A marker with no adjacent number is referential prose and must not "
        f"trigger the numeric gate. Got: {mismatches}"
    )


# ── Case 7: unit/scale transforms fail closed ───────────────────────────
# 0.966667 == 96.6667% numerically, but the validator must not guess the
# transform. Fail closed rather than accept an unmodeled unit/scale change.


def test_case7_percent_form_fails_closed():
    markers = [MarkerStub(marker="RESULT-3", metric_name="model_accuracy",
                          observed_value=0.966667)]
    paper = "Our model achieved 96.6667% [RESULT-3] accuracy on the test set."

    mismatches = validate_claim_result_alignment(paper, markers)

    numeric = [m for m in mismatches if "numeric" in m.reason.lower()
               or "value" in m.reason.lower()]
    assert len(numeric) == 1, (
        "96.6667% against observed_value 0.966667 must fail closed: the "
        "validator does not model unit/scale transforms. "
        f"Got: {mismatches}"
    )


# ── Existing role-attribution cases must remain unchanged ───────────────
# These are the Phase-10 correction-B semantics. The numeric gate is
# additive: it must not weaken or remove the role check.


def test_existing_role_mismatch_still_detected():
    """A model-claim citing a baseline marker still blocks (role gate)."""
    markers = [
        MarkerStub(marker="RESULT-1", metric_name="baseline_accuracy",
                   observed_value=0.333333, role="baseline"),
    ]
    paper = "Our model achieved 0.333333 [RESULT-1], outperforming all baselines."

    mismatches = validate_claim_result_alignment(paper, markers)

    role_mismatch = [m for m in mismatches
                     if getattr(m, "marker_role", "") == "baseline"]
    assert len(role_mismatch) >= 1, (
        "Role-attribution must still flag a model-claim citing a baseline "
        f"marker. Got: {mismatches}"
    )


def test_clean_model_claim_with_correct_values_passes_both_gates():
    """A correct model-claim citing a comparison marker with the right
    number passes both the role gate and the numeric gate."""
    markers = [
        MarkerStub(marker="RESULT-3", metric_name="model_accuracy",
                   observed_value=0.966667, role="comparison"),
    ]
    paper = "Our model achieved 0.966667 [RESULT-3] accuracy on the held-out set."

    mismatches = validate_claim_result_alignment(paper, markers)

    assert mismatches == [], (
        f"A clean model claim with correct value should pass both gates. "
        f"Got: {mismatches}"
    )
