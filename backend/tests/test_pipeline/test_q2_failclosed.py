"""Q2 regressions: fail-closed provider readiness, transport-failure
identity, and the autonomous false-SUCCEEDED closure.

Provenance: Case-3 qualification attempts 3B–3D failed opaquely because
(a) startup readiness was non-authoritative (warn + static defaults),
(b) the gateway converted transport/provider failures into
success-shaped empty LLMResponses, and (c) an autonomous run with gaps
but zero ideas finalized as SUCCEEDED. These tests pin all three
corrections.
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.gateway.transport import GatewayTransportError

# ── Q2-1: fail-closed readiness ────────────────────────────────────────────


class TestFailClosedReadiness:
    def test_not_ready_raises_typed_error(self):
        from backend.pipeline.orchestrator.readiness import (
            ProviderUnavailableError,
            enforce_required_provider_readiness,
        )
        fake_pf = SimpleNamespace(
            ready=False, errors=["endpoint unreachable"], model_id="x",
            context_length=0, max_context_length=0,
            had_to_load=False, had_to_reload=False, evicted_models=[],
        )
        mgr = MagicMock()
        mgr.preflight_check.return_value = fake_pf
        with patch(
            "backend.pipeline.research.LMStudioManager", return_value=mgr,
        ), pytest.raises(ProviderUnavailableError, match="endpoint unreachable"):
            enforce_required_provider_readiness(MagicMock())

    def test_preflight_exception_raises_typed_error(self):
        from backend.pipeline.orchestrator.readiness import (
            ProviderUnavailableError,
            enforce_required_provider_readiness,
        )
        mgr = MagicMock()
        mgr.preflight_check.side_effect = OSError("boom")
        with patch(
            "backend.pipeline.research.LMStudioManager", return_value=mgr,
        ), pytest.raises(ProviderUnavailableError, match="boom"):
            enforce_required_provider_readiness(MagicMock())

    def test_ready_returns_manager_and_preflight(self):
        from backend.pipeline.orchestrator.readiness import (
            enforce_required_provider_readiness,
        )
        fake_pf = SimpleNamespace(
            ready=True, errors=[], model_id="qwen", context_length=8192,
            max_context_length=8192, had_to_load=False,
            had_to_reload=False, evicted_models=[],
        )
        mgr = MagicMock()
        mgr.preflight_check.return_value = fake_pf
        with patch(
            "backend.pipeline.research.LMStudioManager", return_value=mgr,
        ):
            m, pf = enforce_required_provider_readiness(MagicMock())
        assert m is mgr and pf.model_id == "qwen"

    def test_required_determination_from_registry(
        self, monkeypatch, tmp_path,
    ):
        from backend.pipeline.orchestrator import readiness as rmod

        settings = MagicMock()
        settings.default_provider = "openai"
        settings.capability_registry_path = None
        settings.readiness_probe_stage = None
        # A present registry file (CI has none by default).
        reg = tmp_path / "data" / "model_certification"
        reg.mkdir(parents=True)
        (reg / "production_registry.yaml").write_text("models: {}")
        monkeypatch.chdir(tmp_path)

        def _candidates(self, stage):
            return [SimpleNamespace(provider="lmstudio")]

        monkeypatch.setattr(
            "backend.pipeline.routing.certified_lookup"
            ".CertifiedCapabilityLookup.get_candidates_for_stage",
            _candidates,
        )
        assert rmod.lmstudio_required_for_run(settings) is True

        settings.default_provider = "lmstudio"
        assert rmod.lmstudio_required_for_run(settings) is True

    def test_registry_missing_fails_closed(self, monkeypatch, tmp_path):
        """Q2 review P1: a missing registry means UNKNOWN — never
        silently not-required."""
        from backend.pipeline.orchestrator.readiness import (
            ProviderUnavailableError,
            lmstudio_required_for_run,
        )

        monkeypatch.chdir(tmp_path)  # no data/model_certification here
        settings = MagicMock()
        settings.default_provider = "openai"
        settings.capability_registry_path = None
        settings.readiness_probe_stage = None
        with pytest.raises(
            ProviderUnavailableError, match="registry missing",
        ):
            lmstudio_required_for_run(settings)

    def test_registry_parse_error_fails_closed(
        self, monkeypatch, tmp_path,
    ):
        from backend.pipeline.orchestrator.readiness import (
            ProviderUnavailableError,
            lmstudio_required_for_run,
        )

        reg = tmp_path / "data" / "model_certification"
        reg.mkdir(parents=True)
        (reg / "production_registry.yaml").write_text("models: {}")
        monkeypatch.chdir(tmp_path)

        def _boom(self, stage):
            raise ValueError("yaml corrupt")

        monkeypatch.setattr(
            "backend.pipeline.routing.certified_lookup"
            ".CertifiedCapabilityLookup.get_candidates_for_stage",
            _boom,
        )
        settings = MagicMock()
        settings.default_provider = "openai"
        settings.capability_registry_path = None
        settings.readiness_probe_stage = None
        with pytest.raises(
            ProviderUnavailableError, match="registry lookup failed",
        ):
            lmstudio_required_for_run(settings)

    def test_coordinator_terminalizes_transport_failure(self):
        """Q2 review P1: an exhausted gateway transport failure sets
        the typed outcome — no false SUCCEEDED for non-autonomous
        runs."""
        from unittest.mock import patch

        from backend.pipeline.gateway.transport import (
            GatewayTransportError,
        )
        from backend.pipeline.orchestrator.run_coordinator import (
            RunCoordinator,
        )
        from backend.pipeline.result import PipelineOutcome, PipelineResult

        coord = object.__new__(RunCoordinator)
        orch = MagicMock()
        orch._strategy_config.stages = {
            "gap_analysis": MagicMock(enabled=True),
        }
        orch._strategy_name = "deep_research"
        orch._last_stage_retries = 0
        orch._lifecycle.doom_detected = False
        orch._settings.heartbeat_enabled = False
        orch._services.cross_stage_ctx = None

        async def _prep(ctx_, name_):
            return ctx_

        orch._compaction.prepare_context = _prep
        coord._orch = orch

        result = PipelineResult()
        result.gaps = [SimpleNamespace(title="g")]

        stage = MagicMock()
        stage.name = "gap_analysis"

        async def _execute_with_retry(*a, **kw):
            raise GatewayTransportError(
                "gap_analysis", "dead endpoint",
            )

        orch._execute_stage_with_retry = _execute_with_retry

        async def _no_model_load(*a, **kw):
            return None

        with patch.object(
            RunCoordinator, "_ensure_model_loaded", _no_model_load,
        ), patch(
            "backend.pipeline.stages.ExportStage", MagicMock(),
        ):
            asyncio.run(
                coord.execute_stage_loop(
                    [stage], MagicMock(), result, MagicMock(),
                    "r", "d", None,
                )
            )

        assert result.outcome == PipelineOutcome.FAILED_EXECUTION
        assert result.terminal_stage == "gap_analysis"
        assert "gateway transport failure" in result.terminal_reason


# ── Q2-2: transport-failure identity ────────────────────────────────────────


def _gateway_with_call(exc: Exception) -> MagicMock:
    gw = MagicMock()
    gw.call = AsyncMock(side_effect=exc)
    return gw


class TestGatewayTransportIdentity:
    def test_gateway_call_raises_typed_on_provider_failure(self):
        from backend.pipeline.gateway.gateway import LLMGateway

        gw = object.__new__(LLMGateway)
        gw._budget_authority = None
        gw._smart_router = None
        gw._routing_mode = "disabled"
        gw._enforced_stages = []
        gw._resolve_model = MagicMock()
        gw._log_call = MagicMock()
        gw._circuit = MagicMock()
        gw._circuit.check = MagicMock()
        executor = MagicMock()
        executor.execute = AsyncMock(
            side_effect=ConnectionError("refused")
        )
        gw._provider_fn = executor.execute
        gw._budgeter = MagicMock()
        gw._budgeter.check = MagicMock(
            return_value=MagicMock(approved=True, reserved_tokens=0),
        )
        gw._executor = executor
        gw._default_model = "m"
        from backend.pipeline.gateway.gateway import LLMRequest

        with pytest.raises(GatewayTransportError, match="refused"):
            asyncio.run(gw.call(LLMRequest(task="t", messages=[])))

    def test_gateway_provider_propagates_typed_error(self):
        from backend.pipeline.gateway.gateway_provider import GatewayProvider

        gw = _gateway_with_call(
            GatewayTransportError("complete", "dead endpoint")
        )
        inner = MagicMock()
        inner.complete = AsyncMock(return_value="should-not-be-used")
        provider = GatewayProvider(gateway=gw, inner_provider=inner, stage="s")
        with pytest.raises(GatewayTransportError):
            asyncio.run(provider.complete([{"role": "user", "content": "q"}]))
        inner.complete.assert_not_awaited()

    def test_gateway_provider_propagates_on_usage_path(self):
        from backend.pipeline.gateway.gateway_provider import GatewayProvider

        gw = _gateway_with_call(
            GatewayTransportError("structured", "timeout")
        )
        inner = MagicMock()
        inner.structured_output_with_usage = AsyncMock(return_value=None)
        provider = GatewayProvider(gateway=gw, inner_provider=inner, stage="s")
        with pytest.raises(GatewayTransportError):
            asyncio.run(
                provider.structured_output_with_usage(
                    [{"role": "user", "content": "q"}], {"type": "object"},
                )
            )
        inner.structured_output_with_usage.assert_not_awaited()


# ── Q2-3: autonomous false-SUCCEEDED closure ────────────────────────────────


class TestAutonomousFalseSucceeded:
    def _finalize(self, params, ideas, gaps):
        from backend.pipeline.orchestrator.stage_lifecycle import (
            StageLifecycle,
        )
        from backend.pipeline.result import PipelineResult

        lifecycle = object.__new__(StageLifecycle)
        lifecycle._persistence = MagicMock()
        lifecycle._notifier = None
        lifecycle._provider = MagicMock()
        lifecycle._cost_tracker = None
        lifecycle._integration = None
        lifecycle._settings = MagicMock()
        lifecycle._settings.run_artifacts_enabled = False
        lifecycle._settings.session_management_enabled = False

        class _Dead:
            def __getattr__(self, name):
                return None

        class _Hooks:
            async def dispatch_sync_safe(self, *a, **k):
                return None

        class _WorldModel:
            async def update_from_run(self, *a, **k):
                return None

        lifecycle._services = _Dead()
        lifecycle._services.hooks = _Hooks()
        lifecycle._services.world_model = _WorldModel()
        lifecycle._processor = MagicMock()
        result = PipelineResult()
        result.ideas = ideas
        result.gaps = gaps
        asyncio.run(lifecycle.post_pipeline_finalize(
            result=result,
            ctx=MagicMock(),
            run_id="r",
            domain="d",
            strategy="deep_research",
            params=params,
            db_run_id=None,
            session_id=None,
            ideas_per=1,
            rounds=1,
        ))
        return result

    def test_autonomous_missing_design_is_typed_failure(self):
        """The exact 3D shape: gaps exist, ideas empty, autonomous
        enabled, design absent — must NOT finalize as SUCCEEDED."""
        result = self._finalize(
            params={"autonomous_experiment_enabled": True},
            ideas=[],
            gaps=[SimpleNamespace(title="g")],
        )
        from backend.pipeline.result import PipelineOutcome

        assert result.outcome == PipelineOutcome.FAILED_OUTPUT_CONTRACT
        assert result.terminal_stage == "autonomous_design"
        assert "not produced" in result.terminal_reason

    def test_autonomous_designed_still_succeeds(self):
        result = self._finalize(
            params={
                "autonomous_experiment_enabled": True,
                "autonomous_experiment_design": {"status": "designed"},
            },
            ideas=[SimpleNamespace(score=0.8, proposed_method="m")],
            gaps=[SimpleNamespace(title="g")],
        )
        from backend.pipeline.result import PipelineOutcome

        assert result.outcome == PipelineOutcome.SUCCEEDED

    def test_nonautonomous_zero_ideas_still_falls_to_legacy_path(self):
        """Non-autonomous runs keep the existing semantics (legacy
        empty-marking / success) — the closure is scoped to autonomous
        runs per the Q2 authorization."""
        result = self._finalize(
            params={},
            ideas=[],
            gaps=[SimpleNamespace(title="g")],
        )
        from backend.pipeline.result import PipelineOutcome

        assert result.outcome == PipelineOutcome.SUCCEEDED
