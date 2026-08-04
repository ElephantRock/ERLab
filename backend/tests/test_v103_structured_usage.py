"""Focused behavioral verification for Commit 5 — structured provider usage.

These tests exercise the runtime behavior introduced by Commit 5 (not the
frozen source-string contracts in test_v103_release_reconciliation.py):

* the gateway schema branch issues exactly one provider request via the
  usage-aware structured boundary;
* stage and run_id are preserved into that call;
* the structured payload returned to the gateway caller is unchanged;
* an authoritative usage receipt produces exactly one cost event;
* a usage response with no authoritative receipt marks the run partial;
* the partial-accounting flag is run-scoped — run B's gap never taints run A.

The orchestrator-level test exercises the REAL production closure installed by
``PipelineOrchestrator.__init__`` (via ``gateway.call``), not a replica.

No external provider calls are made.
"""
from __future__ import annotations

import json

import pytest

from backend.pipeline.gateway.gateway import LLMRequest
from backend.pipeline.persistence import PipelinePersistence
from backend.providers.base import LLMProvider, LLMResponse
from backend.providers.provider_factory import CostTracker


class _UsageProviderDouble(LLMProvider):
    """Minimal provider double that records every structured-usage call.

    Tracks call_count so tests assert exactly-one-request semantics, and
    captures the stage/run_id the orchestrator closure threaded through.
    """

    provider_name = "test"
    default_model = "test-model"

    def __init__(self, *, structured_payload, input_tokens=10, output_tokens=5):
        super().__init__()
        self._payload = structured_payload
        self._inp = input_tokens
        self._out = output_tokens
        self.structured_call_count = 0
        self.last_structured_call: dict | None = None

    # --- LLMProvider abstract surface (only what the gateway schema path hits) ---
    async def complete(self, messages, temperature=0.7, max_tokens=4096):
        return ""

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        if False:  # pragma: no cover - generator
            yield ""

    async def structured_output(self, messages, schema, temperature=0.3, max_tokens=4096):
        return self._payload

    async def structured_output_with_usage(
        self, messages, schema, temperature=0.3, stage="", run_id=None,
    ):
        self.structured_call_count += 1
        self.last_structured_call = {
            "messages": messages,
            "schema": schema,
            "temperature": temperature,
            "stage": stage,
            "run_id": run_id,
        }
        if self._cost_callback is not None:
            from backend.providers.base import CostEvent

            self._cost_callback(CostEvent(
                provider="test", model="test-model",
                input_tokens=self._inp, output_tokens=self._out,
                stage=stage, run_id=run_id,
            ))
        return LLMResponse(
            content="",
            structured=self._payload,
            input_tokens=self._inp,
            output_tokens=self._out,
        )

    async def complete_with_usage(self, messages, temperature=0.7, max_tokens=4096, stage="", run_id=None):
        return LLMResponse(content="", input_tokens=0, output_tokens=0)


def _build_orchestrator(provider):
    """Construct a real PipelineOrchestrator wired to the fake provider.

    Mirrors what test_b_cost_01_orchestrator_creates_cost_tracker does. The
    orchestrator's __init__ installs the gateway provider closure; we then
    exercise it through gateway.call() — the actual production code path.
    """
    from backend.config import get_settings
    from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator

    return PipelineOrchestrator(provider=provider, settings=get_settings())


@pytest.mark.anyio
async def test_real_gateway_schema_call_uses_usage_path_exactly_once():
    """The production closure issues exactly one structured_output_with_usage."""
    provider = _UsageProviderDouble(structured_payload={"answer": 42})
    orch = _build_orchestrator(provider)
    request = LLMRequest(
        task="gap_analysis",
        messages=[{"role": "user", "content": "q"}],
        schema={"type": "object"},
        temperature=0.3,
    )
    response = await orch._gateway.call(request)
    assert provider.structured_call_count == 1
    # The structured payload is returned to the gateway caller.
    assert response.content == {"answer": 42}


@pytest.mark.anyio
async def test_real_gateway_preserves_stage_and_run_id():
    """Stage/run_id from the gateway context thread into the usage call."""
    provider = _UsageProviderDouble(structured_payload={"k": 1})
    orch = _build_orchestrator(provider)
    orch._gateway._stage = "idea_generation"
    orch._current_run_id = "run_42"
    request = LLMRequest(
        task="idea_generation",
        messages=[{"role": "user", "content": "q"}],
        schema={"type": "object"},
        temperature=0.2,
    )
    await orch._gateway.call(request)
    assert provider.last_structured_call["stage"] == "idea_generation"
    assert provider.last_structured_call["run_id"] == "run_42"
    assert provider.last_structured_call["temperature"] == 0.2


