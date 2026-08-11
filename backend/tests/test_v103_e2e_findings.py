"""Frozen regressions from the v1.0.3 confirmatory E2E (run_20260805_045655).

The confirmatory E2E exposed a stage-attribution defect and E2E-protocol
defects.  These tests freeze the **desired post-repair contracts** so they
fail on the current candidate (5861789) and pass only after the production
repair lands.

Root-cause analysis (corrected):
  GatewayProvider puts ``stage`` and ``run_id`` into every ``LLMRequest``
  it constructs.  But ``LLMGateway.call()`` invokes the provider callback
  (``self._provider_fn``) with only ``messages, temperature, max_tokens,
  schema, tools`` — it **drops** ``request.stage`` and ``request.run_id``.

  The orchestrator callback then tries to reconstruct context via
  ``getattr(self._gateway, "_stage", "")``, but ``self._gateway`` is the
  ``LLMGateway`` object (which has no ``_stage``), not the
  ``GatewayProvider``.  Result: ``run_id`` survives via orchestrator state,
  but ``stage`` is always ``""``.

  The narrow authoritative defect is therefore:
    ``LLMRequest.stage/run_id`` is not propagated across
    ``LLMGateway.call()`` → ``provider callback``.

  The existing ``GatewayProvider`` design (all call sites use
  ``complete()``/``structured_output()``, routed through the gateway) is
  correct and must not be abandoned.

No external provider calls are made.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
from backend.pipeline.gateway.gateway import LLMGateway, LLMRequest
from backend.pipeline.gateway.gateway_provider import GatewayProvider
from backend.pipeline.gateway.token_budget import TokenBudgeter
from backend.providers.base import CostEvent, LLMProvider, LLMResponse

# ── Test doubles ─────────────────────────────────────────────────────


class _RecordingInnerProvider(LLMProvider):
    """Inner provider that records every call and fires the cost callback."""

    provider_name = "openai"
    default_model = "glm-4.6"

    def __init__(self) -> None:
        super().__init__()
        self.usage_calls: list[dict] = []
        self.structured_usage_calls: list[dict] = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
        return "response"

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):  # noqa: ARG002
        if False:  # pragma: no cover
            yield ""

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096):  # noqa: ARG002
        return {"k": 1}

    async def complete_with_usage(
        self, messages, temperature=0.7, max_tokens=4096, stage="", run_id=None,  # noqa: ARG002
    ) -> LLMResponse:
        self.usage_calls.append({"stage": stage, "run_id": run_id})
        if self._cost_callback is not None:
            self._cost_callback(CostEvent(
                provider="openai", model="glm-4.6",
                input_tokens=10, output_tokens=5, stage=stage, run_id=run_id,
            ))
        return LLMResponse(content="response", input_tokens=10, output_tokens=5)

    async def structured_output_with_usage(
        self, messages, schema, temperature=0.3, stage="", run_id=None,  # noqa: ARG002
    ) -> LLMResponse:
        self.structured_usage_calls.append({"stage": stage, "run_id": run_id})
        if self._cost_callback is not None:
            self._cost_callback(CostEvent(
                provider="openai", model="glm-4.6",
                input_tokens=8, output_tokens=4, stage=stage, run_id=run_id,
            ))
        return LLMResponse(content="", structured={"k": 1}, input_tokens=8, output_tokens=4)


def _build_gateway_and_provider():
    """Build a real LLMGateway + GatewayProvider wired to a recording inner provider.

    The orchestrator's provider callback is replicated exactly (the production
    closure from _orchestrator.py:309-353) so the test exercises the real
    gateway-context propagation path, not a simplified stand-in.
    """
    inner = _RecordingInnerProvider()
    cap_registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter(default_context=4096)
    gateway = LLMGateway(
        capability_registry=cap_registry,
        token_budgeter=budgeter,
        default_model=inner.default_model,
    )
    provider = GatewayProvider(gateway, inner_provider=inner, stage="gap_analysis", run_id="run_test")

    # Replicate the orchestrator's provider callback (production closure shape).
    # After the v1.0.3 gateway-context repair, the callback receives stage and
    # run_id as kwargs from LLMGateway.call() (which propagates them from the
    # LLMRequest constructed by GatewayProvider).
    async def _provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None, stage="", run_id=None):
        if schema:
            if hasattr(inner, "structured_output_with_usage"):
                resp = await inner.structured_output_with_usage(
                    messages, schema, temperature, stage=stage, run_id=run_id,
                )
                structured = getattr(resp, "structured", None)
                if structured is not None:
                    return structured
                return {}
            return await inner.structured_output(messages, schema, temperature)
        if hasattr(inner, "complete_with_usage"):
            resp = await inner.complete_with_usage(
                messages, temperature, max_tokens, stage=stage, run_id=run_id,
            )
            return resp.content if hasattr(resp, "content") else str(resp)
        return await inner.complete(messages, temperature, max_tokens)

    gateway.set_provider_fn(_provider_fn)
    return gateway, provider, inner


# ── Finding 1: LLMGateway.call() must pass stage/run_id to the callback ─


@pytest.mark.anyio
async def test_gateway_call_passes_stage_and_run_id_to_provider_callback():
    """Finding 1: LLMGateway.call() must propagate LLMRequest.stage and
    LLMRequest.run_id to the provider callback.

    After repair, the callback receives them as kwargs.  This test installs a
    callback that accepts stage/run_id and verifies call() actually passes the
    request's values through.
    """
    inner = _RecordingInnerProvider()
    cap_registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter(default_context=4096)
    gateway = LLMGateway(
        capability_registry=cap_registry, token_budgeter=budgeter,
        default_model=inner.default_model,
    )

    received: dict = {}

    async def _recording_cb(*, messages, temperature, max_tokens, schema=None, tools=None, stage="", run_id=None):  # noqa: ARG001
        received["stage"] = stage
        received["run_id"] = run_id
        return "ok"

    gateway.set_provider_fn(_recording_cb)

    request = LLMRequest(
        task="gap_analysis",
        messages=[{"role": "user", "content": "q"}],
        stage="gap_analysis",
        run_id="run_test",
    )
    await gateway.call(request)

    assert received.get("stage") == "gap_analysis", (
        "Finding 1: LLMGateway.call() must pass request.stage to the provider "
        f"callback. Got stage={received.get('stage')!r}."
    )
    assert received.get("run_id") == "run_test", (
        "Finding 1: LLMGateway.call() must pass request.run_id to the provider "
        f"callback. Got run_id={received.get('run_id')!r}."
    )


# ── Finding 2: GatewayProvider.complete() carries stage through to inner usage ─


@pytest.mark.anyio
async def test_gateway_provider_complete_carries_stage_to_inner_usage():
    """Finding 2: after set_context('gap_analysis', 'run_test'), a
    GatewayProvider.complete() call must invoke the inner provider's
    complete_with_usage() with stage='gap_analysis' and run_id='run_test'.

    This fails because LLMGateway.call() drops the stage, so the callback
    reconstructs stage='' from the gateway object.
    """
    from backend.providers.provider_factory import CostTracker

    tracker = CostTracker()
    gateway, provider, inner = _build_gateway_and_provider()
    inner._cost_callback = tracker.record

    await provider.complete(
        [{"role": "user", "content": "q"}], temperature=0.3, max_tokens=100,
    )

    # The inner provider's complete_with_usage must have received the stage.
    assert len(inner.usage_calls) == 1, "Expected exactly one usage call"
    assert inner.usage_calls[0]["stage"] == "gap_analysis", (
        "Finding 2: inner complete_with_usage received blank stage. "
        "GatewayProvider put stage='gap_analysis' into the LLMRequest, but "
        "LLMGateway.call() dropped it before invoking the callback."
    )
    assert inner.usage_calls[0]["run_id"] == "run_test"


# ── Finding 3: GatewayProvider.structured_output() preserves stage ─────


@pytest.mark.anyio
async def test_gateway_provider_structured_output_carries_stage():
    """Finding 3: GatewayProvider.structured_output() must preserve the same
    stage and run_id through the usage-aware path."""
    gateway, provider, inner = _build_gateway_and_provider()

    await provider.structured_output(
        [{"role": "user", "content": "q"}], {"type": "object"}, temperature=0.3,
    )

    assert len(inner.structured_usage_calls) == 1, "Expected exactly one structured-usage call"
    assert inner.structured_usage_calls[0]["stage"] == "gap_analysis", (
        "Finding 3: inner structured_output_with_usage received blank stage. "
        "The gateway dropped the LLMRequest.stage before calling the callback."
    )
    assert inner.structured_usage_calls[0]["run_id"] == "run_test"


# ── Finding 4: cost event + ledger carry stage and isolated run_id ─────


@pytest.mark.anyio
async def test_cost_event_and_ledger_carry_stage_and_run_id(tmp_path):
    """Finding 4: the resulting cost event and persisted ledger must contain
    stage='gap_analysis' and only 'run_test'."""
    from backend.providers.provider_factory import CostTracker

    tracker = CostTracker()
    gateway, provider, inner = _build_gateway_and_provider()
    inner._cost_callback = tracker.record

    await provider.complete(
        [{"role": "user", "content": "q"}], temperature=0.3, max_tokens=100,
    )

    events = tracker._filtered("run_test")
    assert len(events) == 1
    assert events[0].stage == "gap_analysis", (
        "Finding 4: cost event has blank stage — the gateway dropped it."
    )

    ledger_path = tmp_path / "run_test_cost_ledger.jsonl"
    tracker.persist(str(ledger_path), run_id="run_test")
    records = [json.loads(line) for line in ledger_path.read_text().splitlines()]
    assert all(r["stage"] == "gap_analysis" for r in records), (
        "Finding 4: ledger records must all carry stage='gap_analysis'."
    )
    assert all(r["run_id"] == "run_test" for r in records)


# ── Findings 5-8: E2E runner protocol contracts (behavioral) ─────────


def _import_runner():
    """Import the confirmatory runner module from the repo root."""
    import importlib
    import sys

    repo_root = str(Path(__file__).resolve().parents[2])
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    return importlib.import_module("run_e2e_pipeline")


class _FakeSessionRun:
    """Mimics SessionRunRecord for test verification."""

    def __init__(self, run_id, status="running", tokens_used=0, cost_usd=0.0):
        self.run_id = run_id
        self.status = status
        self.tokens_used = tokens_used
        self.cost_usd = cost_usd
        self.started_at = 1.0
        self.completed_at = None


class _FakeSession:
    """Mimics Session for test verification."""

    def __init__(self, session_id, state="active"):
        self.id = session_id
        self.runs: list[_FakeSessionRun] = []
        self.state = state


class _FakeSessionManager:
    """Session manager double that owns run records internally.

    The fake orchestrator simulates the production lifecycle by calling
    register_run + complete_run on this manager during run().
    """

    def __init__(self):
        self._sessions: dict[str, _FakeSession] = {}
        self.activated: list[str] = []
        self.resumed: list[str] = []
        self.registered: list[tuple[str, str]] = []
        self.completed: list[tuple[str, str]] = []

    def create(self, name=""):
        import secrets
        sid = f"sess_{secrets.token_hex(4)}"
        self._sessions[sid] = _FakeSession(sid, state="created")
        return self._sessions[sid]

    def get(self, session_id):
        return self._sessions.get(session_id)

    def activate(self, session_id):
        self.activated.append(session_id)
        s = self._sessions.get(session_id)
        if s:
            s.state = "active"

    def resume(self, session_id):
        self.resumed.append(session_id)
        s = self._sessions.get(session_id)
        if s:
            s.state = "active"

    def register_run(self, session_id, run_id):
        self.registered.append((session_id, run_id))
        s = self._sessions.get(session_id)
        if s:
            s.runs.append(_FakeSessionRun(run_id))

    def complete_run(self, session_id, run_id, tokens_used=0, cost_usd=0.0):
        self.completed.append((session_id, run_id))
        s = self._sessions.get(session_id)
        if s:
            for r in s.runs:
                if r.run_id == run_id:
                    r.status = "completed"
                    r.tokens_used = tokens_used
                    r.cost_usd = cost_usd
                    r.completed_at = 2.0
                    break

    def _save(self, session):
        self._sessions[session.id] = session


class _FakeOrchestrator:
    """Orchestrator double that simulates the production lifecycle.

    During run(), it calls register_run + complete_run on the injected
    session manager — exactly as the real orchestrator/lifecycle does.
    """

    def __init__(self, result_run_id="run_test", cost_summary=None,
                 session_manager=None, lifecycle_tokens=15, lifecycle_cost=0.08,
                 settings=None):
        self._run_kwargs: dict | None = None
        self._received_settings = settings
        self._result_run_id = result_run_id
        self._cost_summary = cost_summary or {
            "total_tokens": lifecycle_tokens, "total_cost_usd": lifecycle_cost, "event_count": 1,
        }
        self._session_manager = session_manager
        self._lifecycle_tokens = lifecycle_tokens
        self._lifecycle_cost = lifecycle_cost
        # Expose the session manager through _services so the runner's
        # visibility check (services.session_manager.get(session_id)) passes.
        from types import SimpleNamespace
        self._services = SimpleNamespace(session_manager=session_manager)

    async def run(self, **kwargs):
        self._run_kwargs = kwargs
        session_id = kwargs.get("session_id")
        run_id = kwargs.get("run_id")
        # Simulate the production lifecycle: register then complete.
        if self._session_manager and session_id and run_id:
            self._session_manager.register_run(session_id, run_id)
            self._session_manager.complete_run(
                session_id, run_id,
                tokens_used=self._lifecycle_tokens,
                cost_usd=self._lifecycle_cost,
            )
        from types import SimpleNamespace

        # Build a result with at least one completed paper so the runner's
        # terminal-outcome validation accepts it.
        proposal = SimpleNamespace(
            sections={"title": "Test Paper"},
            metadata={"full_paper": {"paper_markdown": "# Hermetic Completed Paper\n\nSubstantive test content."}},
        )
        return SimpleNamespace(
            run_id=self._result_run_id,
            ideas=[], gaps=[],
            proposals={0: proposal},
        )


class _FakeCostTracker:
    """Minimal cost tracker double."""

    def __init__(self, summary_data):
        self._summary = summary_data

    def summary(self, run_id=None):  # noqa: ARG002
        return self._summary


class _FakeRunService:
    """RunService double that enforces run-ID uniqueness."""

    def __init__(self):
        self._existing: set[str] = set()

    def create_run(self, domain="AI/NLP", strategy="deep_research",  # noqa: ARG002
                   session_id=None, config=None, *, run_id_override=None):  # noqa: ARG002
        rid = run_id_override or "auto_gen"
        if rid in self._existing:
            raise ValueError(f"Duplicate run_id: {rid}")
        self._existing.add(rid)
        return rid


# ── The four original frozen tests, now strengthened ──


@pytest.mark.anyio
async def test_runner_obtains_explicit_run_id_before_execution():
    """Finding 5: the runner must obtain one explicit run ID before
    orchestrator/provider construction and pass that exact ID to
    orchestrator.run()."""
    runner = _import_runner()
    cost_summary = {"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1}
    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_test")
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    rs = _FakeRunService()
    tracker = _FakeCostTracker(cost_summary)
    orch = _FakeOrchestrator(result_run_id="run_test", session_manager=sm)

    await runner.run_confirmatory(
        config, orchestrator_factory=lambda settings=None: orch,
        session_manager=sm, run_service=rs, cost_tracker=tracker,
    )

    assert orch._run_kwargs is not None, "orchestrator.run() was never called"
    assert orch._run_kwargs.get("run_id") == "run_test"
    assert orch._run_kwargs.get("session_id") == "sess_test"


@pytest.mark.anyio
async def test_runner_binds_session_id():
    """Finding 6: the runner must resolve a session and the lifecycle must
    register + complete exactly one run record. The runner itself must NOT
    call register_run or complete_run."""
    runner = _import_runner()
    cost_summary = {"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1}
    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_test")
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    rs = _FakeRunService()
    tracker = _FakeCostTracker(cost_summary)
    orch = _FakeOrchestrator(result_run_id="run_test", session_manager=sm)

    await runner.run_confirmatory(
        config, orchestrator_factory=lambda settings=None: orch,
        session_manager=sm, run_service=rs, cost_tracker=tracker,
    )

    # The runner resolved the session (already active, so no activate needed).
    # The lifecycle (fake orchestrator) did register + complete exactly once.
    assert ("sess_test", "run_test") in sm.registered
    assert ("sess_test", "run_test") in sm.completed
    # Runner-side calls to register/complete are prohibited — verify
    # by checking the runner did not add extra records beyond the lifecycle's.
    session = sm.get("sess_test")
    matching = [r for r in session.runs if r.run_id == "run_test"]
    assert len(matching) == 1, (
        f"Expected exactly one session run record, found {len(matching)}"
    )


@pytest.mark.anyio
async def test_runner_has_pre_provider_binding_validation():
    """Finding 7: invalid identifiers and duplicate durable run IDs must
    abort before orchestrator construction."""
    runner = _import_runner()

    factory_called: list[bool] = []

    def _factory():
        factory_called.append(True)
        return _FakeOrchestrator()

    # Blank run_id → rejected before factory.
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    config_blank = runner.ConfirmatoryConfig(run_id="", session_id="sess_test")
    with pytest.raises(runner.PreflightError, match="run_id"):
        await runner.run_confirmatory(
            config_blank, orchestrator_factory=_factory, session_manager=sm,
        )
    assert not factory_called

    # Unsafe run_id → rejected before factory.
    config_unsafe = runner.ConfirmatoryConfig(run_id="run;rm -rf /", session_id="sess_test")
    with pytest.raises(runner.PreflightError, match="unsafe"):
        await runner.run_confirmatory(
            config_unsafe, orchestrator_factory=_factory, session_manager=sm,
        )
    assert not factory_called

    # Duplicate durable run ID → RunService rejects, factory not called.
    rs = _FakeRunService()
    rs._existing.add("run_dup")
    config_dup = runner.ConfirmatoryConfig(run_id="run_dup", session_id="sess_test")
    with pytest.raises(runner.PreflightError, match="Duplicate"):
        await runner.run_confirmatory(
            config_dup, orchestrator_factory=_factory, session_manager=sm, run_service=rs,
        )
    assert not factory_called, "Orchestrator factory must not be called when run-ID binding fails"


@pytest.mark.anyio
async def test_runner_verifies_session_completion_against_ledger():
    """Finding 8: session completion must be verified against the same
    run-scoped ledger totals. The lifecycle (fake orchestrator) performs
    register_run + complete_run; the runner verifies."""
    runner = _import_runner()
    cost_summary = {"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1}
    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_test")
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    rs = _FakeRunService()
    tracker = _FakeCostTracker(cost_summary)
    orch = _FakeOrchestrator(
        result_run_id="run_test", session_manager=sm,
        lifecycle_tokens=15, lifecycle_cost=0.08,
    )

    result = await runner.run_confirmatory(
        config, orchestrator_factory=lambda settings=None: orch,
        session_manager=sm, run_service=rs, cost_tracker=tracker,
    )

    assert result["binding_verified"] is True
    assert result["session_reconciled"] is True
    assert result["session_tokens"] == 15
    assert abs(result["session_cost_usd"] - 0.08) < 1e-6


# ── Strengthened behavioral tests ──


@pytest.mark.anyio
async def test_duplicate_session_run_records_fail_verification():
    """Duplicate session run records (e.g. from double registration) must
    fail the runner's verification."""
    runner = _import_runner()
    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_test")
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    rs = _FakeRunService()

    # Orchestrator that registers twice (simulating the original bug).
    class _DoubleRegOrch(_FakeOrchestrator):
        async def run(self, **kwargs):
            self._run_kwargs = kwargs
            sid = kwargs.get("session_id")
            rid = kwargs.get("run_id")
            if self._session_manager and sid and rid:
                self._session_manager.register_run(sid, rid)
                self._session_manager.register_run(sid, rid)  # duplicate
            from types import SimpleNamespace
            return SimpleNamespace(run_id=self._result_run_id)

    orch = _DoubleRegOrch(result_run_id="run_test", session_manager=sm)

    with pytest.raises(RuntimeError, match="exactly one"):
        await runner.run_confirmatory(
            config, orchestrator_factory=lambda settings=None: orch,
            session_manager=sm, run_service=rs,
        )


