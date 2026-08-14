"""Regression (run 2713, second repair attempt): the revision directive
never stated the marker-placement contract that the numeric fidelity
gate enforces — each [RESULT-N] marker is checked against the number
immediately adjacent to it. The model produced grouped citations
("from 0.005185 to 0.009787 [RESULT-2], [RESULT-20]") where every marker
after the first is read against the wrong value, and the gate failed on
a revision whose values were all individually correct.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.evaluation.revision_directive import (
    EvidenceInvariant,
    RevisionDirective,
    verify_revised_paper_invariants,
)


def _directive() -> RevisionDirective:
    return RevisionDirective(
        blocking_findings=("numeric_fidelity: test",),
        research_question="q",
        task_type="classification",
        target_name="species",
        executed_method="isotonic calibration",
        baseline_method="uncalibrated",
        comparison_method="sigmoid calibration",
        primary_metric="aurc",
        metric_direction="lower_is_better",
        dataset_name="iris",
        split_method="stratified",
        random_seed=42,
        evidence=EvidenceInvariant(
            result_map=(("RESULT-2", 0.005185), ("RESULT-20", 0.009787)),
            source_map=("[SOURCE-1]",),
            experiment_manifest_hash="h",
            dataset_hash="d",
            analysis_code_hash="c",
        ),
        unexecuted_methods_detected=(),
    )


class TestDirectiveStatesAdjacencyContract:
    def test_prompt_contains_placement_rule(self):
        prompt = _directive().build_revision_prompt()
        assert "IMMEDIATELY AFTER" in prompt
        assert "NEVER group several markers" in prompt
        assert "0.005185 [RESULT-2]" in prompt

    def test_prompt_lists_frozen_values(self):
        prompt = _directive().build_revision_prompt()
        assert "RESULT-2 = 0.005185" in prompt
        assert "RESULT-20 = 0.009787" in prompt


class TestGroupedCitationStillViolatesInvariants:
    """The invariant layer must not be relaxed to accept grouped
    citations — the fix is on the prompt side only."""

    def test_grouped_markers_pass_identity_but_values_unchecked(self):
        grouped = "isotonic AURC rises from 0.005185 to 0.009787 [RESULT-2], [RESULT-20]"
        ok, violations = verify_revised_paper_invariants(
            grouped, _directive().evidence,
        )
        # Marker identities are valid, so identity invariants pass...
        assert ok is True
        assert violations == []
        # ...but the numeric gate (claim_result_alignment) rejects the
        # grouped form at evaluation time: adjacent value for RESULT-2
        # is 0.009787, not its frozen 0.005185.
        from backend.pipeline.evaluation.claim_result_validator import (
            _extract_adjacent_numbers as extract_adjacent_numbers,
        )
        adjacent_2 = extract_adjacent_numbers(grouped, "[RESULT-2]")
        assert adjacent_2 and abs(adjacent_2[0] - 0.009787) < 1e-9
        assert abs(adjacent_2[0] - 0.005185) > 1e-9

    def test_per_marker_adjacency_reads_correct_value(self):
        separated = (
            "AURC under severity 0.0 is 0.005185 [RESULT-2]; "
            "under severity 0.5 it is 0.009787 [RESULT-20]."
        )
        from backend.pipeline.evaluation.claim_result_validator import (
            _extract_adjacent_numbers as extract_adjacent_numbers,
        )
        adjacent_2 = extract_adjacent_numbers(separated, "[RESULT-2]")
        adjacent_20 = extract_adjacent_numbers(separated, "[RESULT-20]")
        assert adjacent_2 and abs(adjacent_2[0] - 0.005185) < 1e-9
        assert adjacent_20 and abs(adjacent_20[0] - 0.009787) < 1e-9
