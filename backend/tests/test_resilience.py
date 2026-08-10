"""Tests for provider resilience — circuit breaker, retry, encryption, key vault."""

import time

import anyio
import pytest


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param

from backend.providers.resilience.circuit_breaker import CircuitBreaker
from backend.providers.resilience.errors import (
    CircuitOpenError,
    RetryDecision,
    classify_status,
)
from backend.providers.resilience.resilient_provider import ResilientProvider
from backend.providers.resilience.retry import RetryConfig, retry_with_backoff
from backend.providers.secrets import CryptoUtils, KeyVault
from backend.tests.conftest import FakeLLMProvider, FlakyLLMProvider

# ---- Circuit Breaker ----


class TestCircuitBreaker:
    @pytest.mark.anyio
    async def test_opens_after_threshold(self, circuit_breaker):
        for _ in range(3):
            await circuit_breaker.record_failure()
        assert circuit_breaker.state == "open"
        assert not await circuit_breaker.allow_request()

    @pytest.mark.anyio
    async def test_half_open_recovery(self, circuit_breaker):
        for _ in range(3):
            await circuit_breaker.record_failure()
        assert circuit_breaker.state == "open"
        await anyio.sleep(0.6)
        assert await circuit_breaker.allow_request()
        assert circuit_breaker.state == "half_open"
        await circuit_breaker.record_success()
        assert circuit_breaker.state == "closed"

    @pytest.mark.anyio
    async def test_closed_resets_failure_count_on_success(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == "closed"
        await cb.record_success()
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == "closed"

    @pytest.mark.anyio
    async def test_check_raises_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0)
        await cb.record_failure()
        with pytest.raises(CircuitOpenError):
            cb.check()


# ---- Retry ----


class TestRetry:
    @pytest.mark.anyio
    async def test_succeeds_after_transient_failure(self, retry_config):
        cb = CircuitBreaker(failure_threshold=10)
        call_count = 0

        async def flaky_fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient")
            return "ok"

        result = await retry_with_backoff(flaky_fn, retry_config, cb)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.anyio
    async def test_cooldown_on_429(self, retry_config):
        cb = CircuitBreaker(failure_threshold=10)

        class MockResponse:
            status_code = 429

        class RateLimitError(Exception):
            response = MockResponse()

        call_count = 0

        async def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("rate limited")
            return "ok"

        start = time.monotonic()
        result = await retry_with_backoff(rate_limited, retry_config, cb)
        elapsed = time.monotonic() - start
        assert result == "ok"
        assert elapsed >= 0.04

    @pytest.mark.anyio
    async def test_no_retry_on_401(self, retry_config):
        cb = CircuitBreaker(failure_threshold=10)

        class MockResponse:
            status_code = 401

        class AuthError(Exception):
            response = MockResponse()

        async def auth_fail():
            raise AuthError("unauthorized")

        with pytest.raises(AuthError):
            await retry_with_backoff(auth_fail, retry_config, cb)

    @pytest.mark.anyio
    async def test_exhausts_retries(self, retry_config):
        cb = CircuitBreaker(failure_threshold=10)

        async def always_fail():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            await retry_with_backoff(always_fail, retry_config, cb)

    @pytest.mark.anyio
    async def test_circuit_open_fast_fail(self, retry_config):
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0)
        await cb.record_failure()

        async def fn():
            return "should not reach"

        with pytest.raises(CircuitOpenError):
            await retry_with_backoff(fn, retry_config, cb)


# ---- ResilientProvider ----