@pytest.mark.anyio
async def test_totals_mismatch_fails_verification():
    """A totals mismatch between the cost summary and the session record
    must fail verification."""
    runner = _import_runner()
    cost_summary = {"total_tokens": 99, "total_cost_usd": 0.99, "event_count": 1}
    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_test")
    sm = _FakeSessionManager()
    sm._sessions["sess_test"] = _FakeSession("sess_test")
    rs = _FakeRunService()
    tracker = _FakeCostTracker(cost_summary)
    # Orchestrator completes with different totals than the tracker reports.
    orch = _FakeOrchestrator(
        result_run_id="run_test", session_manager=sm,
        lifecycle_tokens=15, lifecycle_cost=0.08,
    )

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        await runner.run_confirmatory(
            config, orchestrator_factory=lambda settings=None: orch,
            session_manager=sm, run_service=rs, cost_tracker=tracker,
        )


@pytest.mark.anyio
async def test_terminal_state_session_rejected_before_construction():
    """A supplied session in a terminal state must be rejected before
    orchestrator construction."""
    runner = _import_runner()
    sm = _FakeSessionManager()
    sm._sessions["sess_ended"] = _FakeSession("sess_ended", state="ended")
    rs = _FakeRunService()
    factory_called: list[bool] = []

    def _factory():
        factory_called.append(True)
        return _FakeOrchestrator()

    config = runner.ConfirmatoryConfig(run_id="run_test", session_id="sess_ended")
    with pytest.raises(runner.PreflightError, match="terminal"):
        await runner.run_confirmatory(
            config, orchestrator_factory=_factory, session_manager=sm, run_service=rs,
        )
    assert not factory_called


