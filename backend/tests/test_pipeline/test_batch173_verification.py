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
