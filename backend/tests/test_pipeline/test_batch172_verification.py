"""BATCH-172 TASK-04: Verification.

Verify integration consistency: stage order, preflight + trigger,
and documentation updates.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


ROOT = Path(__file__).resolve().parents[3]  # elephant-rock-platform
STATE_MD = ROOT / "docs" / "aiv" / "STATE.md"
CHANGELOG = ROOT / "CHANGELOG.md"


# ── Test 1: Full suite passes (check batch172 files only for speed) ────

def test_batch172_tests_all_pass():
    """Run the 3 batch172 test files and verify they all pass."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "backend/tests/test_pipeline/test_batch172_wiring.py",
         "backend/tests/test_pipeline/test_batch172_preflight.py",
         "backend/tests/test_pipeline/test_batch172_strategies.py",
         "-q", "--tb=no", "-p", "no:asyncio"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )
    assert result.returncode == 0, f"Tests failed:\n{result.stdout}\n{result.stderr}"
    # Should have 21 tests (7 + 8 + 6)
    assert "21 passed" in result.stdout, f"Expected 21 passed, got: {result.stdout}"


# ── Test 2: _STAGE_ORDER matches _build_stages ─────────────────────────

def test_stage_order_matches_build_stages():
    from backend.pipeline.orchestrator import PipelineOrchestrator
    from backend.tests.test_pipeline.test_batch172_wiring import _make_orchestrator

    orch = _make_orchestrator()
    stages = orch._build_stages()
    names = [s.name for s in stages]
    assert names == list(PipelineOrchestrator._STAGE_ORDER)


# ── Test 3: Preflight + trigger integration (503/200) ──────────────────

def test_preflight_trigger_integration():
    """Test both 503 (fatal) and 200 (success) paths through the API."""
    from backend.pipeline.preflight import CheckSeverity, PreflightResult
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.api.routes.pipeline import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 503 path
    fatal_check = PreflightResult(
        name="llm_provider", severity=CheckSeverity.FATAL,
        message="Failed", detail="conn refused",
    )
    mock_report_503 = MagicMock()
    mock_report_503.can_proceed = False
    mock_report_503.fatal = 1
    mock_report_503.warnings = 0
    mock_report_503.checks = [fatal_check]

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report_503):
        resp = client.post("/run", json={"domain": "AI/NLP", "strategy": "deep_research"})
        assert resp.status_code == 503

    # 200 path
    mock_report_ok = MagicMock()
    mock_report_ok.can_proceed = True
    mock_report_ok.fatal = 0
    mock_report_ok.warnings = 0
    mock_report_ok.checks = []

    with patch("backend.pipeline.preflight.run_preflight", new_callable=AsyncMock, return_value=mock_report_ok):
        resp = client.post("/run", json={"domain": "AI/NLP", "strategy": "deep_research"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["preflight"]["can_proceed"] is True


# ── Test 4: STATE.md has BATCH-172 ─────────────────────────────────────

def test_state_md_has_batch172():
    assert STATE_MD.exists(), f"STATE.md not found at {STATE_MD}"
    content = STATE_MD.read_text(encoding="utf-8")
    assert "BATCH-172" in content, "STATE.md does not mention BATCH-172"


# ── Test 5: CHANGELOG has BATCH-172 ────────────────────────────────────

def test_changelog_has_batch172():
    assert CHANGELOG.exists(), f"CHANGELOG.md not found at {CHANGELOG}"
    content = CHANGELOG.read_text(encoding="utf-8")
    assert "BATCH-172" in content, "CHANGELOG.md does not mention BATCH-172"
