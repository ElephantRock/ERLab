"""Gateway-bound budget enforcement integration tests (Commit 2).

Proves the hard budget authority is wired into the production
LLMGateway.call() boundary — the single chokepoint covering every
billable call. Exercises the real gateway with a budget authority and a
provider spy, proving:
- an allowed call proceeds and is reconciled;
- a refused call never reaches the provider (ledger unchanged);
- the refusal propagates as a PromptTooLargeError subclass so
  GatewayProvider re-raises rather than billing via the inner fallback;
- reservation is released on provider exception.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.acceptance.budget_authority import (
    BudgetAuthority,
    BudgetExceededError,
)
from backend.pipeline.gateway.capability_registry import (
    ModelCapabilities,
    ModelCapabilityRegistry,
)
from backend.pipeline.gateway.gateway import LLMGateway
from backend.pipeline.gateway.token_budget import (
    PromptTooLargeError,
    TokenBudgeter,
)


def _run(coro):
    return asyncio.run(coro)


class _RecordingInner:
    """Inner provider fn recording every call and returning token usage."""

    def __init__(self):
        self.calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.served_model = "spy-model"

    async def __call__(self, *, messages, temperature, max_tokens,
                       schema=None, tools=None, stage="", run_id=None, **kw):
        self.calls += 1
        in_tok = 60
        out_tok = 40
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        if schema is not None:
            return {"gaps": []}
        return "spy response"


def _make_gateway(authority: BudgetAuthority | None = None) -> tuple[LLMGateway, _RecordingInner]:
    registry = ModelCapabilityRegistry()
    # Register a model with a large context window so the token-budget
    # pre-flight never trips (we are testing the MONEY budget, not tokens).
    try:
        caps = ModelCapabilities(
            model_id="spy-model", provider="spy",
            context_window=200000, max_output_tokens=8192,
            input_cost_per_1k=0.5, output_cost_per_1k=1.5,
        )
        registry.register(caps)
    except Exception:
        pass
    budgeter = TokenBudgeter(default_context=200000)
    gateway = LLMGateway(registry, budgeter, default_model="spy-model")
    inner = _RecordingInner()

    async def _provider_fn(*, messages, temperature, max_tokens, schema=None,
                           tools=None, stage="", run_id=None, **kw):
        return await inner(messages=messages, temperature=temperature,
                           max_tokens=max_tokens, schema=schema, tools=tools,
                           stage=stage, run_id=run_id)

    gateway.set_provider_fn(_provider_fn)
    if authority is not None:
        gateway.set_budget_authority(authority)
    return gateway, inner


def _request(schema=None):
    from backend.pipeline.gateway.gateway import LLMRequest
    return LLMRequest(
        task="gap_analysis", stage="gap_analysis",
        messages=[{"role": "user", "content": "identify gaps"}],
        max_output_tokens=100,
        schema=schema,
    )


class TestGatewayBudgetEnforcement:
    def test_allowed_call_proceeds_and_reconciles(self):
        auth = BudgetAuthority(
            ceiling_usd=1.0, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gateway, inner = _make_gateway(auth)
        _run(gateway.call(_request()))
        assert inner.calls == 1
        # The reservation was reconciled: reserved returns to ~0.
        assert auth.reserved_usd() == pytest.approx(0.0)
        # Committed reflects the actual call cost.
        assert auth.committed_usd() > 0.0
        assert auth.snapshot().denied_calls == 0

    def test_refused_call_never_reaches_provider(self):
        # Tiny ceiling; with pricing, the projection (100 in + 100 out tokens)
        # costs 0.05 + 0.15 = 0.20, exceeding the 0.01 ceiling.
        auth = BudgetAuthority(
            ceiling_usd=0.01, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gateway, inner = _make_gateway(auth)
        with pytest.raises(BudgetExceededError):
            _run(gateway.call(_request()))
        # The provider was NEVER called.
        assert inner.calls == 0
        assert inner.total_input_tokens == 0
        assert auth.snapshot().denied_calls == 1
        # No cost committed for a refused call.
        assert auth.committed_usd() == pytest.approx(0.0)

    def test_refusal_is_prompt_too_large_subclass(self):
        """Critical: the refusal MUST be a PromptTooLargeError so the
        GatewayProvider re-raises rather than falling back to the inner
        provider (which would bill)."""
        auth = BudgetAuthority(
            ceiling_usd=0.001, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gateway, inner = _make_gateway(auth)
        with pytest.raises(PromptTooLargeError):
            _run(gateway.call(_request()))

    def test_second_call_denied_after_budget_exhausted(self):
        auth = BudgetAuthority(
            ceiling_usd=0.05, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gateway, inner = _make_gateway(auth)
        # First call: projection 100in/100out = 0.20 > 0.05 ceiling → denied.
        # Use a smaller request to fit.
        from backend.pipeline.gateway.gateway import LLMRequest
        small = LLMRequest(
            task="t", stage="t", messages=[{"role": "user", "content": "x"}],
            max_output_tokens=10,
        )
        # projection: ~1 in token + 10 out = 0.0005 + 0.015 = 0.0155 <= 0.05 ✓
        _run(gateway.call(small))
        assert inner.calls == 1
        # Second call: same size, but now committed ~0.006 (60in/40out actual)
        # + reserved 0.0155 → total ~0.0215; another 0.0155 → 0.037 <= 0.05 ✓
        _run(gateway.call(small))
        assert inner.calls == 2
        # Third call should now be near/over ceiling → denied.
        # (Exact threshold depends on actual reconciled cost; assert at least
        # that denial eventually happens by tightening.)
        auth3 = BudgetAuthority(
            ceiling_usd=0.02, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gw3, inner3 = _make_gateway(auth3)
        _run(gw3.call(small))  # fits once
        with pytest.raises(BudgetExceededError):
            _run(gw3.call(small))  # second denied
        assert inner3.calls == 1

    def test_reservation_released_on_provider_exception(self):
        auth = BudgetAuthority(
            ceiling_usd=1.0, price_per_1k_input=0.5, price_per_1k_output=1.5,
        )
        gateway, inner = _make_gateway(auth)

        # Replace the provider fn with one that raises.
        async def _failing(*a, **kw):
            raise RuntimeError("provider transport down")

        gateway.set_provider_fn(_failing)
        # Q2: the gateway preserves transport-failure identity — it
        # raises GatewayTransportError (no success-shaped degraded
        # response) and MUST still release the reservation.
        from backend.pipeline.gateway.transport import GatewayTransportError
        with pytest.raises(GatewayTransportError, match="transport down"):
            _run(gateway.call(_request()))
        # Reservation released: reserved returns to ~0.
        assert auth.reserved_usd() == pytest.approx(0.0)
        # Nothing committed because the call failed.
        assert auth.committed_usd() == pytest.approx(0.0)

    def test_no_authority_means_no_enforcement(self):
        # Legacy behavior: without an authority, calls proceed unconstrained.
        gateway, inner = _make_gateway(authority=None)
        _run(gateway.call(_request()))
        assert inner.calls == 1
