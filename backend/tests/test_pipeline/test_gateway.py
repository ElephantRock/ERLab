"""Tests for the LLM gateway control plane.

Covers: TokenBudgeter, ModelCapabilityRegistry, LLMGateway, GatewayProvider.
"""

import asyncio
import pytest

from backend.pipeline.gateway.token_budget import (
    TokenBudget, TokenBudgeter, PromptTooLargeError,
)
from backend.pipeline.gateway.capability_registry import (
    ModelCapabilities, ModelCapabilityRegistry,
)
from backend.pipeline.gateway.gateway import LLMGateway, LLMRequest, LLMResponse
from backend.pipeline.gateway.gateway_provider import GatewayProvider


# ── TokenBudget ──────────────────────────────────────────────────────────────

class TestTokenBudget:
    def test_fits_when_within_budget(self):
        b = TokenBudget(input_tokens=3000, output_reserve=1000, context_window=8192)
        assert b.fits is True
        assert b.overflow_tokens == 0

    def test_does_not_fit_when_over(self):
        b = TokenBudget(input_tokens=7000, output_reserve=2000, context_window=8192)
        assert b.fits is False
        assert b.overflow_tokens > 0

    def test_safety_margin_reduces_usable_budget(self):
        b = TokenBudget(input_tokens=6000, output_reserve=1000, context_window=8192, safety_margin=0.15)
        # Total budget = 8192 * 0.85 = 6963
        # Input + output = 7000 > 6963 → doesn't fit
        assert b.fits is False

    def test_available_for_input(self):
        b = TokenBudget(input_tokens=3000, output_reserve=2000, context_window=8192)
        # Total budget = 8192 * 0.85 = 6963
        # Available for input = 6963 - 2000 = 4963
        assert b.available_for_input == 4963

    def test_available_for_output(self):
        b = TokenBudget(input_tokens=3000, output_reserve=2000, context_window=8192)
        # Total budget = 8192 * 0.85 = 6963
        # Available for output = 6963 - 3000 = 3963
        assert b.available_for_output == 3963

    def test_summary_ok(self):
        b = TokenBudget(input_tokens=1000, output_reserve=1000, context_window=8192)
        assert "[OK]" in b.summary()

    def test_summary_overflow(self):
        b = TokenBudget(input_tokens=8000, output_reserve=2000, context_window=8192)
        assert "[OVERFLOW]" in b.summary()


# ── TokenBudgeter ────────────────────────────────────────────────────────────

class TestTokenBudgeter:
    def test_count_tokens_short_text(self):
        b = TokenBudgeter()
        count = b.count_tokens([{"role": "user", "content": "Hello world"}])
        assert count.total_tokens > 0
        assert count.total_tokens < 20

    def test_count_tokens_long_text(self):
        b = TokenBudgeter()
        long_text = "word " * 1000  # ~5000 chars
        count = b.count_tokens([{"role": "user", "content": long_text}])
        # Should be roughly 5000/3.8 ≈ 1316 tokens
        assert 1000 < count.total_tokens < 1500

    def test_check_fits(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "short prompt"}]
        budget = b.check(messages, max_output_tokens=100, context_window=4096)
        assert budget.fits is True

    def test_check_does_not_fit(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "x" * 20000}]  # ~5263 tokens
        budget = b.check(messages, max_output_tokens=2000, context_window=4096)
        assert budget.fits is False
        assert budget.overflow_tokens > 0

    def test_check_or_raise_fits(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "short"}]
        budget = b.check_or_raise(messages, max_output_tokens=100, context_window=4096)
        assert budget.fits is True

    def test_check_or_raise_raises(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "x" * 20000}]
        with pytest.raises(PromptTooLargeError) as exc_info:
            b.check_or_raise(messages, max_output_tokens=2000, context_window=4096)
        assert exc_info.value.input_tokens > 0
        assert exc_info.value.available >= 0

    def test_recommend_max_output(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "short"}]
        recommended = b.recommend_max_output(messages, context_window=8192)
        # Should be large (most of the context is available)
        assert recommended > 6000

    def test_recommend_max_output_too_large(self):
        b = TokenBudgeter()
        messages = [{"role": "user", "content": "x" * 40000}]  # ~10526 tokens
        recommended = b.recommend_max_output(messages, context_window=4096)
        # Prompt alone exceeds context, should return 0
        assert recommended == 0


# ── ModelCapabilityRegistry ─────────────────────────────────────────────────

class TestModelCapabilityRegistry:
    def test_static_defaults_loaded(self):
        reg = ModelCapabilityRegistry()
        caps = reg.get("qwen/qwen3-4b-2507")
        assert caps.provider == "lmstudio"
        assert caps.context_window > 0

    def test_unknown_model_returns_conservative(self):
        reg = ModelCapabilityRegistry()
        caps = reg.get("totally-unknown-model")
        assert caps.context_window == 4096  # conservative default
        assert caps.provider == "unknown"

    def test_prefix_match(self):
        reg = ModelCapabilityRegistry()
        # Instance with colon should match base model
        caps = reg.get("qwen/qwen3-4b-2507:2")
        assert caps.provider == "lmstudio"

    def test_can_handle(self):
        caps = ModelCapabilities(
            model_id="test", provider="test", context_window=8192, safe_input_tokens=5734,
        )
        assert caps.can_handle(input_tokens=4000, output_tokens=2000) is True  # 6000 < 6963
        assert caps.can_handle(input_tokens=6000, output_tokens=2000) is False  # 8000 > 6963

    def test_get_for_role(self):
        reg = ModelCapabilityRegistry()
        draft_models = reg.get_for_role("draft")
        assert len(draft_models) > 0
        for m in draft_models:
            assert "draft" in m.roles

    def test_get_for_role_with_min_context(self):
        reg = ModelCapabilityRegistry()
        # Request high context — only larger models should match
        large_models = reg.get_for_role("synthesize", min_context=10000)
        for m in large_models:
            assert m.context_window >= 10000

    def test_list_models(self):
        reg = ModelCapabilityRegistry()
        models = reg.list_models()
        assert len(models) > 0
        assert all("model_id" in m for m in models)


