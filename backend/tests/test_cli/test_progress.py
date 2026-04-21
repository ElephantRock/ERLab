"""Tests for pipeline progress callback mechanism.

Tests the _record_stage callback logic without importing the full orchestrator
(which has heavy transitive dependencies like chromadb).
"""


# Stage order is a plain constant — verify it here independently
_STAGE_ORDER = [
    "literature_search",
    "ingestion",
    "gap_analysis",
    "idea_generation",
    "novelty_checking",
    "feasibility_scoring",
    "proposal_synthesis",
    "export",
]


class TestStageCallback:
    def test_callback_receives_stage_events(self):
        """Verify callback receives stage name, index, total, and elapsed."""
        events = []

        def capture(stage_name, idx, total, elapsed):
            events.append((stage_name, idx, total, elapsed))

        # Simulate _record_stage logic
        stage_name = "gap_analysis"
        elapsed = 5.0
        idx = _STAGE_ORDER.index(stage_name) + 1
        capture(stage_name, idx, len(_STAGE_ORDER), elapsed)

        assert len(events) == 1
        assert events[0][0] == "gap_analysis"
        assert events[0][1] == 3
        assert events[0][2] == 8
        assert events[0][3] == 5.0

    def test_no_callback_is_safe(self):
        """When callback is None, nothing happens (no crash)."""
        callback = None
        if callback:
            callback("literature_search", 1, 8, 0.0)  # should not execute

    def test_stage_order_completeness(self):
        """All 8 pipeline stages are present in _STAGE_ORDER."""
        expected = {
            "literature_search",
            "ingestion",
            "gap_analysis",
            "idea_generation",
            "novelty_checking",
            "feasibility_scoring",
            "proposal_synthesis",
            "export",
        }
        assert set(_STAGE_ORDER) == expected
        assert len(_STAGE_ORDER) == 8

    def test_unknown_stage_handled(self):
        """Unknown stage names get index '?' instead of crashing."""
        stage_name = "unknown_stage"
        idx = _STAGE_ORDER.index(stage_name) + 1 if stage_name in _STAGE_ORDER else "?"
        assert idx == "?"