@pytest.mark.anyio
async def test_bound_run_and_session_ids_reach_orchestrator_run():
    """The exact bound run_id and resolved session_id must reach
    orchestrator.run()."""
    runner = _import_runner()
    config = runner.ConfirmatoryConfig(run_id="run_exact", session_id="sess_exact")
    sm = _FakeSessionManager()
    sm._sessions["sess_exact"] = _FakeSession("sess_exact")
    rs = _FakeRunService()
    tracker = _FakeCostTracker({"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1})
    orch = _FakeOrchestrator(result_run_id="run_exact", session_manager=sm)

    await runner.run_confirmatory(
        config, orchestrator_factory=lambda settings=None: orch,
        session_manager=sm, run_service=rs, cost_tracker=tracker,
    )

    assert orch._run_kwargs.get("run_id") == "run_exact"
    assert orch._run_kwargs.get("session_id") == "sess_exact"


# ── Session-wiring tests: runner and orchestrator share the session store ──


@pytest.mark.anyio
async def test_factory_receives_session_enabled_true(tmp_path):
    """The orchestrator factory must receive settings with session_enabled=True."""
    runner = _import_runner()
    from backend.pipeline.session.manager import SessionManager

    real_sm = SessionManager(data_dir=str(tmp_path))
    sess = real_sm.create(name="test")
    real_sm.activate(sess.id)
    config = runner.ConfirmatoryConfig(run_id="run_se", session_id=sess.id)
    rs = _FakeRunService()
    tracker = _FakeCostTracker({"total_tokens": 15, "total_cost_usd": 0.08, "event_count": 1})
    received_settings = []

    class _SettingsCapturingOrch(_FakeOrchestrator):
        def __init__(self, settings=None, **kw):  # noqa: ARG002
            super().__init__(result_run_id="run_se", session_manager=real_sm)
            received_settings.append(settings)

    await runner.run_confirmatory(
        config,
        orchestrator_factory=lambda settings=None: _SettingsCapturingOrch(settings=settings),
        session_manager=real_sm, run_service=rs, cost_tracker=tracker,
    )

    assert len(received_settings) == 1
    assert received_settings[0].session_enabled is True, (
        "Orchestrator factory must receive session_enabled=True."
    )

    assert len(received_settings) == 1
    assert received_settings[0].session_enabled is True, (
        "Orchestrator factory must receive session_enabled=True."
    )


@pytest.mark.anyio
async def test_two_managers_share_session_directory(tmp_path):
    """Two separate SessionManager instances on the same directory can see
    each other's sessions through the public JSON-persisted API."""
    from backend.pipeline.session.manager import SessionManager

    sm1 = SessionManager(data_dir=str(tmp_path))
    sm2 = SessionManager(data_dir=str(tmp_path))

    session = sm1.create(name="cross-test")
    sm1.activate(session.id)

    # sm2 must see the session created by sm1.
    seen = sm2.get(session.id)
    assert seen is not None, "Second SessionManager must see sessions from the same directory."
    assert seen.id == session.id


@pytest.mark.anyio
async def test_runner_session_visible_to_orchestrator_session_manager(tmp_path):
    """A session created through the runner-side manager is visible to a
    separate SessionManager opened on the same directory — proving the runner
    and production lifecycle share the same store."""
    from backend.pipeline.session.manager import SessionManager

    # Runner-side manager creates + activates a session.
    runner_sm = SessionManager(data_dir=str(tmp_path))
    sess = runner_sm.create(name="confirmatory")
    runner_sm.activate(sess.id)

    # A second manager (simulating the orchestrator's ServiceRegistry) opens
    # the same directory and can see the session + simulate lifecycle ops.
    orch_sm = SessionManager(data_dir=str(tmp_path))
    seen = orch_sm.get(sess.id)
    assert seen is not None, "Orchestrator-side manager must see runner-created session."
    assert seen.state.value == "active"

    # The lifecycle can register + complete through the second manager.
    orch_sm.register_run(sess.id, "run_cross")
    orch_sm.complete_run(sess.id, "run_cross", tokens_used=42, cost_usd=0.05)

    # The runner-side manager sees the lifecycle's result.
    runner_view = runner_sm.get(sess.id)
    matching = [r for r in runner_view.runs if r.run_id == "run_cross"]
    assert len(matching) == 1
    assert matching[0].status == "completed"
    assert matching[0].tokens_used == 42


@pytest.mark.anyio
async def test_orchestrator_with_null_session_manager_rejected_before_run(tmp_path):
    """If the orchestrator factory returns an orchestrator with
    services.session_manager=None (session management not enabled), execution
    must abort before orchestrator.run() or any provider call."""
    runner = _import_runner()
    from backend.pipeline.session.manager import SessionManager

    real_sm = SessionManager(data_dir=str(tmp_path))
    sess = real_sm.create(name="test")
    real_sm.activate(sess.id)
    config = runner.ConfirmatoryConfig(run_id="run_null", session_id=sess.id)
    rs = _FakeRunService()
    run_called: list[bool] = []

    class _NullSessionOrch(_FakeOrchestrator):
        def __init__(self, settings=None, **kw):  # noqa: ARG002
            super().__init__(result_run_id="run_null", session_manager=None)
            # Override _services to have session_manager=None.
            from types import SimpleNamespace
            self._services = SimpleNamespace(session_manager=None)

        async def run(self, **kwargs):
            run_called.append(True)
            from types import SimpleNamespace
            return SimpleNamespace(run_id="run_null")

    with pytest.raises(runner.PreflightError, match="session management is not enabled"):
        await runner.run_confirmatory(
            config,
            orchestrator_factory=lambda settings=None: _NullSessionOrch(settings=settings),
            session_manager=real_sm, run_service=rs,
        )
    assert not run_called, "orchestrator.run() must not be called when session_manager is None"


@pytest.mark.anyio
async def test_wrong_session_store_rejected_before_run(tmp_path):
    """If the orchestrator's session manager points to a different directory
    than the runner's, the resolved session is not visible and execution
    must abort before orchestrator.run()."""
    runner = _import_runner()
    from backend.pipeline.session.manager import SessionManager

    # Runner creates session on dir A.
    dir_a = tmp_path / "sessions_a"
    dir_b = tmp_path / "sessions_b"
    runner_sm = SessionManager(data_dir=str(dir_a))
    sess = runner_sm.create(name="test")
    runner_sm.activate(sess.id)
    config = runner.ConfirmatoryConfig(run_id="run_wrong", session_id=sess.id)
    rs = _FakeRunService()
    run_called: list[bool] = []

    # Orchestrator opens a DIFFERENT directory (B).
    orch_sm = SessionManager(data_dir=str(dir_b))

    class _WrongDirOrch(_FakeOrchestrator):
        def __init__(self, settings=None, **kw):  # noqa: ARG002
            super().__init__(result_run_id="run_wrong", session_manager=orch_sm)

        async def run(self, **kwargs):
            run_called.append(True)
            from types import SimpleNamespace
            return SimpleNamespace(run_id="run_wrong")

    with pytest.raises(runner.PreflightError, match="not visible"):
        await runner.run_confirmatory(
            config,
            orchestrator_factory=lambda settings=None: _WrongDirOrch(settings=settings),
            session_manager=runner_sm, run_service=rs,
        )
    assert not run_called, "orchestrator.run() must not be called when session is not visible"


@pytest.mark.anyio
async def test_shared_directory_lifecycle_through_orchestrator_manager(tmp_path):
    """Full protocol: runner creates session via manager A, orchestrator exposes
    manager B on the same directory, lifecycle registers+completes through B,
    runner verifies through A after execution."""
    runner = _import_runner()
    from backend.pipeline.session.manager import SessionManager

    shared_dir = str(tmp_path / "shared_sessions")

    # Manager A (runner-side).
    runner_sm = SessionManager(data_dir=shared_dir)
    sess = runner_sm.create(name="confirmatory")
    runner_sm.activate(sess.id)

    # Manager B (orchestrator-side) on the same directory.
    orch_sm = SessionManager(data_dir=shared_dir)

    config = runner.ConfirmatoryConfig(run_id="run_shared", session_id=sess.id)
    rs = _FakeRunService()
    tracker = _FakeCostTracker({"total_tokens": 20, "total_cost_usd": 0.10, "event_count": 1})

    class _SharedOrch(_FakeOrchestrator):
        def __init__(self, settings=None, **kw):  # noqa: ARG002
            super().__init__(
                result_run_id="run_shared", session_manager=orch_sm,
                lifecycle_tokens=20, lifecycle_cost=0.10,
            )

    result = await runner.run_confirmatory(
        config,
        orchestrator_factory=lambda settings=None: _SharedOrch(settings=settings),
        session_manager=runner_sm, run_service=rs, cost_tracker=tracker,
    )

    # Runner verifies through manager A that the lifecycle (through B) worked.
    runner_view = runner_sm.get(sess.id)
    matching = [r for r in runner_view.runs if r.run_id == "run_shared"]
    assert len(matching) == 1
    assert matching[0].status == "completed"
    assert matching[0].tokens_used == 20
    assert result["session_reconciled"] is True


@pytest.mark.anyio
async def test_run_coordinator_propagates_context_through_stage_aware_provider():
    """Finding 9: the real RunCoordinator execution path must propagate
    stage/run_id through StageAwareProvider to GatewayProvider.

    When ModelManager is active, the orchestrator's provider is
    ``StageAwareProvider(GatewayProvider(...))``.  The coordinator
    (run_coordinator.py:156-159) sets ``_stage``/``_run_id`` via direct
    attribute assignment on the outer wrapper, which does not propagate
    to the inner ``GatewayProvider``.

    This test invokes the **real** ``RunCoordinator.execute_stage_loop`` with
    a minimal fake orchestrator and a real named stage (``gap_analysis``)
    whose ``execute()`` makes exactly one ordinary completion call through
    the provider chain.  The recording inner provider then asserts the
    stage and run_id reached the usage-aware call.

    The coordinator's context-setting lines are NOT reproduced in the test —
    they are executed by the real ``RunCoordinator``.
    """
    from backend.pipeline.execution.run_state import RunCheckpoint
    from backend.pipeline.orchestrator.run_coordinator import RunCoordinator
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import PipelineStage, StageContext
    from backend.pipeline.strategies.models import StageConfig, StrategyConfig
    from backend.providers.stage_context import StageAwareProvider

    # ── Real provider chain: StageAwareProvider(GatewayProvider(LLMGateway, inner)) ──
    inner = _RecordingInnerProvider()
    cap_registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter(default_context=4096)
    gateway = LLMGateway(
        capability_registry=cap_registry, token_budgeter=budgeter,
        default_model=inner.default_model,
    )
    gw_provider = GatewayProvider(gateway, inner_provider=inner, stage="", run_id="")
    stage_aware = StageAwareProvider(gw_provider, model_manager=None)

    # Install the orchestrator's provider callback (production closure shape).
    # After the v1.0.3 gateway-context repair, the callback receives stage and
    # run_id as kwargs from LLMGateway.call().
    async def _provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None, stage="", run_id=None):
        if schema:
            if hasattr(inner, "structured_output_with_usage"):
                resp = await inner.structured_output_with_usage(
                    messages, schema, temperature, stage=stage, run_id=run_id,
                )
                structured = getattr(resp, "structured", None)
                return structured if structured is not None else {}
            return await inner.structured_output(messages, schema, temperature)
        if hasattr(inner, "complete_with_usage"):
            resp = await inner.complete_with_usage(
                messages, temperature, max_tokens, stage=stage, run_id=run_id,
            )
            return resp.content if hasattr(resp, "content") else str(resp)
        return await inner.complete(messages, temperature, max_tokens)

    gateway.set_provider_fn(_provider_fn)

    # ── Minimal fake orchestrator (stubs for unrelated boundaries) ──
    class _StubLifecycle:
        doom_detected = False

        async def post_stage_common(self, *a, **kw):
            pass

        async def post_stage_specific(self, *a, **kw):
            return "continue"

    class _StubCompaction:
        async def prepare_context(self, ctx, stage_name):
            return ctx

    class _StubPersistence:
        def advance_stage(self, *a, **kw):
            pass

        def save_checkpoint(self, *a, **kw):
            pass

    class _StubProcessor:
        def persist_stage_report(self, *a, **kw):
            pass

        async def persist_stage_context(self, *a, **kw):
            pass

    class _StubServices:
        cross_stage_ctx = None
        governance_policy = None

    settings = SimpleNamespace(heartbeat_enabled=False)

    class _FakeOrchestrator:
        """Minimal orchestrator carrying only what execute_stage_loop reads."""

        def __init__(self):
            self._provider = stage_aware
            self._strategy_config = StrategyConfig(
                name="test",
                stages={"gap_analysis": StageConfig(enabled=True)},
            )
            self._strategy_name = "test"
            self._lifecycle = _StubLifecycle()
            self._compaction = _StubCompaction()
            self._persistence = _StubPersistence()
            self._processor = _StubProcessor()
            self._services = _StubServices()
            self._settings = settings
            self._model_manager = None
            self._operation_executor = None
            self._mm_stage_aliases = {}
            self._task_router = None
            self._resolve_user_model = None
            self._should_stop = lambda: False
            self._STAGE_ORDER = ["gap_analysis"]
            self._last_stage_retries = 0

        async def _execute_stage_with_retry(self, stage, ctx, checkpoint):
            return await stage.execute(ctx)

        def _record_stage(self, stage_name, t0):
            pass

    # ── Minimal named stage that calls provider.complete() ──
    class _GapAnalysisTestStage(PipelineStage):
        name = "gap_analysis"

        async def execute(self, ctx: StageContext) -> bool:
            await ctx.provider_override.complete(
                [{"role": "user", "content": "identify gaps"}],
                temperature=0.3, max_tokens=100,
            ) if ctx.provider_override else None
            # If no override, call the orchestrator's provider directly.
            if not ctx.provider_override:
                # The stage accesses the provider via the orchestrator; here
                # we simulate that by calling stage_aware directly.
                await stage_aware.complete(
                    [{"role": "user", "content": "identify gaps"}],
                    temperature=0.3, max_tokens=100,
                )
            return True

    fake_orch = _FakeOrchestrator()
    coordinator = RunCoordinator(fake_orch)

    ctx = StageContext(result=PipelineResult())
    ctx.provider_override = None  # no model-routing override
    result = PipelineResult()
    checkpoint = RunCheckpoint.create_new(
        run_id="run_test", stage_names=["gap_analysis"],
    )

    await coordinator.execute_stage_loop(
        stages=[_GapAnalysisTestStage()],
        ctx=ctx,
        result=result,
        checkpoint=checkpoint,
        run_id="run_test",
        domain="test",
        db_run_id=None,
    )

    # ── Assert: the real coordinator propagated context to the inner provider ──
    assert len(inner.usage_calls) == 1, (
        f"Finding 9: expected exactly one inner usage call. Got {len(inner.usage_calls)}."
    )
    assert inner.usage_calls[0]["stage"] == "gap_analysis", (
        "Finding 9: the real RunCoordinator execution path did not propagate "
        "gap_analysis/run_test through StageAwareProvider to GatewayProvider. "
        "Inner complete_with_usage received blank stage."
    )
    assert inner.usage_calls[0]["run_id"] == "run_test", (
        "Finding 9: inner complete_with_usage received blank/None run_id."
    )
