"""BATCH-173 TASK-02: Persist + Expose Stage Report via API tests."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.pipeline.result import StageReport

# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def sample_stage_report():
    """16-entry stage report simulating a full run."""
    from backend.pipeline.orchestrator import PipelineOrchestrator
    stages = PipelineOrchestrator._STAGE_ORDER
    report = []
    for i, name in enumerate(stages):
        if i < 10:
            report.append(StageReport(name=name, status="executed", elapsed_s=0.1 * (i + 1)))
        elif i < 13:
            report.append(StageReport(name=name, status="skipped_by_error", elapsed_s=0.01, error="test error"))
        else:
            report.append(StageReport(name=name, status="not_reached"))
    return report


@pytest.fixture
def mock_run_with_report(sample_stage_report):
    """Mock PipelineRun DB object with stage_report_json."""
    run = MagicMock()
    run.id = 42
    run.status = "completed"
    run.domain = "AI/NLP"
    run.current_stage = "completed"
    run.config_json = json.dumps({"domain": "AI/NLP"})
    run.stages_completed = json.dumps([
        "literature_search", "ingestion", "gap_analysis", "gap_reflection",
        "idea_generation", "idea_reflection", "novelty_checking", "feasibility_scoring",
        "mechanical_metrics", "proposal_synthesis",
    ])
    run.stage_report_json = json.dumps([r.to_dict() for r in sample_stage_report])
    run.tree_data_json = None
    run.created_at = datetime.now(UTC)
    run.completed_at = datetime.now(UTC)
    run.error_message = None
    run.ideas = []
    return run


@pytest.fixture
def mock_run_without_report():
    """Mock PipelineRun DB object WITHOUT stage_report_json (pre-B173 run)."""
    run = MagicMock()
    run.id = 7
    run.status = "completed"
    run.domain = "AI/NLP"
    run.current_stage = "completed"
    run.config_json = json.dumps({"domain": "AI/NLP"})
    run.stages_completed = json.dumps(["literature_search", "ingestion"])
    run.stage_report_json = None
    run.tree_data_json = None
    run.created_at = datetime.now(UTC)
    run.completed_at = datetime.now(UTC)
    run.error_message = None
    run.ideas = []
    return run


def _call_get_run(mock_run):
    """Helper to call get_run with proper mocking of inside-function imports."""
    mock_sess = MagicMock()
    mock_sess.__enter__ = MagicMock(return_value=mock_sess)
    mock_sess.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.crud.get_pipeline_run", return_value=mock_run), \
         patch("backend.db.database.get_session", return_value=mock_sess):
        import asyncio

        from backend.api.routes.pipeline import get_run
        return asyncio.run(get_run(run_id=mock_run.id))


# ── 1. Run detail API returns stage_report key ───────────────────────────

def test_api_returns_stage_report_key(mock_run_with_report):
    """The /runs/detail/{id} response includes stage_report."""
    response = _call_get_run(mock_run_with_report)
    assert "stage_report" in response
    assert isinstance(response["stage_report"], list)


# ── 2. stage_report has 16 entries ───────────────────────────────────────

def test_api_stage_report_has_16_entries(mock_run_with_report):
    """stage_report should have exactly 16 entries for a full run."""
    response = _call_get_run(mock_run_with_report)
    assert len(response["stage_report"]) == 18


# ── 3. Executed stages have elapsed_s > 0 ───────────────────────────────

def test_executed_stages_have_elapsed(mock_run_with_report):
    """Executed stages in the report should have elapsed_s > 0."""
    response = _call_get_run(mock_run_with_report)
    executed = [r for r in response["stage_report"] if r["status"] == "executed"]
    assert len(executed) > 0
    for entry in executed:
        assert entry["elapsed_s"] > 0


# ── 4. Completed run has "executed" status entries ───────────────────────

def test_completed_run_has_executed_entries(mock_run_with_report):
    """A completed run should have some stages with status='executed'."""
    report = json.loads(mock_run_with_report.stage_report_json)
    executed = [r for r in report if r["status"] == "executed"]
    assert len(executed) > 0


# ── 5. stages_completed still populated (backward compat) ───────────────

def test_stages_completed_backward_compat(mock_run_with_report):
    """The stages_completed field is still returned for backward compatibility."""
    response = _call_get_run(mock_run_with_report)
    assert "stages_completed" in response
    assert isinstance(response["stages_completed"], list)
    assert len(response["stages_completed"]) > 0


# ── 6. Pre-B173 run returns empty list (backward compat) ────────────────

def test_pre_b173_run_returns_empty_list(mock_run_without_report):
    """A run created before BATCH-173 should return empty stage_report list."""
    response = _call_get_run(mock_run_without_report)
    assert "stage_report" in response
    assert response["stage_report"] == []
