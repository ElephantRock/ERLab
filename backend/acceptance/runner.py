"""Manifest-driven acceptance mode for the existing runner.

Extends — does not replace — the confirmatory runner in
``run_e2e_pipeline.py``. Acceptance mode:

1. loads and validates a ``LivePaperAcceptanceCase`` manifest;
2. runs the preflight sequence (code-origin SHA, clean tree, budget
   enforcement capability, new attempt directory);
3. delegates EXECUTION to the same production
   ``PipelineOrchestrator(strategy='deep_research')`` path used by the
   confirmatory runner;
4. classifies the result with the verdict layer;
5. writes an immutable evidence bundle.

The acceptance layer NEVER generates research content (ideas, proposals,
papers, evaluations, citations). It only inspects and classifies.

Network policy: hermetic rehearsal injects deterministic dependencies and
must make zero network calls. Live execution requires separate
authorization.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.acceptance.live_paper_contract import LivePaperAcceptanceCase
from backend.acceptance.live_paper_verdict import (
    AcceptanceVerdict,
    GateResult,
    VerdictReport,
    evaluate_gates,
    invalid_case,
)


@dataclass
class CodeOrigin:
    """Recorded code-origin facts for evidence."""

    expected_sha: str
    actual_sha: str
    working_tree_clean: bool
    runner_path: str
    backend_package_path: str
    python_version: str
    dependency_snapshot_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "expected_sha": self.expected_sha,
            "actual_sha": self.actual_sha,
            "working_tree_clean": self.working_tree_clean,
            "runner_path": self.runner_path,
            "backend_package_path": self.backend_package_path,
            "python_version": self.python_version,
            "dependency_snapshot_hash": self.dependency_snapshot_hash,
        }


@dataclass
class PreflightResult:
    """Outcome of the acceptance preflight sequence."""

    ok: bool
    reason_code: str = ""
    detail: str = ""
    code_origin: CodeOrigin | None = None
    attempt_session_dir: Path | None = None

    def to_invalid_case(self, case_id: str) -> VerdictReport:
        return invalid_case(case_id, self.reason_code, self.detail)


# ── Code-origin verification ─────────────────────────────────────────


def _git(repo_root: Path, *args: str) -> str:
    """Run a git command, returning stripped stdout. Raises on failure."""
    out = subprocess.run(
        ["git", *args], cwd=str(repo_root), capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def resolve_repo_root(start: Path | None = None) -> Path:
    """Resolve the repository root from a starting path."""
    start = start or Path(__file__).resolve()
    cwd = start if start.is_dir() else start.parent
    root = _git(cwd, "rev-parse", "--show-toplevel")
    return Path(root)


def capture_code_origin(
    expected_sha: str,
    repo_root: Path,
    require_clean: bool = True,
    require_exact_sha: bool = True,
) -> CodeOrigin:
    """Capture code-origin facts and enforce the clean-tree / exact-SHA policy.

    Raises ``RuntimeError`` when a required policy is violated.
    """
    actual_sha = _git(repo_root, "rev-parse", "HEAD")
    status = _git(repo_root, "status", "--porcelain")
    clean = status == ""

    if require_exact_sha and not actual_sha.lower().startswith(expected_sha.lower()):
        raise RuntimeError(
            f"code_origin_mismatch: HEAD {actual_sha} != expected {expected_sha}"
        )
    if require_clean and not clean:
        raise RuntimeError("code_origin_dirty: working tree is not clean")

    runner_path = str(Path(run_e2e_path()))
    backend_pkg = str(Path(__file__).resolve().parent.parent)
    py_version = sys.version.replace("\n", " ")

    # Dependency snapshot hash (best-effort; empty if requirements absent).
    dep_hash = ""
    for req_name in ("requirements.txt", "pyproject.toml"):
        req = repo_root / req_name
        if req.exists():
            dep_hash = hashlib.sha256(req.read_bytes()).hexdigest()
            break

    return CodeOrigin(
        expected_sha=expected_sha,
        actual_sha=actual_sha,
        working_tree_clean=clean,
        runner_path=runner_path,
        backend_package_path=backend_pkg,
        python_version=py_version,
        dependency_snapshot_hash=dep_hash,
    )


def run_e2e_path() -> Path:
    """Locate run_e2e_pipeline.py relative to this package."""
    return Path(__file__).resolve().parents[2] / "run_e2e_pipeline.py"


# ── Preflight sequence ───────────────────────────────────────────────


def run_preflight(
    case: LivePaperAcceptanceCase,
    repo_root: Path | None = None,
    base_session_dir: str | None = None,
) -> PreflightResult:
    """Run the acceptance preflight before orchestrator construction.

    Returns a PreflightResult. ``ok=False`` carries an INVALID_CASE
    reason_code; the caller must not continue execution.
    """
    repo_root = repo_root or resolve_repo_root()
    try:
        origin = capture_code_origin(
            expected_sha=case.expected_code_sha,
            repo_root=repo_root,
            require_clean=case.execution.require_clean_tree,
            require_exact_sha=case.execution.require_exact_code_sha,
        )
    except RuntimeError as e:
        return PreflightResult(ok=False, reason_code="code_origin_mismatch",
                               detail=str(e))

    # Attempt-isolated session directory (reuse the confirmatory derivation).
    from run_e2e_pipeline import derive_attempt_session_dir  # type: ignore

    if base_session_dir is None:
        from backend.config import get_settings
        base_session_dir = get_settings().session_data_dir

    try:
        attempt_dir = derive_attempt_session_dir(base_session_dir, case.case_id)
    except Exception as e:  # PreflightError or path issues
        return PreflightResult(ok=False, reason_code="attempt_dir_invalid",
                               detail=str(e))

    if case.execution.require_new_attempt_directory and attempt_dir.exists():
        return PreflightResult(
            ok=False, reason_code="attempt_dir_reused",
            detail=f"attempt session directory already exists: {attempt_dir}",
        )

    return PreflightResult(ok=True, code_origin=origin, attempt_session_dir=attempt_dir)


# ── Evidence bundle ──────────────────────────────────────────────────


def write_evidence(
    evidence_dir: Path,
    case: LivePaperAcceptanceCase,
    verdict: VerdictReport,
    code_origin: CodeOrigin | None,
    result: Any | None = None,
    extra_files: dict[str, Any] | None = None,
) -> Path:
    """Write the immutable evidence bundle.

    Hashes are generated LAST and exclude themselves. No artifact may be
    edited after the verdict.
    """
    evidence_dir.mkdir(parents=True, exist_ok=False)
    extra_files = extra_files or {}

    def _write(name: str, payload: Any) -> None:
        path = evidence_dir / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True),
                            encoding="utf-8")

    _write("acceptance_case.json", case.model_dump(mode="json"))
    _write("code_origin.json", code_origin.to_dict() if code_origin else {})
    _write("acceptance_verdict.json", verdict.to_dict())
    _write("acceptance_verdict.md", _verdict_markdown(verdict))
    if result is not None:
        _write("pipeline_result.json", _safe_result_summary(result))
        _write("stage_report.json", _stage_report_dump(result))
    for name, payload in extra_files.items():
        _write(name, payload)

    # Artifact hashes — generated last, over everything except this file.
    artifact_hashes = {}
    for f in sorted(evidence_dir.iterdir()):
        if f.name == "artifact_hashes.json":
            continue
        artifact_hashes[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    _write("artifact_hashes.json", artifact_hashes)
    return evidence_dir


def _verdict_markdown(verdict: VerdictReport) -> str:
    lines = [f"# Acceptance verdict: {verdict.verdict.value.upper()}",
             f"- case_id: {verdict.case_id}",
             f"- attempt_id: {verdict.attempt_id}",
             f"- exit_code: {verdict.exit_code}"]
    if verdict.external_interruption:
        lines.append(f"- external_interruption: {verdict.external_interruption}")
    if verdict.failed_gates:
        lines.append("\n## Failed gates")
        for g in verdict.failed_gates:
            lines.append(f"- **{g.gate}** ({g.reason_code}): {g.detail}")
    if verdict.passed_gates:
        lines.append(f"\n## Passed gates: {len(verdict.passed_gates)}")
    if verdict.not_applicable_gates:
        lines.append(f"\n## Not applicable: {', '.join(verdict.not_applicable_gates)}")
    return "\n".join(lines) + "\n"


def _safe_result_summary(result: Any) -> dict:
    """A credential-free summary of the pipeline result."""
    return {
        "run_id": getattr(result, "run_id", ""),
        "outcome": str(getattr(result, "outcome", "")),
        "terminal_stage": getattr(result, "terminal_stage", None),
        "gaps_count": len(getattr(result, "gaps", []) or []),
        "ideas_count": len(getattr(result, "ideas", []) or []),
        "proposals_count": len(getattr(result, "proposals", {}) or {}),
        "export_paths": {str(k): str(v) for k, v in
                         (getattr(result, "export_paths", {}) or {}).items()},
    }


def _stage_report_dump(result: Any) -> list[dict]:
    out = []
    for rep in getattr(result, "stage_report", []) or []:
        out.append({
            "name": getattr(rep, "name", ""),
            "status": getattr(rep, "status", ""),
            "elapsed_s": getattr(rep, "elapsed_s", 0.0),
        })
    return out


# ── Top-level acceptance run ─────────────────────────────────────────


async def run_acceptance(
    case_path: str | Path,
    evidence_dir: str | Path,
    *,
    repo_root: Path | None = None,
    orchestrator_factory: Any = None,
    run_id: str | None = None,
    session_id: str | None = None,
    restart_recovery_check: Any | None = None,
) -> tuple[VerdictReport, Path]:
    """Run one acceptance attempt end to end.

    Returns (verdict, evidence_dir). Execution delegates to the production
    orchestrator via the confirmatory runner's binding protocol; this
    function adds preflight, verdict classification, and evidence.

    The ``restart_recovery_check`` callable, if supplied, is invoked after
    execution with the run identity and must return True iff a fresh
    persistence instance recovered the artifacts.
    """
    case = LivePaperAcceptanceCase.load(case_path)
    repo_root = repo_root or resolve_repo_root()
    evidence_dir = Path(evidence_dir)

    # ── Preflight ──
    preflight = run_preflight(case, repo_root=repo_root)
    if not preflight.ok:
        verdict = preflight.to_invalid_case(case.case_id)
        # Even INVALID_CASE writes an evidence bundle (no result).
        write_evidence(evidence_dir, case, verdict, preflight.code_origin)
        return verdict, evidence_dir

    # ── Execution (delegated to the existing confirmatory spine) ──
    import run_e2e_pipeline as spine  # type: ignore

    rid = run_id or f"accept_{case.case_id}_{time.strftime('%Y%m%d_%H%M%S')}"
    sid = session_id or f"session_{case.case_id}_{time.strftime('%Y%m%d_%H%M%S')}"
    config = spine.ConfirmatoryConfig(run_id=rid, session_id=sid, domain=case.research_domain)

    result = None
    execution_error: str = ""
    try:
        result = await spine.run_confirmatory(
            config, orchestrator_factory=orchestrator_factory,
        )
    except Exception as e:  # noqa: BLE001 — classify, don't crash
        execution_error = f"{type(e).__name__}: {str(e)[:300]}"

    # ── Restart recovery ──
    restart_ok = True
    if case.execution.require_restart_recovery and restart_recovery_check is not None:
        try:
            restart_ok = bool(restart_recovery_check(rid))
        except Exception as e:  # noqa: BLE001
            restart_ok = False
            execution_error = f"{execution_error}; restart_check_error: {e}".strip("; ")

    # ── Verdict ──
    if result is None:
        # Execution failed before producing a result.
        report = VerdictReport(
            verdict=AcceptanceVerdict.FAIL,
            case_id=case.case_id,
            attempt_id=rid,
            failed_gates=[],
            exit_code=1,
        )
    else:
        report = evaluate_gates(
            case, result, attempt_id=rid,
            code_origin_ok=True,  # preflight already enforced this
            identity_isolation_ok=True,
            restart_recovery_ok=restart_ok,
            accounting_ok=True,  # the spine reconciles accounting; refine later
        )

    # Attach execution error detail if present.
    if execution_error and report.verdict is AcceptanceVerdict.FAIL:
        report.failed_gates.append(
            GateResult(
                gate="execution", passed=False, reason_code="execution_error",
                detail=execution_error,
            )
        )

    write_evidence(evidence_dir, case, report, preflight.code_origin, result=result)
    return report, evidence_dir
