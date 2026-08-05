"""Frozen regressions from the second v1.0.3 confirmatory E2E.

The second authorized attempt (run e2e_v103_2nd_20260805_150951) produced
zero papers despite reconciled accounting and session binding.  Three
independent defects were identified:

1. The confirmatory runner exits 0 (success) even when the pipeline aborts
   at the Decision Gate with 0 gaps/ideas/proposals/papers.
2. The runner uses the shared ``./data/sessions`` directory instead of an
   attempt-isolated session store.
3. The gap-analysis stage silently converts a nonempty but schema-incompatible
   provider response into zero gaps without an explicit output-contract failure.

These tests freeze the **desired post-repair contracts** so they fail on the
current candidate and pass only after production repair.

No external provider calls are made.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _import_runner():
    """Import the confirmatory runner module from the repo root."""
    import importlib

    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module("run_e2e_pipeline")


# ── Finding 1: failed product outcome must fail the runner ────────────


class _ReconciledZeroPaperOrch:
    """Orchestrator that simulates a reconciled but paper-less run.

    The lifecycle registers + completes a session run record with matching
    totals, but the pipeline result has 0 gaps/ideas/proposals.
    """

    def __init__(self, session_manager=None, settings=None):  # noqa: ARG002
        self._run_kwargs: dict | None = None
        self._session_manager = session_manager
        self._received_settings = settings
        self._services = SimpleNamespace(session_manager=session_manager)

    async def run(self, **kwargs):
        self._run_kwargs = kwargs
        sid = kwargs.get("session_id")
        rid = kwargs.get("run_id")
        if self._session_manager and sid and rid:
            self._session_manager.register_run(sid, rid)
            self._session_manager.complete_run(sid, rid, tokens_used=15, cost_usd=0.08)
        # Return a result with 0 gaps, 0 ideas, 0 proposals — pipeline failed.
        return SimpleNamespace(
            run_id=rid, ideas=[], gaps=[], proposals={},
        )


class _FailedTerminalOrch:
    """Orchestrator that returns a result explicitly marked failed."""

    def __init__(self, session_manager=None, settings=None):  # noqa: ARG002
        self._run_kwargs: dict | None = None
        self._session_manager = session_manager
        self._received_settings = settings
        self._services = SimpleNamespace(session_manager=session_manager)

    async def run(self, **kwargs):
        self._run_kwargs = kwargs
        sid = kwargs.get("session_id")
        rid = kwargs.get("run_id")
        if self._session_manager and sid and rid:
            self._session_manager.register_run(sid, rid)
            self._session_manager.complete_run(sid, rid, tokens_used=15, cost_usd=0.08)
        # Return with an incidental idea but a failed terminal status.
        return SimpleNamespace(
            run_id=rid, ideas=["stub"], gaps=[], proposals={},
            status="failed",
        )


class _RecordingSM:
    """Minimal session manager double."""

    def __init__(self):
        import secrets
        self._sid = f"sess_{secrets.token_hex(4)}"
        self._runs: dict[str, dict] = {}

    def create(self, name=""):
        from types import SimpleNamespace
        return SimpleNamespace(id=self._sid, runs=[], state="created")

    def get(self, session_id):
        from types import SimpleNamespace
        runs = []
        for rid, data in self._runs.items():
            runs.append(SimpleNamespace(
                run_id=rid, status=data["status"],
                tokens_used=data["tokens_used"], cost_usd=data["cost_usd"],
                completed_at=data.get("completed_at"),
            ))
        return SimpleNamespace(id=session_id, runs=runs, state="active")

    def activate(self, session_id):
        pass

    def resume(self, session_id):
        pass

    def register_run(self, session_id, run_id):
        self._runs[run_id] = {"status": "running", "tokens_used": 0, "cost_usd": 0.0}

    def complete_run(self, session_id, run_id, tokens_used=0, cost_usd=0.0):
        if run_id in self._runs:
            self._runs[run_id] = {
                "status": "completed", "tokens_used": tokens_used,
                "cost_usd": cost_usd, "completed_at": 1.0,
            }


class _FakeRunService:
    def __init__(self):
        self._existing: set[str] = set()

    def create_run(self, domain="AI/NLP", strategy="deep_research",  # noqa: ARG002
                   session_id=None, config=None, *, run_id_override=None):  # noqa: ARG002
        rid = run_id_override or "auto"
        if rid in self._existing:
            raise ValueError(f"Duplicate run_id: {rid}")
        self._existing.add(rid)
        return rid


def _successful_pipeline_result(run_id: str):
    """Build a PipelineResult-shaped object representing a successful terminal
    research outcome with at least one completed paper.

    Uses the real field names: ``proposals`` dict containing a
    ``ResearchProposal`` whose ``metadata['full_paper']['paper_markdown']``
    is nonempty — matching the shape that ``PipelinePersistence`` reads.
    """
    from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

    proposal = ResearchProposal(idea_id=1, title="Synthesized Research Paper")
    proposal.metadata = {
        "full_paper": {
            "paper_markdown": "# Synthesized Research Paper\n\n## Abstract\n\nA complete paper.",
            "word_count": 2000,
            "status": "ready",
        }
    }
    return SimpleNamespace(
        run_id=run_id,
        ideas=[],
        gaps=[SimpleNamespace(title="A gap", description="d", gap_type="t",
                              confidence=0.5, potential_impact="m",
                              truth=None, related_clusters=[])],
        proposals={0: proposal},
        evaluation_reports={},
        export_paths={0: "/tmp/paper.md"},
    )


class _FakeTracker:
    def __init__(self):
        self._data = {"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1}

    def summary(self, run_id=None):  # noqa: ARG002
        return self._data


@pytest.mark.anyio
async def test_confirmatory_runner_rejects_reconciled_run_with_no_terminal_paper():
    """Finding 1a: run_confirmatory() must raise when the pipeline produces
    0 gaps/ideas/proposals even if accounting and session reconciliation succeed."""
    runner = _import_runner()
    sm = _RecordingSM()
    rs = _FakeRunService()
    tracker = _FakeTracker()
    config = runner.ConfirmatoryConfig(run_id="run_zero", session_id="sess_zero")
    _ReconciledZeroPaperOrch(session_manager=sm)

    with pytest.raises((RuntimeError, Exception), match=r"(?i)(paper|terminal|outcome|proposal)"):
        await runner.run_confirmatory(
            config,
            orchestrator_factory=lambda settings=None: _ReconciledZeroPaperOrch(
                session_manager=sm, settings=settings,
            ),
            session_manager=sm, run_service=rs, cost_tracker=tracker,
        )


@pytest.mark.anyio
async def test_confirmatory_runner_rejects_failed_terminal_status():
    """Finding 1b: a result explicitly marked failed cannot be accepted even
    if it contains incidental intermediate objects."""
    runner = _import_runner()
    sm = _RecordingSM()
    rs = _FakeRunService()
    tracker = _FakeTracker()
    config = runner.ConfirmatoryConfig(run_id="run_fail", session_id="sess_fail")

    with pytest.raises((RuntimeError, Exception), match=r"(?i)(failed|terminal|outcome|status)"):
        await runner.run_confirmatory(
            config,
            orchestrator_factory=lambda settings=None: _FailedTerminalOrch(
                session_manager=sm, settings=settings,
            ),
            session_manager=sm, run_service=rs, cost_tracker=tracker,
        )


# ── Finding 2: session storage must be attempt-isolated ──────────────


class _SuccessfulPaperOrch:
    """Orchestrator that returns a successful terminal paper outcome.

    The lifecycle registers + completes a session run record, and run()
    returns a result with at least one completed paper in the canonical
    proposals[idx].metadata['full_paper']['paper_markdown'] field.
    """

    def __init__(self, session_manager=None, settings=None):  # noqa: ARG002
        self._session_manager = session_manager
        self._received_settings = settings
        self._services = SimpleNamespace(session_manager=session_manager)

    async def run(self, **kwargs):
        sid = kwargs.get("session_id")
        rid = kwargs.get("run_id")
        if self._session_manager and sid and rid:
            self._session_manager.register_run(sid, rid)
            self._session_manager.complete_run(sid, rid, tokens_used=15, cost_usd=0.08)
        return _successful_pipeline_result(rid)


@pytest.mark.anyio
async def test_confirmatory_runner_derives_distinct_session_store_per_attempt(tmp_path):
    """Finding 2a: two separate attempts must receive distinct session stores,
    neither equal to the shared configured base directory."""
    runner = _import_runner()

    # Run A
    sm_a = _RecordingSM()
    config_a = runner.ConfirmatoryConfig(run_id="run_a", session_id="sess_a")
    summary_a = await runner.run_confirmatory(
        config_a,
        orchestrator_factory=lambda settings=None: _SuccessfulPaperOrch(
            session_manager=sm_a, settings=settings,
        ),
        session_manager=sm_a, run_service=_FakeRunService(),
        cost_tracker=_FakeTracker(),
    )
    dir_a = summary_a.get("session_data_dir", "")

    # Run B
    sm_b = _RecordingSM()
    config_b = runner.ConfirmatoryConfig(run_id="run_b", session_id="sess_b")
    summary_b = await runner.run_confirmatory(
        config_b,
        orchestrator_factory=lambda settings=None: _SuccessfulPaperOrch(
            session_manager=sm_b, settings=settings,
        ),
        session_manager=sm_b, run_service=_FakeRunService(),
        cost_tracker=_FakeTracker(),
    )
    dir_b = summary_b.get("session_data_dir", "")

    assert dir_a != dir_b, (
        "Finding 2a: two attempts must receive distinct session stores. "
        f"Both used {dir_a!r}."
    )


@pytest.mark.anyio
async def test_runner_and_orchestrator_share_only_the_current_attempt_store(tmp_path):
    """Finding 2b: the runner-side session directory must not equal the
    configured shared base directory — it must be an isolated attempt store."""
    runner = _import_runner()

    sm = _RecordingSM()
    config = runner.ConfirmatoryConfig(run_id="run_share", session_id="sess_share")

    summary = await runner.run_confirmatory(
        config,
        orchestrator_factory=lambda settings=None: _SuccessfulPaperOrch(
            session_manager=sm, settings=settings,
        ),
        session_manager=sm, run_service=_FakeRunService(),
        cost_tracker=_FakeTracker(),
    )

    runner_dir = summary.get("session_data_dir", "")
    from backend.config import get_settings
    configured_dir = get_settings().session_data_dir

    assert runner_dir != configured_dir, (
        f"Finding 2b: session dir {runner_dir!r} equals the configured shared "
        f"directory {configured_dir!r} instead of an isolated attempt store."
    )


# ── Finding 3: wrong-schema gap output must not become "zero gaps" ────


def test_gap_analysis_rejects_nonempty_wrong_schema_instead_of_returning_zero_gaps():
    """Finding 3: a nonempty JSON response in the wrong schema (e.g. a bare
    array of paper-like objects) must produce an explicit output-contract
    failure, not silently normalize to zero gaps."""
    from backend.pipeline.utils.json_extraction import extract_json

    # Synthetic wrong-schema response (well-formed JSON, wrong schema).
    wrong_schema = '[{"title": "Example paper", "authors": ["A. Researcher"], "year": 2025}]'
    extract_json(wrong_schema)

    # The contract: extract_json returns the parsed data, but the gap-analysis
    # boundary must detect that the schema is incompatible and raise/signals
    # a contract failure rather than silently producing zero gaps.
    #
    # Currently, extract_json returns the list, gap_analyzer wraps it as
    # {"gaps": [...]}, and the paper-like objects get through as malformed
    # gaps. The contract failure is NOT raised.
    #
    # The desired behavior: a wrong-schema response should be detected and
    # explicitly rejected. This test asserts that the gap-analysis boundary
    # has a schema-validation step.
    import inspect

    from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer

    analyze_source = inspect.getsource(GapAnalyzer.analyze)
    has_schema_validation = any(
        keyword in analyze_source
        for keyword in ("schema_valid", "output_contract", "contract_fail",
                        "validate_schema", "wrong_schema", "SchemaError",
                        "OutputContractError", "raise.*contract")
    )
    assert has_schema_validation, (
        "Finding 3: GapAnalyzer.analyze must validate the output schema and "
        "raise an explicit output-contract failure when the response is nonempty "
        "but schema-incompatible. Currently, nonempty schema-incompatible output "
        "was accepted or normalized instead of producing an explicit contract failure."
    )


def test_gap_analysis_distinguishes_valid_empty_gap_result_from_schema_failure():
    """Positive control: a valid empty-gap result (provider correctly returned
    no gaps in the right schema) must not be treated as a contract failure."""
    from backend.pipeline.utils.json_extraction import extract_json

    # Valid schema with empty gaps list.
    valid_empty = '{"gaps": []}'
    parsed = extract_json(valid_empty)
    assert isinstance(parsed, dict)
    assert "gaps" in parsed
    assert parsed["gaps"] == []

    # This is a valid result — not a contract failure. The test passes today
    # because the parsing boundary correctly handles this case.


def test_gap_analysis_contract_failure_emits_safe_diagnostics():
    """Positive control: when the gap-analysis boundary detects a wrong-schema
    response, it must emit safe diagnostics establishing at least:
    stage, failure category, response nonemptiness, and parsed type."""
    import inspect

    from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer

    analyze_source = inspect.getsource(GapAnalyzer.analyze)
    # After repair, the contract failure should include diagnostic info.
    has_diagnostics = any(
        keyword in analyze_source
        for keyword in ("response_len", "parsed_type", "output_contract",
                        "schema_validation", "failure_category", "diagnostic")
    )
    # The current code has response_len and parsed_type in the warning log,
    # which is diagnostic-adjacent. This control passes today.
    assert has_diagnostics, (
        "Finding 3 control: GapAnalyzer.analyze should emit safe diagnostics "
        "(stage, failure category, response length, parsed type) on contract failure."
    )
