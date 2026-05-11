"""BATCH-173 TASK-03: Verification and batch close tests."""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=120,
    )


# ── 1. All batch173 tests pass ───────────────────────────────────────────

def test_all_batch173_tests_pass():
    """All batch173 tests pass (16 tests)."""
    r = _run([sys.executable, "-m", "pytest",
              "backend/tests/test_pipeline/test_batch173_stage_report.py",
              "backend/tests/test_pipeline/test_batch173_api_expose.py",
              "-q", "-p", "no:asyncio"])
    assert r.returncode == 0, f"Batch173 tests failed:\n{r.stdout}\n{r.stderr}"
    # Count passed
    lines = r.stdout.strip().split("\n")
    summary = lines[-1] if lines else ""
    assert "passed" in summary, f"Unexpected output: {summary}"


# ── 2. All batch172 tests still pass (no regression) ─────────────────────

def test_batch172_no_regression():
    """All batch172 tests still pass."""
    r = _run([sys.executable, "-m", "pytest",
              "backend/tests/test_pipeline/test_batch172_wiring.py",
              "backend/tests/test_pipeline/test_batch172_preflight.py",
              "backend/tests/test_pipeline/test_batch172_strategies.py",
              "backend/tests/test_pipeline/test_batch172_verification.py",
              "-q", "-p", "no:asyncio"])
    assert r.returncode == 0, f"Batch172 regression:\n{r.stdout}\n{r.stderr}"


# ── 3. Existing pipeline tests pass (sample) ────────────────────────────

def test_sample_pipeline_tests_pass():
    """A sample of existing pipeline tests still pass."""
    r = _run([sys.executable, "-m", "pytest",
              "backend/tests/test_pipeline/test_batch57_task02.py",
              "backend/tests/test_pipeline/test_batch172_preflight.py",
              "-q", "-p", "no:asyncio"])
    assert r.returncode == 0, f"Sample pipeline tests failed:\n{r.stdout}\n{r.stderr}"


# ── 4. STATE.md has BATCH-173 ────────────────────────────────────────────

def test_state_md_has_batch173():
    """STATE.md references BATCH-173."""
    state = (ROOT / "docs" / "aiv" / "STATE.md").read_text(encoding="utf-8")
    assert "BATCH-173" in state, "STATE.md missing BATCH-173"


# ── 5. CHANGELOG has BATCH-173 ───────────────────────────────────────────

def test_changelog_has_batch173():
    """CHANGELOG.md references BATCH-173."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "BATCH-173" in changelog, "CHANGELOG.md missing BATCH-173"
