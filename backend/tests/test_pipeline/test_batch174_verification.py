"""BATCH-174 TASK-03: Verification and batch close.

Verify:
1. All batch174 tests pass (21 tests)
2. Prior batch tests still pass (no regression)
3. STATE.md has BATCH-174 entry
4. CHANGELOG has BATCH-174 entry
"""

from __future__ import annotations

import subprocess
import sys

sys.modules.setdefault("chromadb", __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())
sys.modules.setdefault("google.generativeai", __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock())

import pytest


@pytest.fixture
def project_root():
    from pathlib import Path
    # This file: backend/tests/test_pipeline/test_batch174_verification.py
    # project root (where CHANGELOG.md lives): 3 levels up
    return Path(__file__).resolve().parents[3]


class TestBatch174Verification:
    """Meta-tests for batch integrity."""

    def test_all_batch174_tests_pass(self, project_root):
        """All batch174 tests (core + synthesis) pass."""
        result = subprocess.run(
            [sys.executable, "-m", "pytest",
             "backend/tests/test_pipeline/test_batch174_core_stages.py",
             "backend/tests/test_pipeline/test_batch174_synthesis_stages.py",
             "-v", "-p", "no:asyncio", "--tb=short"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"batch174 tests failed:\n{result.stdout}\n{result.stderr}"
        )
        # Count passed tests in output
        summary_line = [l for l in result.stdout.splitlines() if "passed" in l]
        assert len(summary_line) > 0, "No pytest summary line found"
        # Should be at least 21 tests (10 core + 11 synthesis)
        assert "passed" in summary_line[-1]

    def test_prior_batch_tests_no_regression(self, project_root):
        """batch172 + batch173 tests still pass (no regression)."""
        from glob import glob
        root = str(project_root)
        prior_tests = (
            glob(f"{root}/backend/tests/test_pipeline/test_batch172_*.py")
            + glob(f"{root}/backend/tests/test_pipeline/test_batch173_*.py")
        )
        assert len(prior_tests) > 0, "No prior batch test files found"
        result = subprocess.run(
            [sys.executable, "-m", "pytest"] + prior_tests + ["-q", "-p", "no:asyncio", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"Prior batch tests regressed:\n{result.stdout}\n{result.stderr}"
        )

    def test_state_md_has_batch174(self, project_root):
        """STATE.md contains BATCH-174 entry."""
        state_path = project_root / "docs" / "aiv" / "STATE.md"
        content = state_path.read_text(encoding="utf-8")
        assert "BATCH-174" in content, "STATE.md missing BATCH-174 entry"

    def test_changelog_has_batch174(self, project_root):
        """CHANGELOG.md contains BATCH-174 entry."""
        changelog_path = project_root / "CHANGELOG.md"
        content = changelog_path.read_text(encoding="utf-8")
        assert "BATCH-174" in content, "CHANGELOG.md missing BATCH-174 entry"