# ── LLMGateway ──────────────────────────────────────────────────────────────

class TestLLMGateway:
    def _make_gateway(self):
        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter(default_context=4096)
        gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
        return gateway

    @pytest.mark.asyncio
    async def test_basic_call(self):
        gateway = self._make_gateway()

        async def mock_provider(**kw):
            return "test response"

        gateway.set_provider_fn(mock_provider)

        response = await gateway.call(LLMRequest(
            task="test",
            messages=[{"role": "user", "content": "hello"}],
            max_output_tokens=100,
        ))

        assert response.content == "test response"
        assert response.confidence > 0
        assert len(gateway.get_call_log()) == 1

    @pytest.mark.asyncio
    async def test_oversized_prompt_fails(self):
        gateway = self._make_gateway()

        async def mock_provider(**kw):
            return "should not reach"

        gateway.set_provider_fn(mock_provider)

        with pytest.raises(PromptTooLargeError):
            await gateway.call(LLMRequest(
                task="test",
                messages=[{"role": "user", "content": "x" * 20000}],
                max_output_tokens=2000,
                context_window_override=4096,
            ))

    @pytest.mark.asyncio
    async def test_call_logging(self):
        gateway = self._make_gateway()

        async def mock_provider(**kw):
            return "response"

        gateway.set_provider_fn(mock_provider)

        await gateway.call(LLMRequest(
            task="test_task",
            messages=[{"role": "user", "content": "hello"}],
            max_output_tokens=100,
            stage="test_stage",
            run_id="run_123",
        ))

        log = gateway.get_call_log()
        assert len(log) == 1
        assert log[0]["task"] == "test_task"
        assert log[0]["stage"] == "test_stage"
        assert log[0]["run_id"] == "run_123"

    @pytest.mark.asyncio
    async def test_degraded_on_provider_failure(self):
        gateway = self._make_gateway()

        async def failing_provider(**kw):
            raise RuntimeError("provider down")

        gateway.set_provider_fn(failing_provider)

        response = await gateway.call(LLMRequest(
            task="test",
            messages=[{"role": "user", "content": "hello"}],
            max_output_tokens=100,
        ))

        assert response.degraded is True
        assert response.confidence == 0.0
        assert len(response.warnings) > 0

    @pytest.mark.asyncio
    async def test_validation_warnings(self):
        gateway = self._make_gateway()

        async def empty_provider(**kw):
            return ""

        gateway.set_provider_fn(empty_provider)

        response = await gateway.call(LLMRequest(
            task="test",
            messages=[{"role": "user", "content": "hello"}],
            max_output_tokens=100,
        ))

        assert "Empty output" in response.warnings[0]
        assert response.confidence < 1.0

    @pytest.mark.asyncio
    async def test_structured_output_missing_field(self):
        gateway = self._make_gateway()

        async def partial_provider(**kw):
            return {"field_a": "value"}  # missing field_b

        gateway.set_provider_fn(partial_provider)

        schema = {
            "required": ["field_a", "field_b"],
            "properties": {"field_a": {}, "field_b": {}},
        }

        response = await gateway.call(LLMRequest(
            task="test",
            messages=[{"role": "user", "content": "test"}],
            max_output_tokens=100,
            schema=schema,
        ))

        assert any("field_b" in w for w in response.warnings)


# ── GatewayProvider ──────────────────────────────────────────────────────────

class TestGatewayProvider:
    def _make_provider(self):
        from backend.providers.base import LLMProvider, LLMResponse

        class MockProvider(LLMProvider):
            def __init__(self):
                super().__init__()
                self.calls = []

            async def complete(self, messages, temperature=0.7, max_tokens=4096):
                self.calls.append(("complete", messages, max_tokens))
                return f"mock response (max={max_tokens})"

            async def structured_output(self, messages, schema, temperature=0.3):
                self.calls.append(("structured_output", messages))
                return {"result": "mock"}

            def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
                async def _gen():
                    yield "mock"
                return _gen()

            @property
            def provider_name(self) -> str:
                return "mock"

            @property
            def default_model(self) -> str:
                return "mock-model"

        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter(default_context=8192)
        gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")

        mock = MockProvider()

        async def provider_fn(**kw):
            if kw.get("schema"):
                return await mock.structured_output(kw["messages"], kw["schema"], kw.get("temperature", 0.3))
            return await mock.complete(kw["messages"], kw.get("temperature", 0.7), kw.get("max_tokens", 4096))

        gateway.set_provider_fn(provider_fn)

        gp = GatewayProvider(gateway, mock)
        return gp, mock

    @pytest.mark.asyncio
    async def test_complete_delegates_through_gateway(self):
        gp, mock = self._make_provider()
        result = await gp.complete([{"role": "user", "content": "test"}], max_tokens=100)
        assert "mock response" in result

    @pytest.mark.asyncio
    async def test_structured_output_delegates(self):
        gp, mock = self._make_provider()
        # Note: GatewayProvider's structured_output uses max_output_tokens=4096
        # which may overflow default context. The gateway auto-reduces output budget.
        result = await gp.structured_output(
            [{"role": "user", "content": "test"}],
            schema={"required": ["result"], "properties": {"result": {}}},
        )
        # Gateway may wrap the result or return it directly
        assert result.get("result") == "mock" or "result" in str(result)

    def test_provider_name_delegates(self):
        gp, mock = self._make_provider()
        assert gp.provider_name == mock.provider_name
