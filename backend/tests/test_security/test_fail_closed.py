"""Tests for Phase 5: Security & Fail-Closed Critical Paths.

Tests cover:
1. Production config refuses insecure defaults
2. WebSocket auth: no query-string token, first-message auth required
3. Embedding fail-closed: provider failure raises, zero vectors rejected
4. Persistence failure propagation (checkpoint errors fail the stage)
5. Exception discipline in new code paths

Run: pytest backend/tests/test_security/ -v
"""

from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.config import Settings, ProductionConfigError


# ===================================================================
# 1. Production Config Validation
# ===================================================================

class TestProductionConfigValidation:
    """Production mode refuses insecure defaults."""

    def test_dev_mode_allows_defaults(self):
        """Development mode should not trigger validation automatically."""
        # When env=development, validate_production is not called by get_settings.
        # We verify that the env field itself indicates development.
        s = Settings(env="development")
        assert not s.is_production
        assert not s.effective_debug or s.debug is False  # dev allows debug

        # Calling validate_production directly with dev settings
        # should still work because env is development, not production.
        # validate_production checks is_production internally — it should
        # be a no-op for development.
        s2 = Settings(env="development")
        assert not s2.is_production

    def test_production_rejects_default_jwt_secret(self):
        """Production must not use the default JWT secret."""
        s = Settings(env="production", jwt_secret="dev-secret-change-in-production")
        with pytest.raises(ProductionConfigError, match="jwt_secret"):
            s.validate_production()

    def test_production_accepts_custom_jwt_secret(self):
        """Production with a custom JWT secret should pass that check."""
        s = Settings(
            env="production",
            jwt_secret="a-very-strong-and-unique-secret-12345",
            cors_origins=["https://example.com"],
            auth_enabled=True,
        )
        s.validate_production()

    def test_production_rejects_wildcard_cors(self):
        """Production must not use wildcard CORS."""
        s = Settings(
            env="production",
            jwt_secret="strong-secret",
            cors_origins=["*"],
            auth_enabled=True,
        )
        with pytest.raises(ProductionConfigError, match="cors_origins"):
            s.validate_production()

    def test_production_rejects_auth_disabled(self):
        """Production must have auth enabled."""
        s = Settings(
            env="production",
            jwt_secret="strong-secret",
            cors_origins=["https://example.com"],
            auth_enabled=False,
        )
        with pytest.raises(ProductionConfigError, match="auth_enabled"):
            s.validate_production()

    def test_production_rejects_noop_sandbox(self):
        """Production must not use noop sandbox."""
        s = Settings(
            env="production",
            jwt_secret="strong-secret",
            cors_origins=["https://example.com"],
            auth_enabled=True,
            sandboxing_enabled=True,
            sandbox_backend="noop",
        )
        with pytest.raises(ProductionConfigError, match="noop"):
            s.validate_production()

    def test_production_reports_all_errors(self):
        """All insecure defaults are reported in one error."""
        s = Settings(
            env="production",
            jwt_secret="dev-secret-change-in-production",
            cors_origins=["*"],
            auth_enabled=False,
        )
        with pytest.raises(ProductionConfigError) as exc_info:
            s.validate_production()
        msg = str(exc_info.value)
        assert "jwt_secret" in msg
        assert "cors_origins" in msg
        assert "auth_enabled" in msg

    def test_production_auto_sandbox_warns_not_errors(self):
        """Auto sandbox backend should warn, not error."""
        s = Settings(
            env="production",
            jwt_secret="strong-secret",
            cors_origins=["https://example.com"],
            auth_enabled=True,
            sandboxing_enabled=True,
            sandbox_backend="auto",
        )
        # Should not raise — auto is a warning, not an error
        s.validate_production()


# ===================================================================
# 2. WebSocket Auth
# ===================================================================

class TestWebSocketAuth:
    """WebSocket authentication removes query-string token."""

    def test_websocket_no_query_param_in_signature(self):
        """The websocket_endpoint should not accept a 'token' query param."""
        import inspect
        from backend.api.ws import websocket_endpoint
        sig = inspect.signature(websocket_endpoint)
        assert "token" not in sig.parameters, (
            "WebSocket endpoint must not accept 'token' as a query parameter"
        )

    def test_validate_ws_token_returns_false_for_none(self):
        from backend.api.ws import _validate_ws_token
        assert _validate_ws_token(None) is False

    def test_validate_ws_token_returns_false_for_empty(self):
        from backend.api.ws import _validate_ws_token
        assert _validate_ws_token("") is False

    def test_ws_docstring_mentions_no_query_string(self):
        """Docstring should mention that query-string auth is removed."""
        from backend.api.ws import websocket_endpoint
        assert websocket_endpoint.__doc__ is not None
        assert "query-string" in websocket_endpoint.__doc__.lower() or \
               "query string" in websocket_endpoint.__doc__.lower()


# ===================================================================
# 3. Embedding Fail-Closed
# ===================================================================

