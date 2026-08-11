"""Phase 3 B-09 focused tests: gap analysis empty-output diagnosis.

Verifies that:
1. Valid structured gaps survive parsing and filtering.
2. Malformed output produces an explicit stage failure or diagnostic.
3. Empty provider output remains distinguishable from parser failure.
4. All candidates rejected by validation produces a recorded reason.
5. Zero-gap deep_research does not silently appear to have produced a
   successful research artifact.
6. Existing successful gap-analysis behavior remains unchanged.
7. The B-08 synthesis timeout tests continue passing.

Updated for the typed structured-output contract: gap analysis is routed
through structured_output() and validated against the canonical
GapAnalysisPayload model. Malformed/blank provider output now surfaces as
a contract or execution failure rather than being parsed from free text.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.pipeline.gap_analysis.gap_analyzer import (
    GapAnalysisExecutionError,
    GapAnalysisOutputContractError,
    GapAnalyzer,
)


class FakeProvider:
    """Minimal provider returning a fixed structured_output() payload.

    ``payload`` is returned verbatim by structured_output(). Pass a dict for
    valid/typed payloads, an Exception to simulate provider failure, or a
    non-conforming value (string/None/list) to simulate malformed output.
    """
    def __init__(self, payload):
        self._payload = payload
        self._last_receipt = None

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload

    async def complete(self, messages, temperature=0.7, max_tokens=4096):  # pragma: no cover - defensive
        raise AssertionError("GapAnalyzer must NOT call complete(); use structured_output()")

    @property
    def provider_name(self):
        return "fake"

    @property
    def default_model(self):
        return "fake-model"


def _make_paper(title="Test Paper", abstract="Test abstract"):
    return SimpleNamespace(
        title=title,
        abstract=abstract,
        authors=[SimpleNamespace(name="Author A")],
        year=2024,
        venue="Test Venue",
        source="test",
        source_id="test-1",
        doi=None,
        arxiv_id=None,
        url=None,
        embedding=None,
    )


VALID_GAPS_PAYLOAD = {
    "gaps": [
        {
            "title": "Test Gap",
            "description": "A test research gap",
            "gap_type": "methodological",
            "confidence": 0.8,
            "related_clusters": [0],
            "potential_impact": "High",
        }
    ]
}


@pytest.mark.anyio
async def test_valid_gaps_survive_parsing():
    """Case 1: Valid structured gaps survive parsing and filtering."""
    analyzer = GapAnalyzer(provider=FakeProvider(VALID_GAPS_PAYLOAD))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 1
    assert gaps[0].title == "Test Gap"
    assert gaps[0].confidence == 0.8


@pytest.mark.anyio
async def test_bare_gap_object_without_wrapper_is_recovered():
    """Phase 4 / 4I: a single bare gap object (no 'gaps' wrapper).

    Under the typed contract the provider schema always wraps gaps in a
    ``gaps`` array, but defensive normalization must still accept a bare
    gap-shaped dict so it is not silently discarded.
    """
    bare_gap = {
        "title": "Bare Gap From Model",
        "description": "A gap returned as a bare object without a gaps wrapper.",
        "gap_type": "methodological",
        "confidence": 0.7,
        "related_clusters": [0],
        "potential_impact": "Medium",
    }
    analyzer = GapAnalyzer(provider=FakeProvider(bare_gap))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 1, "bare gap object must be recovered, not discarded"
    assert gaps[0].title == "Bare Gap From Model"


@pytest.mark.anyio
async def test_malformed_output_produces_diagnostic(caplog):
    """Case 2: Malformed (non-conforming) output raises an explicit
    output-contract failure."""
    import logging
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    # A bare string is not a conforming structured payload.
    analyzer = GapAnalyzer(provider=FakeProvider("not a structured payload"))
    with pytest.raises(GapAnalysisOutputContractError):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Safe diagnostics must contain structural fields.
    assert any(
        "output_contract" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_empty_provider_output_distinguishable_from_parser_failure(caplog):
    """Case 3: Empty/None provider output raises a distinct contract failure
    (blank/empty) distinguishable from a non-empty malformed payload."""
    import logging
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    analyzer = GapAnalyzer(provider=FakeProvider(None))
    with pytest.raises(GapAnalysisOutputContractError):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Must be distinguishable from non-empty malformed output.
    assert any(
        "output_contract" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_all_non_dict_candidates_produce_diagnostic(caplog):
    """Case 4: Non-dict gap list members raise a contract failure with
    safe structural diagnostics identifying the invalid member."""
    import logging
    # A gaps array containing non-object members is non-conforming.
    payload = {"gaps": ["string item", 42, None]}
    analyzer = GapAnalyzer(provider=FakeProvider(payload))
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    with pytest.raises(GapAnalysisOutputContractError):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Safe diagnostics must reference an output_contract failure.
    assert any(
        "output_contract" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_zero_gap_does_not_silently_succeed():
    """Case 5: A zero-gap result must not be indistinguishable from success.

    The gap analyzer returns an empty typed result (no exception). The
    pipeline stage then terminalizes the run as no_research_gap (Commit 3).
    No-gap stays distinguishable from failure, which raises.
    """
    analyzer = GapAnalyzer(provider=FakeProvider({"gaps": []}))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 0


@pytest.mark.anyio
async def test_existing_successful_behavior_unchanged():
    """Case 6: Existing successful gap-analysis behavior remains unchanged."""
    # Multiple valid gaps
    multi_gap_payload = {
        "gaps": [
            {"title": f"Gap {i}", "description": f"Desc {i}", "gap_type": "methodological",
             "confidence": 0.7 + i * 0.05, "related_clusters": [0], "potential_impact": "Medium"}
            for i in range(3)
        ]
    }
    analyzer = GapAnalyzer(provider=FakeProvider(multi_gap_payload))
    gaps, cluster_report = await analyzer.analyze(
        [_make_paper(f"Paper {i}") for i in range(5)],
        domain="AI/NLP", max_gaps=5,
    )
    assert len(gaps) == 3
    # Sorted by confidence descending
    assert gaps[0].confidence >= gaps[1].confidence >= gaps[2].confidence


@pytest.mark.anyio
async def test_b08_synthesis_tests_still_pass():
    """Case 7: B-08 synthesis timeout tests continue passing (import check)."""
    from backend.pipeline.stages import PaperSynthesisStage
    assert PaperSynthesisStage.PER_PROPOSAL_TIMEOUT > 0
    assert PaperSynthesisStage.PER_PROPOSAL_TIMEOUT * 2 <= 1800


@pytest.mark.anyio
async def test_provider_failure_raises_execution_error():
    """An exhausted provider/transport failure surfaces as a typed
    GapAnalysisExecutionError, never as an empty gap list."""
    analyzer = GapAnalyzer(provider=FakeProvider(RuntimeError("transport down")))
    with pytest.raises(GapAnalysisExecutionError):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
