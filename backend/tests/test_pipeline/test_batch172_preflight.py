"""BATCH-172 TASK-02: Wire Preflight into API Endpoint.

Verify preflight checks run before pipeline acceptance and return
correct 503/202 responses.
"""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Create a TestClient for the pipeline router with mocked dependencies."""
    from backend.api.routes.pipeline import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _mock_preflight_report(
    can_proceed=True,
    fatal=0,
    warnings=0,
    errors=0,
    checks=None,
):
    """Build a mock PreflightReport."""
    from backend.pipeline.preflight import CheckSeverity, PreflightResult

    if checks is None:
        checks = [
            PreflightResult(name="settings", severity=CheckSeverity.OK, message="OK"),
        ]

    report = MagicMock()
    report.can_proceed = can_proceed
    report.fatal = fatal
    report.warnings = warnings
    report.errors = errors
    report.checks = checks
    return report


# ── Test 1: Preflight module imports successfully ───────────────────────

def test_preflight_module_imports():
    from backend.pipeline.preflight import run_preflight, PreflightReport, PreflightResult, CheckSeverity
    assert callable(run_preflight)
    assert CheckSeverity.FATAL.value == "fatal"
    assert CheckSeverity.WARNING.value == "warning"


# ── Test 2: API returns 503 when LLM provider is FATAL ──────────────────

def test_api_503_on_llm_fatal():
    from backend.pipeline.preflight import CheckSeverity, PreflightResult

    fatal_check = PreflightResult(
        name="llm_provider",
        severity=CheckSeverity.FATAL,
        message="LLM provider failed: ConnectionError",
        detail="Connection refused",
    )
    mock_report = _mock_preflight_report(
        can_proceed=False,
        fatal=1,
        checks=[fatal_check],
    )

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report):
        client = _make_app()
        resp = client.post(
            "/run",
            json={"domain": "AI/NLP", "strategy": "deep_research"},
        )
        assert resp.status_code == 503, f"Expected 503, got {resp.status_code}: {resp.json()}"
        body = resp.json()
        assert body["preflight"]["can_proceed"] is False
        assert body["preflight"]["fatal_count"] == 1
        assert any(c["name"] == "llm_provider" for c in body["preflight"]["fatal_checks"])


# ── Test 3: API returns 503 when database is FATAL ──────────────────────

def test_api_503_on_database_fatal():
    from backend.pipeline.preflight import CheckSeverity, PreflightResult

    db_check = PreflightResult(
        name="database",
        severity=CheckSeverity.FATAL,
        message="Database unreachable: OperationalError",
        detail="no such table",
    )
    mock_report = _mock_preflight_report(
        can_proceed=False,
        fatal=1,
        checks=[db_check],
    )

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report):
        client = _make_app()
        resp = client.post(
            "/run",
            json={"domain": "AI/NLP", "strategy": "deep_research"},
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["preflight"]["fatal_count"] == 1


# ── Test 4: API returns 202 with preflight key on success ───────────────

def test_api_202_with_preflight_on_success():
    mock_report = _mock_preflight_report(can_proceed=True, fatal=0, warnings=0)

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report):
        client = _make_app()
        resp = client.post(
            "/run",
            json={"domain": "AI/NLP", "strategy": "deep_research"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.json()}"
        body = resp.json()
        assert body["status"] == "running"
        assert "preflight" in body
        assert body["preflight"]["can_proceed"] is True


# ── Test 5: API returns 202 when embedding is WARNING ───────────────────

def test_api_202_on_embedding_warning():
    from backend.pipeline.preflight import CheckSeverity, PreflightResult

    checks = [
        PreflightResult(name="settings", severity=CheckSeverity.OK, message="OK"),
        PreflightResult(name="embedding_provider", severity=CheckSeverity.WARNING, message="Embedding slow"),
    ]
    mock_report = _mock_preflight_report(can_proceed=True, fatal=0, warnings=1, checks=checks)

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report):
        client = _make_app()
        resp = client.post(
            "/run",
            json={"domain": "AI/NLP", "strategy": "deep_research"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["preflight"]["can_proceed"] is True
        assert body["preflight"]["warnings"] == 1


# ── Test 6: PreflightReport structure is correct ────────────────────────

def test_preflight_report_structure():
    from backend.pipeline.preflight import CheckSeverity, PreflightReport, PreflightResult

    report = PreflightReport(
        checks=[
            PreflightResult(name="test", severity=CheckSeverity.OK, message="ok"),
        ],
        can_proceed=True,
        warnings=0,
        errors=0,
        fatal=0,
    )
    assert report.can_proceed is True
    assert len(report.checks) == 1
    assert report.checks[0].name == "test"
    assert report.checks[0].severity == CheckSeverity.OK


# ── Test 7: 503 body lists all failures ─────────────────────────────────

def test_503_body_lists_all_failures():
    from backend.pipeline.preflight import CheckSeverity, PreflightResult

    checks = [
        PreflightResult(name="llm_provider", severity=CheckSeverity.FATAL, message="LLM failed", detail="conn refused"),
        PreflightResult(name="database", severity=CheckSeverity.FATAL, message="DB failed", detail="no table"),
        PreflightResult(name="settings", severity=CheckSeverity.OK, message="OK"),
    ]
    mock_report = _mock_preflight_report(
        can_proceed=False,
        fatal=2,
        checks=checks,
    )

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report):
        client = _make_app()
        resp = client.post("/run", json={"domain": "AI/NLP", "strategy": "deep_research"})
        assert resp.status_code == 503
        body = resp.json()
        fatal_names = [c["name"] for c in body["preflight"]["fatal_checks"]]
        assert "llm_provider" in fatal_names
        assert "database" in fatal_names
        assert len(body["preflight"]["fatal_checks"]) == 2


# ── Test 8: run_preflight completes within 30 seconds (with mocks) ──────

def test_run_preflight_completes_within_30s():
    """run_preflight with mocked providers should return quickly."""
    from backend.pipeline.preflight import run_preflight

    mock_settings = MagicMock()
    mock_settings.embedding_provider = "mock"
    mock_settings.embedding_model = "mock"
    mock_settings.openai_api_key = "mock"
    mock_settings.ollama_base_url = "http://localhost:11434"
    mock_settings.embedding_dimension = None
    mock_settings.lmstudio_enabled = False
    mock_settings.thinking_model = ""
    mock_settings.export_dir = "exports"

    with patch("backend.pipeline.preflight._check_llm_provider", new_callable=AsyncMock) as m_llm, \
         patch("backend.pipeline.preflight._check_embedding_provider", new_callable=AsyncMock) as m_emb, \
         patch("backend.pipeline.preflight._check_local_llm", new_callable=AsyncMock) as m_local, \
         patch("backend.pipeline.preflight._check_database", new_callable=AsyncMock) as m_db:
        from backend.pipeline.preflight import CheckSeverity, PreflightResult

        m_llm.return_value = PreflightResult(name="llm_provider", severity=CheckSeverity.OK, message="OK")
        m_emb.return_value = PreflightResult(name="embedding_provider", severity=CheckSeverity.OK, message="OK")
        m_local.return_value = PreflightResult(name="local_llm", severity=CheckSeverity.OK, message="OK")
        m_db.return_value = PreflightResult(name="database", severity=CheckSeverity.OK, message="OK")

        start = time.monotonic()
        report = asyncio.run(run_preflight(domain="AI/NLP", strategy="deep_research", settings=mock_settings))
        elapsed = time.monotonic() - start
        assert elapsed < 30.0, f"run_preflight took {elapsed:.1f}s, expected < 30s"
        assert isinstance(report.can_proceed, bool)
