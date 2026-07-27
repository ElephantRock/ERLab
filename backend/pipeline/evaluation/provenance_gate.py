"""Phase 4 / WP-4D — provenance gate result type.

A paper's artifact-generation state (``paper.status``) and its research-quality
state (``paper_evaluation``) must remain separate. The provenance precondition
runs before the evaluator can report an unqualified positive state: a paper
that cites ``[SOURCE-N]`` markers but has no recoverable source identity fails
the precondition, and the evaluation is recorded as ``unavailable`` with a
concrete provenance reason — never ``ready``.

This module holds only the result dataclass; the gate logic lives on
``PaperSynthesisStage.provenance_precondition`` so it can reuse the synthesis
stage's marker scanner.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProvenanceGateResult:
    """Outcome of the provenance precondition check.

    Attributes:
        passed: True if the paper may receive an unqualified positive
            evaluation; False if missing/unmapped provenance blocks it.
        reason: Human-readable explanation for the UI / evaluation record.
        unmapped_count: Number of citation markers with no recoverable source.
    """

    passed: bool
    reason: str
    unmapped_count: int = 0