@pytest.mark.anyio
async def test_real_gateway_returns_structured_payload_unchanged():
    """The structured dict returned through the gateway is the provider payload."""
    payload = {"title": "x", "steps": [1, 2, 3], "nested": {"a": True}}
    provider = _UsageProviderDouble(structured_payload=payload)
    orch = _build_orchestrator(provider)
    request = LLMRequest(
        task="t", messages=[{"role": "user", "content": "q"}],
        schema={"type": "object"}, temperature=0.3,
    )
    response = await orch._gateway.call(request)
    assert json.loads(json.dumps(response.content)) == json.loads(json.dumps(payload))


@pytest.mark.anyio
async def test_authoritative_usage_produces_one_cost_event():
    """An authoritative usage receipt fires exactly one cost event on the tracker."""
    provider = _UsageProviderDouble(
        structured_payload={"a": 1}, input_tokens=100, output_tokens=50,
    )
    orch = _build_orchestrator(provider)
    # The registry normally wires provider.set_cost_callback(tracker.record)
    # inside registry.create(); since the provider is injected directly here,
    # wire it the same way against the orchestrator's tracker.
    provider._cost_callback = orch._cost_tracker.record
    orch._current_run_id = "run_a"
    request = LLMRequest(
        task="t", messages=[{"role": "user", "content": "q"}],
        schema={"type": "object"}, temperature=0.3,
    )
    await orch._gateway.call(request)
    summary = orch._cost_tracker.summary(run_id="run_a")
    assert summary["event_count"] == 1
    assert summary["total_tokens"] == 150
    assert not orch._cost_tracker.is_accounting_partial("run_a")


def test_missing_usage_marks_run_partial(tmp_path):
    """A run with a known unaccounted call is partial even if another run has events."""
    from backend.providers.base import CostEvent

    tracker = CostTracker()
    # An unrelated event from a DIFFERENT run must not prove reconciliation.
    tracker.record(CostEvent(
        provider="openai", model="m", input_tokens=999, output_tokens=999,
        stage="other", run_id="run_other",
    ))
    tracker.mark_accounting_partial("run_partial", "no authoritative token receipt")

    persistence = PipelinePersistence()
    persistence.persist_cost_ledger(
        run_id="run_partial", tracker=tracker,
        cost_persist_dir=str(tmp_path), cost_cap_usd=100.0,
    )
    summary = json.loads((tmp_path / "run_partial_cost_summary.json").read_text(encoding="utf-8"))
    assert summary["reconciliation_status"] == "partial"
    assert summary["record_count"] == 0


def test_partial_flag_is_run_scoped():
    """Marking run B partial must never taint run A's posture."""
    tracker = CostTracker()
    tracker.mark_accounting_partial("run_b", "gap in run b")
    assert tracker.is_accounting_partial("run_b") is True
    assert tracker.is_accounting_partial("run_a") is False
    assert tracker.is_accounting_partial(None) is False


def test_events_from_another_run_do_not_affect_posture(tmp_path):
    """A run with its own events and no gap reconciles; another run's gap is isolated."""
    from backend.providers.base import CostEvent

    tracker = CostTracker()
    tracker.record(CostEvent(
        provider="openai", model="m", input_tokens=10, output_tokens=5,
        stage="s", run_id="run_a",
    ))
    tracker.mark_accounting_partial("run_b", "gap")
    tracker.record(CostEvent(
        provider="openai", model="m", input_tokens=1, output_tokens=1,
        stage="s", run_id="run_b",
    ))

    persistence = PipelinePersistence()
    persistence.persist_cost_ledger(
        run_id="run_a", tracker=tracker, cost_persist_dir=str(tmp_path), cost_cap_usd=100.0,
    )
    persistence.persist_cost_ledger(
        run_id="run_b", tracker=tracker, cost_persist_dir=str(tmp_path), cost_cap_usd=100.0,
    )
    summary_a = json.loads((tmp_path / "run_a_cost_summary.json").read_text(encoding="utf-8"))
    summary_b = json.loads((tmp_path / "run_b_cost_summary.json").read_text(encoding="utf-8"))
    assert summary_a["reconciliation_status"] == "reconciled"
    assert summary_a["record_count"] == 1
    assert summary_b["reconciliation_status"] == "partial"
    assert summary_b["record_count"] == 1
