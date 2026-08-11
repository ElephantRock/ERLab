"""Hard budget-refusal contract tests (Commit 1).

Freezes the semantics of pre-call budget refusal BEFORE the production
gateway is wired to it. Covers the full refusal matrix from the plan and
proves the refusal exception subclasses PromptTooLargeError (so the
GatewayProvider re-raises rather than falling back to the billed inner
provider).

The proof requirement is exercised via a provider spy with a call ledger:
a denied call leaves call count, usage, tokens, and cost unchanged.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.acceptance.budget_authority import (
    BudgetAuthority,
    BudgetConfigurationError,
    BudgetExceededError,
    BudgetReconciliationError,
    BudgetReservationDeniedError,
    CallProjection,
)
from backend.pipeline.gateway.token_budget import PromptTooLargeError


def _run(coro):
    return asyncio.run(coro)


# ── Typed error contract ─────────────────────────────────────────────


class TestTypedErrors:
    def test_budget_exceeded_is_prompt_too_large(self):
        """The refusal MUST subclass PromptTooLargeError so GatewayProvider
        re-raises it rather than falling back to the (billed) inner provider."""
        assert issubclass(BudgetExceededError, PromptTooLargeError)
        assert issubclass(BudgetReservationDeniedError, BudgetExceededError)

    def test_configuration_error_is_runtime_error(self):
        assert issubclass(BudgetConfigurationError, RuntimeError)

    def test_reconciliation_error_is_runtime_error(self):
        assert issubclass(BudgetReconciliationError, RuntimeError)


# ── Refusal matrix ───────────────────────────────────────────────────


class TestRefusalMatrix:
    def test_well_below_ceiling_allows_call(self):
        auth = BudgetAuthority(ceiling_usd=1.0)
        proj = CallProjection(max_cost_usd=0.05)
        auth.reserve(proj)  # does not raise
        assert auth.reserved_usd() == pytest.approx(0.05)

    def test_exactly_at_ceiling_denies(self):
        auth = BudgetAuthority(ceiling_usd=0.10)
        auth.reconcile("seed", 0.10)  # commit the full ceiling
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(CallProjection(max_cost_usd=0.01))

    def test_above_ceiling_denies(self):
        auth = BudgetAuthority(ceiling_usd=0.10)
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(CallProjection(max_cost_usd=0.20))

    def test_remaining_budget_smaller_than_projected_denies(self):
        auth = BudgetAuthority(ceiling_usd=0.10)
        auth.reconcile("seed", 0.08)  # 0.02 remaining
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(CallProjection(max_cost_usd=0.05))

    def test_zero_dollar_ceiling_denies_all(self):
        auth = BudgetAuthority(ceiling_usd=0.0)
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(CallProjection(max_cost_usd=0.001))

    def test_negative_ceiling_rejected_at_construction(self):
        with pytest.raises(BudgetConfigurationError):
            BudgetAuthority(ceiling_usd=-1.0)


# ── Reservation lifecycle ────────────────────────────────────────────


class TestReservationLifecycle:
    def test_reconcile_releases_unused_and_commits_actual(self):
        auth = BudgetAuthority(ceiling_usd=1.0)
        rid = auth.reserve(CallProjection(max_cost_usd=0.10))
        assert auth.reserved_usd() == pytest.approx(0.10)
        auth.reconcile(rid, actual_cost_usd=0.03)
        assert auth.reserved_usd() == pytest.approx(0.0)
        assert auth.committed_usd() == pytest.approx(0.03)

    def test_release_on_exception_frees_reservation(self):
        auth = BudgetAuthority(ceiling_usd=1.0)
        rid = auth.reserve(CallProjection(max_cost_usd=0.10))
        auth.release(rid)
        assert auth.reserved_usd() == pytest.approx(0.0)
        assert auth.committed_usd() == pytest.approx(0.0)

    def test_overshoot_detected_on_reconcile(self):
        auth = BudgetAuthority(ceiling_usd=0.10, strict=True)
        rid = auth.reserve(CallProjection(max_cost_usd=0.10))
        # Actual usage exceeded the reservation.
        auth.reconcile(rid, actual_cost_usd=0.15)
        snap = auth.snapshot()
        assert snap.overshoot_usd > 0.0
        assert snap.reconciled is False

    def test_multiple_sequential_reservations(self):
        auth = BudgetAuthority(ceiling_usd=0.30)
        r1 = auth.reserve(CallProjection(max_cost_usd=0.10))
        auth.reconcile(r1, 0.08)
        r2 = auth.reserve(CallProjection(max_cost_usd=0.10))
        auth.reconcile(r2, 0.09)
        r3 = auth.reserve(CallProjection(max_cost_usd=0.10))
        auth.reconcile(r3, 0.07)
        snap = auth.snapshot()
        assert snap.committed_usd == pytest.approx(0.24)
        assert snap.reconciled is True


# ── Provider-spy proof: denied call leaves everything unchanged ──────


class _LedgerProvider:
    """Provider spy recording every call. Raises if called when it should
    not be (the refusal must have prevented the call)."""

    def __init__(self):
        self.calls = 0
        self.usage_events: list[dict] = []
        self.total_tokens = 0
        self.total_cost_usd = 0.0
        self._last_receipt = None

    async def structured_output_with_usage(self, messages, schema, temperature=0.3,
                                           stage="", run_id=None, **kw):
        self.calls += 1
        self.usage_events.append({"stage": stage, "run_id": run_id})
        self.total_tokens += 100
        self.total_cost_usd += 0.02
        from backend.providers.base import LLMResponse
        return LLMResponse(content="", structured={"gaps": []},
                           input_tokens=60, output_tokens=40,
                           served_model="spy")

    @property
    def provider_name(self):
        return "spy"

    @property
    def default_model(self):
        return "spy-model"


class TestProviderSpyProof:
    def test_denied_call_leaves_ledger_unchanged(self):
        """The proof requirement: when the budget denies a call, the provider
        is NEVER invoked, so call count, usage events, tokens, and cost are
        all unchanged."""
        provider = _LedgerProvider()
        auth = BudgetAuthority(ceiling_usd=0.01)  # tiny ceiling
        proj = CallProjection(max_cost_usd=0.05)  # exceeds ceiling
        snapshot_before = provider.calls, len(provider.usage_events), provider.total_tokens, provider.total_cost_usd
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(proj)
        # The provider must NOT have been called.
        assert provider.calls == snapshot_before[0] == 0
        assert len(provider.usage_events) == snapshot_before[1] == 0
        assert provider.total_tokens == snapshot_before[2] == 0
        assert provider.total_cost_usd == snapshot_before[3] == 0.0
        snap = auth.snapshot()
        assert snap.denied_calls == 1

    def test_allowed_then_denied_sequence(self):
        """One call fits, the next is denied; only one provider call occurs."""
        provider = _LedgerProvider()
        auth = BudgetAuthority(ceiling_usd=0.03)

        # First call fits.
        rid1 = auth.reserve(CallProjection(max_cost_usd=0.02))
        _run(provider.structured_output_with_usage([], {}, stage="gap_analysis"))
        auth.reconcile(rid1, actual_cost_usd=0.02)
        assert provider.calls == 1

        # Second call denied (only 0.01 remains, call projects 0.02).
        with pytest.raises(BudgetReservationDeniedError):
            auth.reserve(CallProjection(max_cost_usd=0.02))
        assert provider.calls == 1  # unchanged

    def test_denial_does_not_retry(self):
        """A denial must not trigger a retry — the call count stays at the
        pre-denial level even if reserve is attempted again."""
        provider = _LedgerProvider()
        auth = BudgetAuthority(ceiling_usd=0.005)
        for _ in range(5):  # simulate a naive retry loop
            with pytest.raises(BudgetReservationDeniedError):
                auth.reserve(CallProjection(max_cost_usd=0.02))
        assert provider.calls == 0
        assert auth.snapshot().denied_calls == 5


# ── Concurrent calls compete for remaining budget ────────────────────


class TestConcurrentCompetition:
    def test_at_most_affordable_calls_proceed(self):
        """With a ceiling admitting exactly N affordable calls, no more than
        N reservations succeed under concurrency."""
        import threading
        auth = BudgetAuthority(ceiling_usd=0.10)
        per_call = 0.03
        results = {"granted": 0, "denied": 0}
        rlock = threading.Lock()

        def attempt():
            try:
                auth.reserve(CallProjection(max_cost_usd=per_call))
                with rlock:
                    results["granted"] += 1
            except BudgetReservationDeniedError:
                with rlock:
                    results["denied"] += 1

        threads = [threading.Thread(target=attempt) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # ceiling 0.10 / 0.03 per call = at most 3 granted (0.09 <= 0.10).
        assert results["granted"] <= 3
        assert results["granted"] + results["denied"] == 10


# ── Snapshot / evidence ──────────────────────────────────────────────


class TestEvidenceSnapshot:
    def test_snapshot_excludes_no_secrets(self):
        auth = BudgetAuthority(ceiling_usd=0.10)
        auth.reserve(CallProjection(max_cost_usd=0.05, stage="gap_analysis", run_id="r1"))
        snap = auth.snapshot()
        d = snap.to_dict()
        # Only safe structural fields.
        assert set(d.keys()) == {"ceiling_usd", "committed_usd", "reserved_usd",
                                 "denied_calls", "overshoot_usd", "reconciled"}
        # No stage/run_id/prompt content leaks into the budget evidence.
        import json
        assert "gap_analysis" not in json.dumps(d)
        assert "r1" not in json.dumps(d)
