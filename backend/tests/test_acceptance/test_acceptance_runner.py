"""Tests for the acceptance runner preflight and evidence layer.

These test the hermetically-testable building blocks: code-origin capture,
preflight enforcement (clean tree, exact SHA, attempt-dir reuse), and
evidence-bundle writing with last-generated hashes.

The full execution path (orchestrator + verdict) is exercised by the
Phase A6 hermetic rehearsal.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.acceptance.live_paper_contract import LivePaperAcceptanceCase
from backend.acceptance.live_paper_verdict import (
    AcceptanceVerdict,
    VerdictReport,
    invalid_case,
)
from backend.acceptance.runner import (
    CodeOrigin,
    PreflightResult,
    capture_code_origin,
    resolve_repo_root,
    run_preflight,
    write_evidence,
)


def _case(expected_sha: str | None = None) -> LivePaperAcceptanceCase:
    return LivePaperAcceptanceCase.model_validate({
        "schema_version": "erlab.live-paper-acceptance.v1",
        "case_id": "rtest",
        "research_domain": "MT",
        "research_question": "How can transfer help low-resource MT?",
        "expected_code_sha": expected_sha or "abcdef1234567890abcdef1234567890abcdef12",
        "corpus_mode": "synthetic",
        "provider": "zai",
        "model": "glm-4.6",
        "embedding_provider": "lmstudio",
        "embedding_model": "text-embedding-qwen3-embedding-0.6b",
        "execution": {"network_policy": "hermetic"},
        "budget": {
            "maximum_cost_usd": 5.0, "maximum_provider_calls": 200,
            "maximum_input_tokens": 1000, "maximum_output_tokens": 500,
            "maximum_duration_seconds": 1800,
        },
    })


# ── Code-origin capture ──────────────────────────────────────────────


class TestCodeOrigin:
    def test_resolve_repo_root_finds_git_toplevel(self):
        root = resolve_repo_root()
        assert (root / ".git").exists() or root.parent.name != ""

    def test_capture_code_origin_returns_actual_sha(self, tmp_path):
        # Patch the git helper to avoid depending on the live tree state.
        repo_root = tmp_path
        (repo_root / "pyproject.toml").write_text("# test", encoding="utf-8")
        with patch("backend.acceptance.runner._git") as git_mock:
            git_mock.side_effect = lambda r, *a: {
                ("rev-parse", "--show-toplevel"): str(repo_root),
                ("rev-parse", "HEAD"): "abc1234567890" * 3,
                ("status", "--porcelain"): "",
            }.get(a, "")
            origin = capture_code_origin("abc1234567890", repo_root)
        assert origin.actual_sha.startswith("abc1234567890")
        assert origin.working_tree_clean is True

    def test_capture_rejects_sha_mismatch(self, tmp_path):
        with patch("backend.acceptance.runner._git") as git_mock:
            git_mock.side_effect = lambda r, *a: {
                ("rev-parse", "--show-toplevel"): str(tmp_path),
                ("rev-parse", "HEAD"): "ffffffffffffffffffffffffffffffffffffffff",
                ("status", "--porcelain"): "",
            }.get(a, "")
            with pytest.raises(RuntimeError, match="code_origin_mismatch"):
                capture_code_origin("abc1234567890" * 3, tmp_path, require_clean=False)

    def test_capture_rejects_dirty_tree(self, tmp_path):
        with patch("backend.acceptance.runner._git") as git_mock:
            git_mock.side_effect = lambda r, *a: {
                ("rev-parse", "--show-toplevel"): str(tmp_path),
                ("rev-parse", "HEAD"): "abc1234567890" * 3,
                ("status", "--porcelain"): " M some_file.py",
            }.get(a, "")
            with pytest.raises(RuntimeError, match="code_origin_dirty"):
                capture_code_origin("abc1234567890" * 3, tmp_path)


# ── Preflight enforcement ────────────────────────────────────────────


class TestPreflight:
    def test_preflight_passes_when_origin_ok(self, tmp_path):
        case = _case()
        with patch("backend.acceptance.runner.capture_code_origin") as cap, \
             patch("run_e2e_pipeline.derive_attempt_session_dir") as deriv:
            cap.return_value = CodeOrigin(
                expected_sha=case.expected_code_sha, actual_sha=case.expected_code_sha,
                working_tree_clean=True, runner_path="r", backend_package_path="b",
                python_version="3.12",
            )
            deriv.return_value = tmp_path / "attempt"
            preflight = run_preflight(case, repo_root=tmp_path, base_session_dir=str(tmp_path))
        assert preflight.ok is True
        assert preflight.code_origin is not None

    def test_preflight_rejects_attempt_dir_reuse(self, tmp_path):
        case = _case()
        attempt = tmp_path / "confirmatory" / case.case_id
        attempt.mkdir(parents=True)
        with patch("backend.acceptance.runner.capture_code_origin") as cap, \
             patch("run_e2e_pipeline.derive_attempt_session_dir") as deriv:
            cap.return_value = CodeOrigin(
                expected_sha=case.expected_code_sha, actual_sha=case.expected_code_sha,
                working_tree_clean=True, runner_path="r", backend_package_path="b",
                python_version="3.12",
            )
            deriv.return_value = attempt
            preflight = run_preflight(case, repo_root=tmp_path, base_session_dir=str(tmp_path))
        assert preflight.ok is False
        assert preflight.reason_code == "attempt_dir_reused"

    def test_preflight_rejects_origin_mismatch(self, tmp_path):
        case = _case()
        with patch("backend.acceptance.runner.capture_code_origin") as cap:
            cap.side_effect = RuntimeError("code_origin_mismatch: HEAD x != expected y")
            preflight = run_preflight(case, repo_root=tmp_path, base_session_dir=str(tmp_path))
        assert preflight.ok is False
        assert preflight.reason_code == "code_origin_mismatch"

    def test_invalid_preflight_converts_to_verdict(self, tmp_path):
        case = _case()
        preflight = PreflightResult(ok=False, reason_code="sha_mismatch", detail="x")
        report = preflight.to_invalid_case(case.case_id)
        assert report.verdict is AcceptanceVerdict.INVALID_CASE
        assert report.exit_code == 3


# ── Evidence bundle ──────────────────────────────────────────────────


class TestEvidenceBundle:
    def test_writes_required_files_and_hashes(self, tmp_path):
        case = _case()
        verdict = VerdictReport(
            verdict=AcceptanceVerdict.PASS, case_id=case.case_id,
            attempt_id="a1", exit_code=0,
        )
        origin = CodeOrigin("s", "s", True, "r", "b", "3.12", "dep")
        ev = write_evidence(tmp_path / "ev", case, verdict, origin)
        # Required files.
        for name in ("acceptance_case.json", "code_origin.json",
                     "acceptance_verdict.json", "acceptance_verdict.md",
                     "artifact_hashes.json"):
            assert (ev / name).exists(), f"missing {name}"
        # Hashes generated last exclude themselves.
        hashes = json.loads((ev / "artifact_hashes.json").read_text())
        assert "artifact_hashes.json" not in hashes
        assert "acceptance_verdict.json" in hashes

    def test_evidence_rejects_existing_directory(self, tmp_path):
        case = _case()
        verdict = VerdictReport(verdict=AcceptanceVerdict.FAIL, case_id=case.case_id, exit_code=1)
        existing = tmp_path / "ev"
        existing.mkdir()
        with pytest.raises(FileExistsError):
            write_evidence(existing, case, verdict, None)

    def test_verdict_markdown_marks_failure(self, tmp_path):
        case = _case()
        verdict = invalid_case(case.case_id, "sha_mismatch", "x")
        ev = write_evidence(tmp_path / "ev", case, verdict, None)
        md = (ev / "acceptance_verdict.md").read_text(encoding="utf-8")
        assert "INVALID_CASE" in md
        assert "sha_mismatch" in md