class TestResilientProvider:
    @pytest.mark.anyio
    async def test_wraps_all_methods(self, retry_config):
        inner = FakeLLMProvider(responses={"complete": "hello"})
        cb = CircuitBreaker()
        rp = ResilientProvider(inner, cb, retry_config)

        assert await rp.complete([{"role": "user", "content": "hi"}]) == "hello"
        assert rp.provider_name == "fake"
        assert rp.default_model == "fake-model"

    @pytest.mark.anyio
    async def test_retries_transient_failures(self, retry_config):
        inner = FlakyLLMProvider(fail_count=2)
        cb = CircuitBreaker(failure_threshold=10)
        rp = ResilientProvider(inner, cb, retry_config)

        result = await rp.complete([{"role": "user", "content": "hi"}])
        assert result == "Test response"
        assert cb.state == "closed"

    @pytest.mark.anyio
    async def test_stream_checks_circuit(self):
        inner = FakeLLMProvider()
        cb = CircuitBreaker(failure_threshold=1, reset_timeout=10.0)
        rp = ResilientProvider(inner, cb, RetryConfig())

        await cb.record_failure()
        with pytest.raises(CircuitOpenError):
            rp.complete_stream([{"role": "user", "content": "hi"}])

    @pytest.mark.anyio
    async def test_health_check_returns_false_on_failure(self, retry_config):
        inner = FlakyLLMProvider(fail_count=100)
        cb = CircuitBreaker(failure_threshold=100)
        rp = ResilientProvider(inner, cb, retry_config)
        assert await rp.health_check() is False


# ---- Encryption ----


class TestCrypto:
    def test_roundtrip(self):
        plaintext = "sk-test-api-key-12345"
        password = "master-password"
        token = CryptoUtils.encrypt(plaintext, password)
        assert CryptoUtils.decrypt(token, password) == plaintext

    def test_different_tokens_for_same_plaintext(self):
        plaintext = "same-value"
        password = "pass"
        t1 = CryptoUtils.encrypt(plaintext, password)
        t2 = CryptoUtils.encrypt(plaintext, password)
        assert t1 != t2
        assert CryptoUtils.decrypt(t1, password) == CryptoUtils.decrypt(t2, password)

    def test_wrong_password_fails(self):
        token = CryptoUtils.encrypt("secret", "correct")
        with pytest.raises(Exception):
            CryptoUtils.decrypt(token, "wrong")


# ---- KeyVault ----


class TestKeyVault:
    @pytest.mark.anyio
    async def test_multi_key_rotation(self, key_vault):
        assert key_vault.get_active_key("openai") == "sk-test-key-1"
        key2 = await key_vault.rotate_key("openai")
        assert key2 == "sk-test-key-2"
        key3 = await key_vault.rotate_key("openai")
        assert key3 == "sk-test-key-3"

    @pytest.mark.anyio
    async def test_fails_when_all_keys_unhealthy(self, key_vault):
        # 3 keys: rotate marks current unhealthy each time
        # rotate 1: key-0 unhealthy -> key-1 active
        # rotate 2: key-1 unhealthy -> key-2 active
        # rotate 3: key-2 unhealthy -> all unhealthy, raises
        await key_vault.rotate_key("openai")  # key-0 -> key-1
        await key_vault.rotate_key("openai")  # key-1 -> key-2
        with pytest.raises(Exception):
            await key_vault.rotate_key("openai")  # key-2 -> all unhealthy

    def test_persistence(self, tmp_path):
        vault = KeyVault(
            master_password="pw",
            persist_path=str(tmp_path / "test_vault.json"),
        )
        vault.add_key("anthropic", "sk-ant-1")
        vault.add_key("anthropic", "sk-ant-2")
        vault.persist()

        loaded = KeyVault(
            master_password="pw",
            persist_path=str(tmp_path / "test_vault.json"),
        )
        loaded.load()
        assert loaded.key_count("anthropic") == 2
        assert loaded.get_active_key("anthropic") == "sk-ant-1"

    @pytest.mark.anyio
    async def test_rotation_skips_unhealthy(self, key_vault):
        await key_vault.rotate_key("openai")
        keys = key_vault._keys["openai"]
        key_vault.mark_key_unhealthy("openai", key_vault._hint(keys[1]))
        key3 = await key_vault.rotate_key("openai")
        assert key3 == "sk-test-key-3"


# ---- Error Classification ----


class TestErrorClassification:
    def test_429_is_cooldown(self):
        assert classify_status(429) == RetryDecision.COOLDOWN

    def test_401_is_no_retry(self):
        assert classify_status(401) == RetryDecision.NO_RETRY

    def test_403_is_no_retry(self):
        assert classify_status(403) == RetryDecision.NO_RETRY

    def test_500_is_retry(self):
        assert classify_status(500) == RetryDecision.RETRY

    def test_502_is_retry(self):
        assert classify_status(502) == RetryDecision.RETRY

    def test_200_is_no_retry(self):
        assert classify_status(200) == RetryDecision.NO_RETRY
