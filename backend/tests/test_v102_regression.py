uation_provider) + the
    evaluator's internal resolution attempt. In a configured environment,
    resolve_evaluation_provider(None) returns a real provider.
    """
    from backend.pipeline.evaluation.proposal_evaluator import (
        resolve_evaluation_provider,
    )
    resolved = resolve_evaluation_provider(None)
    assert resolved is not None, (
        "B-EVAL-01: resolve_evaluation_provider(None) returned None in a "
        "configured environment — the paper-eval call site would silently "
        "persist zeros"
    )
    assert hasattr(resolved, "complete"), "resolved provider has no complete()"


@pytest.mark.anyio
async def test_b_eval_01_paper_eval_resolves_configured_provider_when_none_passed():
    """After the fix, the paper-evaluation path must resolve a configured
    thinking provider when self._provider is None (mirroring the proposal-eval
    call site at stages.py:3653 which uses get_thinking_provider() fallback).

    This test verifies the call-site resolution helper exists and returns a
    usable provider, so the evaluator is never constructed with None when a
    provider is available.
    """
    from backend.pipeline.evaluation.proposal_evaluator import (
        resolve_evaluation_provider,
    )

    # When called with None, must fall back to the configured thinking provider.
    provider = resolve_evaluation_provider(provider=None)
    assert provider is not None, (
        "B-EVAL-01: resolve_evaluation_provider(None) returned None even though "
        "a cloud provider is configured — the paper-eval call site would "
        "construct ProposalEvaluator(None) and silently persist zeros"
    )
    assert hasattr(provider, "complete"), "resolved provider has no complete()"


# ── Commit 7: durable cost-ledger persistence (B-COST-01) ─────────────────


@pytest.mark.anyio
async def test_b_cost_01_cost_tracker_persists_durable_ledger(tmp_path):
    """After a run reaches terminal state, the CostTracker's captured events
    must be durably persisted to a JSONL ledger with a reconciled run summary.

    On the current branch (pre-Commit-7), CostTracker is in-memory only —
    the confirmatory run (run_c600518856d2) made 88 cloud calls but left
    zero cost files. This test verifies the persistence path exists and
    writes records + summary.
    """
    import json
    from backend.providers.provider_factory import CostTracker
    from backend.providers.base import CostEvent
    from datetime import datetime, timezone

    tracker = CostTracker()
    # Simulate two captured usage events
    tracker.record(CostEvent(
        provider="openai", model="glm-4.6", input_tokens=100, output_tokens=50,
        stage="proposal_synthesis", run_id="run_test",
    ))
    tracker.record(CostEvent(
        provider="openai", model="glm-4.6", input_tokens=200, output_tokens=100,
        stage="evaluation", run_id="run_test",
    ))

    ledger_path = tmp_path / "costs" / "run_test_cost_ledger.jsonl"
    summary_path = tmp_path / "costs" / "run_test_cost_summary.json"

    # The persistence method must exist and write both files.
    from backend.pipeline.persistence import PipelinePersistence
    persistence = PipelinePersistence()
    persistence.persist_cost_ledger(
        run_id="run_test",
        tracker=tracker,
        cost_persist_dir=str(tmp_path / "costs"),
        cost_cap_usd=100.0,
    )

    assert ledger_path.exists(), "cost ledger JSONL was not persisted"
    assert summary_path.exists(), "cost summary JSON was not persisted"

    # Ledger: every event durably stored
    lines = ledger_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2, f"expected 2 ledger entries, got {len(lines)}"
    entry0 = json.loads(lines[0])
    assert entry0["provider"] == "openai"
    assert entry0["model"] == "glm-4.6"
    assert entry0["stage"] == "proposal_synthesis"
    assert entry0["run_id"] == "run_test"
    assert "input_tokens" in entry0 and "output_tokens" in entry0
    assert "cost_usd" in entry0

    # Summary: reconciled totals + cap comparison
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["record_count"] == 2
    assert summary["total_input_tokens"] == 300
    assert summary["total_output_tokens"] == 150
    assert summary["total_tokens"] == 450
    assert summary["total_cost_usd"] >= 0.0
    assert summary["cost_cap_usd"] == 100.0
    assert summary["within_cap"] is True
    assert summary["run_id"] == "run_test"
    # No credentials in artifacts
    ledger_text = ledger_path.read_text(encoding="utf-8") + summary_path.read_text(encoding="utf-8")
    assert "api_key" not in ledger_text.lower() or "sk-" not in ledger_text


def test_b_cost_01_cost_tracker_summary_reconciles():
    """The summary's totals must equal the sum of persisted records."""
    from backend.providers.provider_factory import CostTracker
    from backend.providers.base import CostEvent

    tracker = CostTracker()
    for i in range(5):
        tracker.record(CostEvent(
            provider="openai", model="glm-4.6",
            input_tokens=10 * (i + 1), output_tokens=5 * (i + 1),
            stage=f"stage_{i}", run_id="run_recon",
        ))
    summary = tracker.summary()
    # Sum of records must match summary
    assert summary["event_count"] == 5
    assert summary["total_input_tokens"] == 10 + 20 + 30 + 40 + 50
    assert summary["total_output_tokens"] == 5 + 10 + 15 + 20 + 25


# ── Commit 8: cost-tracker registry wiring (B-COST-01) ─────────────────────


@pytest.mark.anyio
async def test_b_cost_01_orchestrator_wires_cost_tracker_to_provider():
    """The orchestrator must register a CostTracker with the provider factory
    BEFORE creating the provider, so that complete_with_usage fires cost
    callbacks. On the current branch, the orchestrator reads
    self._registry.cost_tracker (which is None) but never creates one or
    registers it, so 0 cost events fire in the live pipeline.

    This test verifies the wiring exists: after orchestrator-equivalent init,
    a complete_with_usage call on the production provider fires a cost event.
    """
    from backend.providers.provider_factory import get_registry, CostTracker
    from backend.config import get_settings

    registry = get_registry()

    # Simulate what the orchestrator SHOULD do (and will after the fix):
    # create a CostTracker and register it before creating the provider.
    tracker = CostTracker()
    registry.set_cost_tracker(tracker)
    provider = registry.create(settings=get_settings())

    # Verify the callback propagated to the inner provider
    assert tracker is not None
    assert hasattr(provider, "complete_with_usage")

    # One call through the usage-enabled path
    resp = await provider.complete_with_usage(
        [{"role": "user", "content": "Say hello"}],
        max_tokens=10, stage="test", run_id="run_test",
    )

    summary = tracker.summary()
    assert summary["event_count"] >= 1, (
        f"B-COST-01 registry wiring: expected >=1 cost event, got {summary['event_count']}. "
        f"The cost tracker was not wired to the provider before creation."
    )


def test_b_cost_01_orchestrator_creates_cost_tracker():
    """The orchestrator must create and wire a CostTracker to the provider
    registry before creating the provider, so cost callbacks fire on every
    complete_with_usage call. On the current branch, the orchestrator reads
    self._registry.cost_tracker (which is None because it never creates one)
    — this test verifies the tracker is non-None after orchestrator init.
    """
    import sys
    from pathlib import Path

    # Adjust PYTHONPATH to recognize the 'backend' package
    sys.path.insert(0, str(Path(__file__).parent.parent))

    from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator
    from backend.config import get_settings

    orch = PipelineOrchestrator(settings=get_settings())
    assert orch._cost_tracker is not None, (
        "B-COST-01: orchestrator._cost_tracker is None — no CostTracker was "
        "created or wired to the provider factory. Cost events will never fire."
    )
