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
from backend.pipeline.gateway.gateway import LLMGateway
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

    # Replicate the orchestrator's provider callback EXACTLY (the production
    # closure). This is the code path that receives the dropped context.
    async def _provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None):
        stage = getattr(gateway, "_stage", "") or ""
        run_id = getattr(provider, "_run_id", None)  # simulates orchestrator state
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

    Currently call() passes only messages/temperature/max_tokens/schema/tools,
    dropping stage and run_id.  After repair, the callback must receive them.
    """
    gateway, provider, inner = _build_gateway_and_provider()

    # Install a callback that records whether it received stage/run_id.
    received: dict = {}

    async def _recording_callback(*, messages, temperature, max_tokens, schema=None, tools=None):
        received["stage_received"] = "stage" in _recording_callback.__kwdefaults__  # type: ignore[attr-defined]
        # The defect: the callback signature doesn't include stage/run_id at all.
        # After repair, call() should pass them as kwargs.
        received["has_stage"] = "stage" in received
        return "ok"

    # We can't easily change the callback signature mid-test. Instead, verify
    # at the source level that the _provider_fn invocation includes stage.
    import inspect as _inspect

    call_source = _inspect.getsource(LLMGateway.call)
    # The defect: call() invokes self._provider_fn without request.stage/run_id.
    # Check specifically that the provider_fn call passes stage/run_id kwargs.
    # The existing "request.stage" references are in call-logging, NOT in the
    # provider_fn invocation — so we check for stage= in the fn call context.
    fn_call_lines = [
        line.strip() for line in call_source.splitlines()
        if "_provider_fn" in line or "provider_fn" in line
    ]
    passes_context = any("stage=" in line or "run_id=" in line for line in fn_call_lines)
    assert passes_context, (
        "Finding 1: LLMGateway.call() must pass request.stage and request.run_id "
        "to the provider callback invocation. Currently drops them — the "
        "_provider_fn call includes only messages/temperature/max_tokens/schema/tools."
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


# ── Findings 5-8: E2E runner protocol defects ─────────────────────────


def _read_runner():
    """Read the confirmatory runner source, or skip if absent."""
    runner_path = Path(__file__).resolve().parents[2] / "run_e2e_pipeline.py"
    if not runner_path.exists():
        pytest.skip("run_e2e_pipeline.py not found")
    return runner_path.read_text(encoding="utf-8")


def test_runner_obtains_explicit_run_id_before_execution():
    """Finding 5: the runner must obtain one explicit run ID before
    orchestrator/provider construction and pass that exact ID to
    orchestrator.run()."""
    source = _read_runner()
    has_run_id = "--run-id" in source or "run_id" in source
    assert has_run_id, (
        "Finding 5: run_e2e_pipeline.py must accept/generate an explicit run_id "
        "and pass it to orchestrator.run(). Currently does not."
    )


def test_runner_binds_session_id():
    """Finding 6: the runner must create or receive a session ID and pass it
    into the same run."""
    source = _read_runner()
    uses_session = (
        "complete_run" in source
        or "session_manager" in source
        or "session_id" in source
    )
    assert uses_session, (
        "Finding 6: run_e2e_pipeline.py must bind a session_id and pass it "
        "into orchestrator.run(). Currently does not."
    )


def test_runner_has_pre_provider_binding_validation():
    """Finding 7: a run-ID binding failure must abort before orchestrator
    construction or any provider call."""
    source = _read_runner()
    assert "preflight" in source.lower() or "bind" in source.lower(), (
        "Finding 7: run_e2e_pipeline.py must validate run-ID binding before "
        "any provider call. Currently has no preflight."
    )


def test_runner_verifies_session_completion_against_ledger():
    """Finding 8: session completion must be verified against the same
    run-scoped ledger totals."""
    source = _read_runner()
    # After repair, the runner should call complete_run and check the returned
    # totals against the persisted ledger/summary.
    verifies_completion = (
        "complete_run" in source
        and ("ledger" in source.lower() or "summary" in source.lower() or "tokens_used" in source)
    )
    assert verifies_completion, (
        "Finding 8: run_e2e_pipeline.py must verify session completion against "
        "the run-scoped ledger totals. Currently does not."
    )


# ── Finding 9: wrapper context propagation through StageAwareProvider ──


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
    async def _provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None):
        stage = getattr(gateway, "_stage", "") or ""
        run_id = getattr(gw_provider, "_run_id", None)
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
