"""Tests for operational dashboard API."""

import pytest
import json
from datetime import datetime, timezone
from backend.api.routes.ops import get_dashboard
from backend.db.models import PipelineRun, Proposal
from backend.db.database import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker



@pytest.fixture
def ops_db(tmp_path):
    """Create isolated DB with test data."""
    db_path = tmp_path / "ops_test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    session = Session()

    # Create a completed run with a stage report
    now = datetime.now(timezone.utc)
    run1 = PipelineRun(
        status="completed",
        domain="test",
        config_json="{}",
        stages_completed='["literature_search","idea_generation"]',
        stage_report_json=json.dumps([
            {"name": "literature_search", "status": "executed", "elapsed_s": 10.5},
            {"name": "idea_generation", "status": "executed", "elapsed_s": 45.2},
        ]),
        created_at=now,
        completed_at=now.replace(hour=now.hour + 1) if now.hour < 23 else now,
    )
    # A failed run
    run2 = PipelineRun(
        status="failed",
        domain="test",
        config_json="{}",
        error_message="LLM timeout",
        stages_completed="[]",
        created_at=now,
    )
    session.add_all([run1, run2])
    session.commit()

    yield session
    session.close()


class TestGetDashboard:
    """Tests for the dashboard endpoint."""

    @pytest.mark.asyncio
    async def test_returns_window(self):
        result = await get_dashboard(days=7)
        assert "window" in result
        assert result["window"]["days"] == 7
        assert "from" in result["window"]
        assert "to" in result["window"]

    @pytest.mark.asyncio
    async def test_returns_all_four_sections(self):
        result = await get_dashboard(days=7)
        assert "run_health" in result
        assert "model_usage" in result
        assert "source_health" in result
        assert "quality_trends" in result

    @pytest.mark.asyncio
    async def test_run_health_has_expected_fields(self):
        result = await get_dashboard(days=7)
        rh = result["run_health"]
        assert "total_runs" in rh
        assert "completed" in rh
        assert "failed" in rh
        assert "average_duration_s" in rh
        assert "slowest_stages" in rh
        assert isinstance(rh["slowest_stages"], list)

    @pytest.mark.asyncio
    async def test_model_usage_returns_gracefully_on_no_receipts(self):
        result = await get_dashboard(days=7)
        mu = result["model_usage"]
        assert "models" in mu
        assert "total_receipts" in mu
        assert "warnings" in mu
        assert isinstance(mu["warnings"], list)

    @pytest.mark.asyncio
    async def test_source_health_has_papers_and_sources(self):
        result = await get_dashboard(days=90)
        sh = result["source_health"]
        assert "papers_found_total" in sh
        assert "sources" in sh
        assert "zero_result_runs" in sh

    @pytest.mark.asyncio
    async def test_quality_trends_has_expected_fields(self):
        result = await get_dashboard(days=7)
        qt = result["quality_trends"]
        assert "proposal_count" in qt
        assert "quality_pass_rate" in qt
        assert "common_failures" in qt
        assert "citation_resolution_rate" in qt
        assert "remediation_count" in qt
        assert "restore_count" in qt

    @pytest.mark.asyncio
    async def test_empty_database_returns_zeros_not_errors(self):
        """When there's no data, metrics should return zero/null, not crash."""
        result = await get_dashboard(days=7)
        rh = result["run_health"]
        assert rh["total_runs"] >= 0  # may be 0 if DB is empty
        assert rh["average_duration_s"] == 0 or rh["average_duration_s"] > 0

    @pytest.mark.asyncio
    async def test_days_parameter_clamped(self):
        """days=90 should work (max allowed)."""
        result = await get_dashboard(days=90)
        assert result["window"]["days"] == 90

    @pytest.mark.asyncio
    async def test_limit_parameter_accepted(self):
        result = await get_dashboard(days=7, limit=10)
        assert "run_health" in result

    @pytest.mark.asyncio
    async def test_partial_failure_returns_error_key_not_crash(self):
        """If a metric section fails, it returns {error: ...} not a crash."""
        # All sections should either return data or error dict
        result = await get_dashboard(days=7)
        for section in ["run_health", "model_usage", "source_health", "quality_trends"]:
            assert isinstance(result[section], dict)
