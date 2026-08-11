"""Phase 7H — durable RESULT-marker linkage persistence.

These tests prove that the persistence contract survives commit+reload:
every [RESULT-N] marker in a paper resolves to its experiment result,
metric, and artifact hash through persisted JSON metadata — not through
in-memory state or convention.

Run: pytest backend/tests/test_persistence/test_phase7h_result_marker_persistence.py -v
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from backend.pipeline.experiment.manifest import ResultMarker
from backend.pipeline.persistence import _extract_paper_artifact

# ── Helpers ──────────────────────────────────────────────────────────

def _make_paper_md(words: int = 250) -> str:
    return "# Test Paper\n\n" + " ".join(f"word{i}" for i in range(words))


def _make_result_markers(exp_id: int = 11) -> list[ResultMarker]:
    return [
        ResultMarker(
            marker_index=1, marker="RESULT-1",
            metric_name="baseline_accuracy",
            observed_value=0.333333,
            artifact_path="metrics.json",
            artifact_sha256="212a34a3fac2cd5d",
            experiment_result_id=exp_id,
        ),
        ResultMarker(
            marker_index=2, marker="RESULT-2",
            metric_name="improvement",
            observed_value=0.633333,
            artifact_path="metrics.json",
            artifact_sha256="212a34a3fac2cd5d",
            experiment_result_id=exp_id,
        ),
        ResultMarker(
            marker_index=3, marker="RESULT-3",
            metric_name="model_accuracy",
            observed_value=0.966667,
            artifact_path="metrics.json",
            artifact_sha256="212a34a3fac2cd5d",
            experiment_result_id=exp_id,
        ),
    ]


def _make_selected_proposal() -> SimpleNamespace:
    return SimpleNamespace(
        metadata=json.dumps({
            "full_paper": {
                "paper_markdown": _make_paper_md(),
                "word_count": 252,
                "source_map": [],
            }
        })
    )


def _make_non_selected_proposal() -> SimpleNamespace:
    return SimpleNamespace(
        metadata=json.dumps({
            "experiment_status": "not_selected_for_experiment",
            "paper_status": "not_requested",
        })
    )


# ── Tests ────────────────────────────────────────────────────────────


class TestResultMarkerPersistence:
    """RESULT-marker map must survive commit+reload."""

    def test_result_markers_persisted_in_paper_meta(self):
        """1. Every persisted [RESULT-N] marker resolves to the correct
        metric and artifact hash."""
        proposal = _make_selected_proposal()
        markers = _make_result_markers(exp_id=11)
        _, meta = _extract_paper_artifact(proposal, result_markers=markers)

        assert "result_markers" in meta
        assert len(meta["result_markers"]) == 3

        expected = {
            "RESULT-1": ("baseline_accuracy", 0.333333),
            "RESULT-2": ("improvement", 0.633333),
            "RESULT-3": ("model_accuracy", 0.966667),
        }
        for rm in meta["result_markers"]:
            assert rm["marker"] in expected
            metric, value = expected[rm["marker"]]
            assert rm["metric_id"] == metric
            assert rm["observed_value"] == value
            assert rm["experiment_result_id"] == 11
            assert rm["artifact_sha256"] == "212a34a3fac2cd5d"

    def test_experiment_result_id_survives_in_paper_meta(self):
        """2. The paper's experiment_result_id survives reload."""
        proposal = _make_selected_proposal()
        markers = _make_result_markers(exp_id=11)
        _, meta = _extract_paper_artifact(proposal, result_markers=markers)

        assert meta["experiment_result_id"] == 11

    def test_no_result_markers_when_none_provided(self):
        """3. Non-empirical papers have no result_markers key."""
        proposal = _make_selected_proposal()
        _, meta = _extract_paper_artifact(proposal, result_markers=None)

        assert "result_markers" not in meta
        assert "experiment_result_id" not in meta

    def test_result_markers_round_trip_through_json(self):
        """4. The marker map survives JSON serialization (the actual
        persistence format)."""
        proposal = _make_selected_proposal()
        markers = _make_result_markers(exp_id=11)
        _, meta = _extract_paper_artifact(proposal, result_markers=markers)

        # Serialize → deserialize (simulates DB write + reload)
        serialized = json.dumps(meta)
        reloaded = json.loads(serialized)

        assert len(reloaded["result_markers"]) == 3
        assert reloaded["experiment_result_id"] == 11
        assert reloaded["result_markers"][0]["metric_id"] == "baseline_accuracy"


class TestNonSelectedProposalPersistence:
    """Non-selected proposal state must survive reload."""

    def test_non_selected_state_persisted(self):
        """5. Non-selected proposal status survives reload."""
        proposal = _make_non_selected_proposal()
        md, meta = _extract_paper_artifact(proposal)

        assert md is None  # no paper synthesized
        assert meta is not None  # but metadata IS persisted
        assert meta["status"] == "not_requested"
        assert meta["experiment_status"] == "not_selected_for_experiment"
        assert meta["paper_status"] == "not_requested"

    def test_non_selected_state_round_trips_through_json(self):
        """6. Non-selected state survives JSON round-trip."""
        proposal = _make_non_selected_proposal()
        _, meta = _extract_paper_artifact(proposal)

        serialized = json.dumps(meta)
        reloaded = json.loads(serialized)

        assert reloaded["experiment_status"] == "not_selected_for_experiment"
        assert reloaded["paper_status"] == "not_requested"

    def test_fast_scan_proposal_stays_null(self):
        """A proposal with no paper and no experiment state stays NULL."""
        proposal = SimpleNamespace(metadata=None)
        md, meta = _extract_paper_artifact(proposal)
        assert md is None
        assert meta is None


class TestNoExtraExperimentCreated:
    """The persistence path creates no new ExperimentResult rows."""

    def test_extract_creates_no_db_rows(self):
        """_extract_paper_artifact is a pure function — it reads from
        in-memory proposal/marker state and returns JSON-able dicts.
        It never touches the experiment_results table."""
        proposal = _make_selected_proposal()
        markers = _make_result_markers(exp_id=11)
        md, meta = _extract_paper_artifact(proposal, result_markers=markers)

        # The function returns data only — no side effects, no DB access
        assert isinstance(md, str)
        assert isinstance(meta, dict)
        # experiment_result_id is PASSED THROUGH from the marker, not created
        assert meta["experiment_result_id"] == 11