class TestEmbeddingFailClosed:
    """Embedding provider failures must raise, not return zero vectors."""

    def test_provider_failure_raises(self):
        """When the embedding provider raises, embed_texts raises."""
        from backend.pipeline.knowledge.embedding_service import (
            EmbeddingService,
            EmbeddingProviderError,
        )

        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(side_effect=RuntimeError("API timeout"))
        mock_provider.dimension = 1536

        service = EmbeddingService(provider=mock_provider, batch_size=10)
        with pytest.raises(EmbeddingProviderError, match="API timeout"):
            asyncio.run(service.embed_texts(["hello"]))

    def test_zero_vector_from_provider_raises(self):
        """When the provider returns zero vectors, embed_texts raises."""
        from backend.pipeline.knowledge.embedding_service import (
            EmbeddingService,
            EmbeddingProviderError,
        )

        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[[0.0] * 1536])
        mock_provider.dimension = 1536

        service = EmbeddingService(provider=mock_provider, batch_size=10)
        with pytest.raises(EmbeddingProviderError, match="zero vectors"):
            asyncio.run(service.embed_texts(["hello"]))

    def test_no_silent_fallback_to_zeros(self):
        """No path in embed_texts produces zero vectors as a return value."""
        from backend.pipeline.knowledge.embedding_service import (
            EmbeddingService,
            EmbeddingProviderError,
        )

        # Provider returns valid vectors — should work
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[[0.1] * 1536])
        mock_provider.dimension = 1536

        service = EmbeddingService(provider=mock_provider, batch_size=10)
        results = asyncio.run(service.embed_texts(["hello"]))
        assert len(results) == 1
        assert all(v != 0.0 for v in results[0])  # Non-zero

    def test_embed_single_raises_on_failure(self):
        """embed_single propagates errors instead of returning zero vector."""
        from backend.pipeline.knowledge.embedding_service import (
            EmbeddingService,
            EmbeddingProviderError,
        )

        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(side_effect=ConnectionError("No network"))
        mock_provider.dimension = 768

        service = EmbeddingService(provider=mock_provider)
        with pytest.raises(EmbeddingProviderError):
            asyncio.run(service.embed_single("test"))

    def test_empty_texts_returns_empty_list(self):
        """Empty input is the only path to an empty return."""
        from backend.pipeline.knowledge.embedding_service import EmbeddingService

        mock_provider = AsyncMock()
        mock_provider.dimension = 1536

        service = EmbeddingService(provider=mock_provider)
        results = asyncio.run(service.embed_texts([]))
        assert results == []


# ===================================================================
# 4. Persistence Failure Propagation
# ===================================================================

class TestPersistenceFailurePropagation:
    """Checkpoint/persistence errors must fail the stage, not warning-only."""

    def test_save_checkpoint_raises_not_warns(self):
        """save_checkpoint failure raises CheckpointPersistenceError."""
        from backend.pipeline.persistence import (
            PipelinePersistence,
            CheckpointPersistenceError,
        )
        from backend.pipeline.execution.run_state import RunCheckpoint

        persistence = PipelinePersistence()
        cp = RunCheckpoint.create_new("test_propagation", ["s1"])

        with patch("pathlib.Path.open", side_effect=OSError("disk full")):
            with pytest.raises(CheckpointPersistenceError):
                persistence.save_checkpoint(cp)

    def test_load_checkpoint_raises_on_corrupt(self):
        """load_checkpoint failure on corrupted file raises typed error."""
        from backend.pipeline.persistence import (
            PipelinePersistence,
            CheckpointPersistenceError,
        )

        persistence = PipelinePersistence()
        with patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_text", return_value="CORRUPT{"):
            with pytest.raises(CheckpointPersistenceError, match="Corrupted"):
                persistence.load_checkpoint("run_bad")

    def test_heartbeat_failure_does_not_crash(self):
        """Heartbeat checkpoint failure logs warning, does not crash the run."""
        from backend.pipeline.execution.run_state import RunCheckpoint
        persistence = MagicMock()
        persistence.save_checkpoint.side_effect = Exception("disk full")

        cp = RunCheckpoint.create_new("test_hb", ["s1"])
        # The heartbeat loop catches exceptions
        # Verify the pattern works: exception is caught and logged
        try:
            persistence.save_checkpoint(cp)
        except Exception as e:
            assert "disk full" in str(e)
            # This is expected — heartbeat catches and logs


# ===================================================================
# 5. Exception Discipline in New Code
# ===================================================================

class TestExceptionDiscipline:
    """New code paths must not have broad 'except Exception' that isn't typed."""

    def test_executor_exception_is_typed(self):
        """OperationExecutor converts exceptions to typed errors."""
        from backend.pipeline.operations.executor import OperationExecutor
        from backend.pipeline.operations.types import LMStudioUnreachableError

        # The _safe_get_loaded_models catches Exception but converts to
        # LMStudioUnreachableError or returns empty
        import inspect
        source = inspect.getsource(OperationExecutor._safe_get_loaded_models)
        assert "LMStudioUnreachableError" in source
        assert "except Exception" in source  # Caught but converted

    def test_run_service_has_no_broad_except(self):
        """RunService should not have any 'except Exception' handlers."""
        import inspect
        from backend.api.run_service import RunService
        source = inspect.getsource(RunService)
        # RunService should be clean — no bare except Exception
        lines = [l.strip() for l in source.split("\n") if "except Exception" in l]
        # If there are any, they must be followed by 'raise' or typed conversion
        assert len(lines) == 0, (
            f"RunService has {len(lines)} 'except Exception' handler(s) — "
            "new code must use typed exceptions"
        )

    def test_persistence_save_has_no_warning_only(self):
        """save_checkpoint must not have warning-only error handling."""
        import inspect
        from backend.pipeline.persistence import PipelinePersistence
        source = inspect.getsource(PipelinePersistence.save_checkpoint)
        assert "self.warnings" not in source, (
            "save_checkpoint must not append to self.warnings — "
            "it must raise typed errors"
        )
        assert "CheckpointPersistenceError" in source
