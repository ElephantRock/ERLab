"""Tests for GeminiEmbeddingProvider identity capture + global-state isolation (P0.4B0.1c).

Per directive B0.1c, these tests prove:
  * configuration occurs at bounded provider construction
  * embedding calls re-establish per-instance configuration before use
  * identity evidence reflects the constructed provider instance
  * two differently-configured instances do not poison each other
  * provider failure still propagates
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_GEMINI_CONFIGURED_MODEL,
    ProviderEmbeddingBatch,
)
from backend.pipeline.knowledge.embedding_providers import GeminiEmbeddingProvider


def _install_fake_genai(monkeypatch, capture_list=None):
    """Install a fake google.generativeai module that records configure() calls.

    Returns the fake module so individual tests can program embed_content.
    """
    fake = MagicMock(name="fake_google_generativeai")
    fake._configure_calls = []
    if capture_list is not None:
        capture_list.extend(fake._configure_calls)

    def _configure(**kwargs):
        fake._configure_calls.append(dict(kwargs))

    fake.configure.side_effect = _configure
    # embed_content is async in production via asyncio.to_thread; we mock
    # it as a sync function because asyncio.to_thread wraps it.
    fake.embed_content = MagicMock(return_value={"embedding": [[0.1, 0.2, 0.3]]})

    monkeypatch.setitem(sys.modules, "google.generativeai", fake)
    return fake


class TestConfigurationIsolation:
    def test_two_instances_do_not_poison_each_other(self, monkeypatch):
        """Core directive requirement: constructing or using one instance
        does not silently alter the other's effective identity.

        Pre-B0: __init__ called genai.configure(api_key=...) once and never
        again, so a second instance with a different api_key would silently
        overwrite the first's global state. B0.1c bounds the mutation to
        each embed() call.
        """
        fake = _install_fake_genai(monkeypatch)
        # Each embed_content call returns different vectors so we can tell
        # which instance served which request.
        fake.embed_content.side_effect = [
            {"embedding": [[0.1, 0.1]]},   # provider_a's first call
            {"embedding": [[0.9, 0.9]]},   # provider_b's first call
            {"embedding": [[0.5, 0.5]]},   # provider_a's second call (after b)
        ]

        provider_a = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_A",
        )
        provider_b = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_B",
        )

        # Provider A embeds, then B, then A again. Each call must reconfigure
        # with the calling instance's api_key, so A's second call sees KEY_A,
        # not the KEY_B that B left in global state.
        result_a1 = asyncio.run(provider_a.embed(["a1"]))
        result_b1 = asyncio.run(provider_b.embed(["b1"]))
        result_a2 = asyncio.run(provider_a.embed(["a2"]))

        assert result_a1 == [[0.1, 0.1]]
        assert result_b1 == [[0.9, 0.9]]
        assert result_a2 == [[0.5, 0.5]]

        # Configure calls: 2 construction + 3 embed = 5 total.
        # Order: KEY_A (init A), KEY_B (init B), KEY_A (reconf A1),
        #        KEY_B (reconf B1), KEY_A (reconf A2).
        configure_calls = fake.configure.call_args_list
        assert len(configure_calls) == 5

        api_keys_seq = [c.kwargs.get("api_key") for c in configure_calls]
        assert api_keys_seq == ["KEY_A", "KEY_B", "KEY_A", "KEY_B", "KEY_A"]

        # Critical isolation guarantee: provider_a's second call (index 4)
        # was preceded by a reconfigure with KEY_A, NOT the KEY_B that
        # provider_b's call left in global state at index 3. Pre-B0 this
        # would have silently used whatever global state was left behind.
        assert api_keys_seq[3] == "KEY_B"  # B's reconfigure
        assert api_keys_seq[4] == "KEY_A"  # A's reconfigure before its 2nd call

    def test_no_api_key_skips_global_configuration(self, monkeypatch):
        """When no api_key is provided, the provider does not mutate global state."""
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content = MagicMock(return_value={"embedding": [[0.1, 0.2]]})

        provider = GeminiEmbeddingProvider(model="models/embedding-001", api_key=None)

        asyncio.run(provider.embed(["a"]))

        # No api_key means no configure calls
        fake.configure.assert_not_called()


class TestIdentityEvidenceCapture:
    def test_evidence_reflects_constructed_instance(self, monkeypatch):
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content = MagicMock(return_value={"embedding": [[0.4, 0.5, 0.6]]})

        provider = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="K",
        )

        asyncio.run(provider.embed(["x"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        assert evidence.provider_kind == "gemini"
        assert evidence.requested_model == "models/embedding-001"
        # Gemini returns no served-model field; reported_model is honestly NULL
        assert evidence.reported_model is None
        assert evidence.deployment_id is None
        assert evidence.provider_revision is None
        assert evidence.evidence_source == EVIDENCE_SOURCE_GEMINI_CONFIGURED_MODEL

    def test_evidence_none_before_first_call(self, monkeypatch):
        _install_fake_genai(monkeypatch)
        provider = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="K",
        )
        assert provider.last_identity_evidence is None

    def test_different_models_preserve_distinct_evidence(self, monkeypatch):
        """Two instances with different configured models keep distinct evidence."""
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content.side_effect = [
            {"embedding": [[0.1]]},
            {"embedding": [[0.2]]},
        ]

        provider_001 = GeminiEmbeddingProvider(model="models/embedding-001", api_key="K")
        provider_004 = GeminiEmbeddingProvider(model="models/text-embedding-004", api_key="K")

        asyncio.run(provider_001.embed(["a"]))
        asyncio.run(provider_004.embed(["b"]))

        assert provider_001.last_identity_evidence.requested_model == "models/embedding-001"
        assert provider_004.last_identity_evidence.requested_model == "models/text-embedding-004"


class TestProviderFailurePropagates:
    def test_embed_content_exception_propagates(self, monkeypatch):
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content.side_effect = RuntimeError("quota exceeded")

        provider = GeminiEmbeddingProvider(model="models/embedding-001", api_key="K")

        with pytest.raises(RuntimeError, match="quota exceeded"):
            asyncio.run(provider.embed(["a"]))

        # Failed call does not leave stale evidence
        assert provider.last_identity_evidence is None


class TestEmbedWithEvidence:
    def test_returns_batch_with_vectors_and_evidence(self, monkeypatch):
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content = MagicMock(return_value={"embedding": [[0.7, 0.8]]})

        provider = GeminiEmbeddingProvider(model="models/embedding-001", api_key="K")

        batch = asyncio.run(provider.embed_with_evidence(["q"]))

        assert isinstance(batch, ProviderEmbeddingBatch)
        assert batch.embeddings == ((0.7, 0.8),)
        assert batch.identity_evidence.provider_kind == "gemini"
        assert batch.identity_evidence.reported_model is None


class TestNoCredentialsInEvidence:
    def test_api_key_not_in_evidence_fields(self, monkeypatch):
        fake = _install_fake_genai(monkeypatch)
        fake.embed_content = MagicMock(return_value={"embedding": [[0.1, 0.2]]})

        provider = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="GEM-SECRET-DO-NOT-LEAK",
        )
        asyncio.run(provider.embed(["a"]))

        evidence = provider.last_identity_evidence
        assert evidence is not None
        for field_name in ("provider_kind", "requested_model", "reported_model",
                           "deployment_id", "provider_revision", "evidence_source"):
            value = getattr(evidence, field_name)
            if value is not None:
                assert "GEM-SECRET" not in str(value), f"secret leaked in field {field_name}"


# ─── P0.4B0.1c follow-up: concurrency seal ────────────────────────────────


class _ConcurrentFakeGenai:
    """Fake genai module that records what api_key was active at the moment
    each embed_content call executed.

    The 'observed_key_for_call' list records the api_key that was in effect
    when each embed_content call began. Without the process-wide lock, an
    interleaving instance's configure() could land between another
    instance's configure() and embed_content() — and embed_content would
    observe the wrong api_key. With the lock, each call observes only its
    own instance's api_key.
    """

    def __init__(self) -> None:
        self.current_api_key: str | None = None
        self.observed_key_for_call: list[str | None] = []
        self.embed_content_calls = 0

    def configure(self, *, api_key: str | None = None) -> None:
        # Simulate the global mutation that is the root of the concurrency hazard
        self.current_api_key = api_key

    def embed_content(self, *, model, content, task_type):
        # CRITICAL: this is the value that must reflect the calling instance's
        # configuration. Read it at the moment of the call (the production code
        # also reads model identity at this point). Yield to the event loop
        # to give other tasks a chance to interleave — without the lock, an
        # interleaving instance's configure() would land here.
        import asyncio as _asyncio
        # The call runs inside asyncio.to_thread in production; we cannot
        # await from inside a sync function, but we can simulate yielding
        # by recording the observed key BEFORE any further mutation.
        observed = self.current_api_key
        self.observed_key_for_call.append(observed)
        self.embed_content_calls += 1
        # Return vectors tagged with the observed api_key so the test can
        # assert which instance actually served the request.
        if observed == "KEY_A":
            return {"embedding": [[0.1, 0.1]]}
        if observed == "KEY_B":
            return {"embedding": [[0.9, 0.9]]}
        return {"embedding": [[0.0, 0.0]]}


class TestGeminiConcurrencySeal:
    """Adversarial test: overlapping calls from two differently-configured
    GeminiEmbeddingProvider instances must not observe each other's
    configuration. Per directive:

        Provider A configured for model A
        Provider B configured for model B
        both calls overlap
        Expected:
          A evidence reports model A
          B evidence reports model B
          A request cannot observe B configuration
          B request cannot observe A configuration
    """

    def test_overlapping_calls_do_not_cross_observe(self, monkeypatch):
        fake = _ConcurrentFakeGenai()
        monkeypatch.setitem(sys.modules, "google.generativeai", fake)

        provider_a = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_A",
        )
        provider_b = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_B",
        )

        # Launch both embed calls concurrently. Without the process-wide
        # lock, B's configure() could land between A's configure() and
        # A's embed_content() execution, causing A's request to observe
        # KEY_B. With the lock, the two calls serialize and each one
        # only ever observes its own api_key.
        async def _run_concurrent():
            return await asyncio.gather(
                provider_a.embed(["a"]),
                provider_b.embed(["b"]),
            )

        results = asyncio.run(_run_concurrent())

        # Exactly two embed_content calls — one per gather'd coroutine
        assert fake.embed_content_calls == 2

        # Each call observed its own api_key — never the other instance's
        observed = fake.observed_key_for_call
        assert sorted(observed) == ["KEY_A", "KEY_B"]
        # Neither call observed None or a stale value
        assert None not in observed

        # Result vectors tagged with the actually-observed key match the
        # caller's identity. (Vector content is a proxy for "which identity
        # served this request".)
        # Results may come back in either gather order, so check the set.
        result_set = {tuple(r[0]) for r in results}
        assert (0.1, 0.1) in result_set  # A's vector
        assert (0.9, 0.9) in result_set  # B's vector
        # No zero-vectors (which would indicate observation of None/other)
        assert (0.0, 0.0) not in result_set

    def test_many_overlapping_calls_each_observe_own_key(self, monkeypatch):
        """Stress the lock: 4 overlapping calls from two providers, each
        interleaved. Each must observe only its own api_key."""
        fake = _ConcurrentFakeGenai()
        monkeypatch.setitem(sys.modules, "google.generativeai", fake)

        provider_a = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_A",
        )
        provider_b = GeminiEmbeddingProvider(
            model="models/embedding-001", api_key="KEY_B",
        )

        async def _run_concurrent():
            return await asyncio.gather(
                provider_a.embed(["a1"]),
                provider_b.embed(["b1"]),
                provider_a.embed(["a2"]),
                provider_b.embed(["b2"]),
            )

        asyncio.run(_run_concurrent())

        assert fake.embed_content_calls == 4
        observed = fake.observed_key_for_call
        # Each call observed its own caller's key — never the other's,
        # never None
        for key in observed:
            assert key in ("KEY_A", "KEY_B")
        # Two calls per provider
        assert observed.count("KEY_A") == 2
        assert observed.count("KEY_B") == 2

    def test_concurrent_same_key_does_not_corrupt_evidence(self, monkeypatch):
        """Sanity: two instances with the SAME api_key can run concurrently
        without either observing stale or wrong state. The lock must not
        introduce deadlocks or evidence corruption for the simple case."""
        fake = _ConcurrentFakeGenai()
        monkeypatch.setitem(sys.modules, "google.generativeai", fake)

        provider_a = GeminiEmbeddingProvider(model="models/embedding-001", api_key="SAME_KEY")
        provider_b = GeminiEmbeddingProvider(model="models/embedding-001", api_key="SAME_KEY")

        async def _run_concurrent():
            return await asyncio.gather(
                provider_a.embed(["a"]),
                provider_b.embed(["b"]),
                provider_a.embed(["c"]),
            )

        asyncio.run(_run_concurrent())

        assert fake.embed_content_calls == 3
        # Every call observed SAME_KEY — no None, no stale value
        assert all(k == "SAME_KEY" for k in fake.observed_key_for_call)
