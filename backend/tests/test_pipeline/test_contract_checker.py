"""Tests for contract checker scalar vs collection handling.

Regression coverage for the bug where papers_found (an int) was treated
as a collection: len(int) fails, defaults to 0, triggering false positive
contract violations even when the stage found 80+ papers.
"""

from __future__ import annotations

import pytest

from backend.pipeline.monitoring.contracts import (
    ContractViolation,
    StageContract,
    verify_contract,
)


class FakeResult:
    """Minimal result object matching PipelineResult's interface."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestScalarOutputContracts:
    """Tests for scalar (int/float) output fields in contract checks."""

    def test_papers_found_positive_int_passes(self):
        """papers_found > 0 should NOT trigger min_output_size violation."""
        contract = StageContract(
            stage_name="literature_search",
            required_outputs=["papers_found"],
            min_output_size={"papers_found": 1},
        )
        result = FakeResult(papers_found=81)

        violation = verify_contract("literature_search", result, contract)
        assert violation is None  # No violation — 81 >= 1

    def test_papers_found_zero_passes_required_but_fails_min(self):
        """papers_found=0 passes required_outputs (int, not None) but fails min_output_size."""
        contract = StageContract(
            stage_name="literature_search",
            required_outputs=["papers_found"],
            min_output_size={"papers_found": 1},
        )
        result = FakeResult(papers_found=0)

        violation = verify_contract("literature_search", result, contract)
        assert violation is not None
        assert any("0 items" in v for v in violation.violations)

    def test_gaps_list_min_size(self):
        """List outputs still use len() correctly."""
        contract = StageContract(
            stage_name="gap_analysis",
            required_outputs=["gaps"],
            min_output_size={"gaps": 1},
        )
        # Use mock gaps with confidence to pass quality checks
        class MockGap:
            def __init__(self):
                self.confidence = 0.8
        result = FakeResult(gaps=[MockGap(), MockGap(), MockGap()])

        violation = verify_contract("gap_analysis", result, contract)
        assert violation is None  # 3 >= 1

    def test_empty_gaps_list_fails(self):
        """Empty list correctly triggers violation."""
        contract = StageContract(
            stage_name="gap_analysis",
            required_outputs=["gaps"],
            min_output_size={"gaps": 1},
        )
        result = FakeResult(gaps=[])

        violation = verify_contract("gap_analysis", result, contract)
        assert violation is not None

    def test_float_output_works(self):
        """Float values treated as scalars, not collections."""
        contract = StageContract(
            stage_name="custom_stage",
            required_outputs=[],
            min_output_size={"score": 5},
        )
        result = FakeResult(score=7.5)

        violation = verify_contract("custom_stage", result, contract)
        assert violation is None  # 7.5 >= 5

    def test_none_output_missing(self):
        """None value triggers 'Missing output' for required_outputs."""
        contract = StageContract(
            stage_name="test",
            required_outputs=["ideas"],
            min_output_size={},
        )
        result = FakeResult()  # no 'ideas' attribute

        violation = verify_contract("test", result, contract)
        assert violation is not None
        assert any("Missing output" in v for v in violation.violations)
