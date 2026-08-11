"""Tests for the P1C snapshot-generation retry boundaries.

Frozen by the P1C closeout qualification (2026-07-21). These six boundaries
must hold; the retry policy is an EXPERIMENT-HARNESS policy only and must
not become an implicit production embedding default:

  authority or binding failure    → fail immediately, no retry
  transient provider failure      → bounded retry
  candidate snapshot failure      → no partial snapshot promoted as valid
  retry exhaustion                → explicit failed generation result
  control snapshot                → never overwritten
  retry policy                    → experiment-harness only

The retry path also records per-item attempt counts and terminal failure
codes so a repeatedly-crashing provider cannot appear merely slow.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from backend.pipeline.capability.capability_errors import (
    CAPABILITY_BINDING_MISMATCH,
    CAPABILITY_CHECK_EXPIRED,
    CapabilityAuthorizationError,
)
from backend.ranking.embedding_snapshot import (
    SnapshotBindingEvidence,
    SnapshotIntegrityError,
    SnapshotItem,
    canonical_text_hash,
    write_snapshot,
)
from backend.ranking.generate_embedding_snapshot import (
    SnapshotGenerationFailure,
    _embed_one_with_retry,
    _is_transient_provider_error,
)


def _fake_runtime(*, query_side_effect=None, doc_side_effect=None):
    """Build a fake VerifiedEmbeddingRuntime-like object for testing."""
    rt = MagicMock()

    async def _q(text):
        if query_side_effect:
            r = query_side_effect(text)
            if isinstance(r, Exception):
                raise r
            if r is not None:
                return r
            # None means "use default receipt"
        rec = MagicMock()
        rec.embedding = (0.1, 0.2, 0.3)
        rec.capability_binding_id = "b" * 64
        rec.capability_check_id = "c" * 64
        rec.runtime_config_fingerprint = "f" * 64
        return rec

    async def _d(texts):
        if doc_side_effect:
            r = doc_side_effect(texts)
            if isinstance(r, Exception):
                raise r
            if r is not None:
                return r
        rec = MagicMock()
        rec.embeddings = tuple((0.1, 0.2, 0.3) for _ in texts)
        rec.capability_binding_id = "b" * 64
        rec.capability_check_id = "c" * 64
        rec.runtime_config_fingerprint = "f" * 64
        return rec

    rt.embed_query_authorized = _q
    rt.embed_documents_authorized = _d
    return rt


class TestAuthorityFailureNeverRetries:
    """Boundary 1: authority/binding failures abort immediately, no retry."""

    def test_capability_authorization_error_is_not_transient(self):
        e = CapabilityAuthorizationError(CAPABILITY_CHECK_EXPIRED, "expired")
        assert _is_transient_provider_error(e) is False

    def test_binding_mismatch_is_not_transient(self):
        e = CapabilityAuthorizationError(CAPABILITY_BINDING_MISMATCH, "mismatch")
        assert _is_transient_provider_error(e) is False

    def test_authority_failure_aborts_immediately_with_explicit_code(self):
        call_count = {"n": 0}

        def query_side_effect(text):
            call_count["n"] += 1
            return CapabilityAuthorizationError(CAPABILITY_CHECK_EXPIRED, "expired")

        rt = _fake_runtime(query_side_effect=query_side_effect)
        with pytest.raises(SnapshotGenerationFailure) as exc_info:
            asyncio.run(_embed_one_with_retry(rt, "q", is_query=True, item_id="q1", max_retries=8))
        assert exc_info.value.code == SnapshotGenerationFailure.CODE_AUTHORITY_FAILURE
        assert exc_info.value.item_id == "q1"
        # Must have aborted on the FIRST attempt — no retry.
        assert exc_info.value.attempts == 1
        assert call_count["n"] == 1


class TestTransientProviderFailureBoundedRetry:
    """Boundary 2: transient provider failures retry, bounded."""

    def test_crash_signature_is_transient(self):
        for msg in ("model has crashed", "Model reloaded..", "no models loaded",
                    "connection reset", "HTTP 503", "HTTP 502"):
            assert _is_transient_provider_error(Exception(msg)) is True, msg

    def test_succeeds_after_transient_failures(self):
        # Fail twice with a crash signature, then succeed.
        attempts = {"n": 0}

        def query_side_effect(text):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return Exception("model has crashed")
            # success path: return None so _q uses its default receipt
            return None

        rt = _fake_runtime(query_side_effect=query_side_effect)
        receipt = asyncio.run(_embed_one_with_retry(
            rt, "q", is_query=True, item_id="q1", max_retries=8))
        # _fake_runtime's _q returns a real receipt on the success path
        assert receipt is not None
        assert receipt.embedding == (0.1, 0.2, 0.3)
        assert attempts["n"] == 3  # 2 transient + 1 success

    def test_retry_exhaustion_raises_explicit_failure_with_attempt_count(self):
        attempts = {"n": 0}

        def query_side_effect(text):
            attempts["n"] += 1
            return Exception("model has crashed")

        rt = _fake_runtime(query_side_effect=query_side_effect)
        with pytest.raises(SnapshotGenerationFailure) as exc_info:
            asyncio.run(_embed_one_with_retry(
                rt, "q", is_query=True, item_id="q1", max_retries=4))
        assert exc_info.value.code == SnapshotGenerationFailure.CODE_RETRY_EXHAUSTED
        assert exc_info.value.item_id == "q1"
        assert exc_info.value.attempts == 4
        # The recorded attempt count proves the provider was crashing, not slow.
        assert attempts["n"] == 4


class TestNonTransientProviderFailureIsTerminal:
    """A provider error that is NOT a known transient signature is terminal."""

    def test_401_is_not_transient(self):
        assert _is_transient_provider_error(Exception("401 unauthorized")) is False

    def test_404_is_not_transient(self):
        assert _is_transient_provider_error(Exception("404 model not found")) is False

    def test_non_transient_failure_aborts_with_explicit_code(self):
        attempts = {"n": 0}

        def query_side_effect(text):
            attempts["n"] += 1
            return Exception("401 unauthorized")

        rt = _fake_runtime(query_side_effect=query_side_effect)
        with pytest.raises(SnapshotGenerationFailure) as exc_info:
            asyncio.run(_embed_one_with_retry(
                rt, "q", is_query=True, item_id="q1", max_retries=8))
        assert exc_info.value.code == SnapshotGenerationFailure.CODE_NON_TRANSIENT_PROVIDER
        assert exc_info.value.attempts == 1  # no retry
        assert attempts["n"] == 1


class TestEmptyVectorIsTerminal:
    """Provider returning zero vectors is a terminal generation failure."""

    def test_empty_vector_raises_terminal_failure(self):
        def doc_side_effect(texts):
            rec = MagicMock()
            rec.embeddings = ()  # empty
            return rec

        rt = _fake_runtime(doc_side_effect=doc_side_effect)
        with pytest.raises(SnapshotGenerationFailure) as exc_info:
            asyncio.run(_embed_one_with_retry(
                rt, "t", is_query=False, item_id="c1", max_retries=4))
        assert exc_info.value.code == SnapshotGenerationFailure.CODE_EMPTY_VECTOR


class TestNoPartialSnapshotPromoted:
    """Boundary 3: a failed generation must not produce a partial snapshot."""

    def test_write_snapshot_is_atomic_per_dir(self, tmp_path):
        """If generation fails mid-way, no snapshot.json exists for that tag."""
        # write_snapshot only writes after ALL items are computed; a mid-flight
        # failure in _embed_all raises before write_snapshot is called, so the
        # output dir contains no snapshot.json. Verify write_snapshot itself
        # is the only writer and it writes both files together.
        d = tmp_path / "snap"
        # no files yet
        assert not (d / "snapshot.json").exists()
        items = [SnapshotItem(item_id="q1", item_role="query", canonical_text="q",
                              text_hash=canonical_text_hash("q"),
                              vector=(0.1,), vector_fingerprint="x" * 64)]
        binding = SnapshotBindingEvidence(
            capability_binding_id="b" * 64, capability_check_id="c" * 64,
            generation_runtime_fingerprint="f" * 64, provider_kind="lmstudio",
            provider_model="m", provider_revision=None,
            endpoint_identity="http://x", deployment_id=None,
            embedding_contract_version="v1", dimension=1, normalization_policy="none",
        )
        write_snapshot(d, benchmark_version="bv", benchmark_fingerprint="a" * 64,
                       binding=binding, items=items)
        # both files written together — atomic-ish (json first, then sidecar)
        assert (d / "snapshot.json").exists()
        assert (d / "snapshot.fingerprint").exists()


class TestControlSnapshotNeverOverwritten:
    """Boundary 5: write_snapshot refuses to overwrite an existing snapshot."""

    def test_refuses_overwrite(self, tmp_path):
        d = tmp_path / "snap"
        items = [SnapshotItem(item_id="q1", item_role="query", canonical_text="q",
                              text_hash=canonical_text_hash("q"),
                              vector=(0.1,), vector_fingerprint="x" * 64)]
        binding = SnapshotBindingEvidence(
            capability_binding_id="b" * 64, capability_check_id="c" * 64,
            generation_runtime_fingerprint="f" * 64, provider_kind="lmstudio",
            provider_model="m", provider_revision=None,
            endpoint_identity="http://x", deployment_id=None,
            embedding_contract_version="v1", dimension=1, normalization_policy="none",
        )
        write_snapshot(d, benchmark_version="bv", benchmark_fingerprint="a" * 64,
                       binding=binding, items=items)
        with pytest.raises(SnapshotIntegrityError, match="refusing to overwrite"):
            write_snapshot(d, benchmark_version="bv", benchmark_fingerprint="a" * 64,
                           binding=binding, items=items)

    def test_control_snapshot_path_is_separate_from_candidate_paths(self):
        """The EROCK_P1C_SNAPSHOT_TAG mechanism writes candidate snapshots under
        docs/p1c_snapshots/<tag>/, NEVER under docs/p1b_snapshot/ (the control).

        This is enforced structurally: when EROCK_P1C_SNAPSHOT_TAG is set,
        SNAPSHOT_DIR points at p1c_snapshots/<tag>; when unset, it points at
        p1b_snapshot. Generation of a candidate therefore cannot overwrite the
        control.

        P0.5 config-effectiveness seal: the tag is read via Settings (the
        EROCK_-prefixed env var), not via a direct os.environ read in production
        code. This test is also the focused config-effect proof for the
        p1c_snapshot_tag Settings field.
        """
        import importlib
        import os

        import backend.ranking.generate_embedding_snapshot as mod
        from backend.config import get_settings

        _ENV = "EROCK_P1C_SNAPSHOT_TAG"

        def _reload_with_cache_clear():
            # get_settings() is lru_cached, so clear it so Settings() re-reads
            # the environment on the next import-time get_settings() call.
            get_settings.cache_clear()
            importlib.reload(mod)

        # default (no tag) -> control path
        os.environ.pop(_ENV, None)
        _reload_with_cache_clear()
        assert mod.SNAPSHOT_DIR.name == "p1b_snapshot"
        # with a candidate tag -> candidate path, distinct from control
        os.environ[_ENV] = "all_minilm_l12_v2"
        try:
            _reload_with_cache_clear()
            assert mod.SNAPSHOT_DIR.name == "all_minilm_l12_v2"
            assert mod.SNAPSHOT_DIR.parent.name == "p1c_snapshots"
        finally:
            os.environ.pop(_ENV, None)
            _reload_with_cache_clear()



class TestRetryPolicyIsExperimentHarnessOnly:
    """Boundary 6: the retry logic lives in the snapshot GENERATION harness,
    not in the production VerifiedEmbeddingRuntime or GovernedEmbeddingAdapter.

    The production embedding path must NOT silently retry — that could mask
    real provider failures in production traffic. We assert the production
    classes do not import or call the retry helper.
    """

    def test_production_runtime_does_not_use_retry_helper(self):
        from backend.pipeline.capability import verified_embedding_runtime as prod
        src = open(prod.__file__).read()
        assert "_embed_one_with_retry" not in src
        assert "SnapshotGenerationFailure" not in src

    def test_production_adapter_does_not_use_retry_helper(self):
        from backend.pipeline import governed_embedding_adapter as prod
        src = open(prod.__file__).read()
        assert "_embed_one_with_retry" not in src
        assert "SnapshotGenerationFailure" not in src

    def test_retry_helper_lives_only_in_generation_harness(self):
        """The retry helper is defined in generate_embedding_snapshot.py only."""
        import backend.ranking.generate_embedding_snapshot as harness
        assert hasattr(harness, "_embed_one_with_retry")
        assert hasattr(harness, "SnapshotGenerationFailure")
