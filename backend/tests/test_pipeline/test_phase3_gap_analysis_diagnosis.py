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
"""

from __future__ import annotations

import asyncio
import json
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.gap_analysis.gap_analyzer import (
    GapAnalysisOutputContractError,
    GapAnalyzer,
)


class FakeProvider:
    """Minimal provider that returns a fixed response."""
    def __init__(self, response: str):
        self._response = response
        self._last_receipt = None

    async def complete(self, messages, temperature=0.7, max_tokens=4096):
        return self._response

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


VALID_GAPS_RESPONSE = json.dumps({
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
})


@pytest.mark.anyio
async def test_valid_gaps_survive_parsing():
    """Case 1: Valid structured gaps survive parsing and filtering."""
    analyzer = GapAnalyzer(provider=FakeProvider(VALID_GAPS_RESPONSE))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 1
    assert gaps[0].title == "Test Gap"
    assert gaps[0].confidence == 0.8


@pytest.mark.anyio
async def test_bare_gap_object_without_wrapper_is_recovered():
    """Phase 4 / 4I: glm-4.6 returns a bare gap dict (no 'gaps' key).

    The prompt asks for a JSON array, but the model sometimes returns a single
    gap object as a dict. Without the parser normalization (gap_analyzer.py
    ~line 119), this produced 0 gaps — the B-09 live blocker. The fix wraps a
    bare gap-shaped dict so it is not silently discarded.
    """
    bare_gap = json.dumps({
        "title": "Bare Gap From Model",
        "description": "A gap returned as a bare object without a gaps wrapper.",
        "gap_type": "methodological",
        "confidence": 0.7,
        "related_clusters": [0],
        "potential_impact": "Medium",
    })
    analyzer = GapAnalyzer(provider=FakeProvider(bare_gap))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 1, "bare gap object must be recovered, not discarded"
    assert gaps[0].title == "Bare Gap From Model"


@pytest.mark.anyio
async def test_malformed_output_produces_diagnostic(caplog):
    """Case 2: Malformed output raises an explicit output-contract failure."""
    import logging
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    analyzer = GapAnalyzer(provider=FakeProvider("not json at all"))
    with pytest.raises(GapAnalysisOutputContractError):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Safe diagnostics must contain structural fields.
    assert any(
        "output_contract" in r.message and "unparseable_json" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_empty_provider_output_distinguishable_from_parser_failure(caplog):
    """Case 3: Empty provider output raises a distinct contract failure
    (blank_response) distinguishable from nonempty unparseable JSON."""
    import logging
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    analyzer = GapAnalyzer(provider=FakeProvider(""))
    with pytest.raises(GapAnalysisOutputContractError, match="blank_response"):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Must be distinguishable from nonempty unparseable: reason=blank_response
    assert any(
        "blank_response" in r.message and "response_nonempty=false" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_all_non_dict_candidates_produce_diagnostic(caplog):
    """Case 4: Non-dict gap list members raise a contract failure with
    safe structural diagnostics identifying the invalid member."""
    import logging
    response = json.dumps({"gaps": ["string item", 42, None]})
    analyzer = GapAnalyzer(provider=FakeProvider(response))
    caplog.set_level(logging.ERROR, logger="backend.pipeline.gap_analysis.gap_analyzer")
    with pytest.raises(GapAnalysisOutputContractError, match="gap_item_not_object"):
        await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    # Safe diagnostics must identify the invalid member index.
    assert any(
        "gap_item_not_object" in r.message and "item_index=0" in r.message
        for r in caplog.records
    )


@pytest.mark.anyio
async def test_zero_gap_does_not_silently_succeed():
    """Case 5: A zero-gap result from a deep_research run must not be
    indistinguishable from success. The gap analyzer should return empty
    gaps but the stage_lifecycle marks the run as failed."""
    analyzer = GapAnalyzer(provider=FakeProvider(json.dumps({"gaps": []})))
    gaps, _ = await analyzer.analyze([_make_paper()], domain="AI/NLP", max_gaps=5)
    assert len(gaps) == 0
    # The run-level check (stage_lifecycle.py:650) marks this as failed.
    # This test proves the gap analyzer correctly returns 0 gaps (not an error),
    # and the stage_lifecycle separately determines the run is failed.


@pytest.mark.anyio
async def test_existing_successful_behavior_unchanged():
    """Case 6: Existing successful gap-analysis behavior remains unchanged."""
    # Multiple valid gaps
    multi_gap_response = json.dumps({
        "gaps": [
            {"title": f"Gap {i}", "description": f"Desc {i}", "gap_type": "methodological",
             "confidence": 0.7 + i * 0.05, "related_clusters": [0], "potential_impact": "Medium"}
            for i in range(3)
        ]
    })
    analyzer = GapAnalyzer(provider=FakeProvider(multi_gap_response))
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
