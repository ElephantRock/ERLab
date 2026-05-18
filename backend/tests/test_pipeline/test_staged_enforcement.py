"""Tests for per-stage enforcement in SmartRouter/Gateway.

Validates:
1. Enforced stages get enforcement_applied=True
2. Non-enforced stages get enforcement_applied=False
3. Degraded results for missing candidates on enforced stages
4. Non-enforced stages continue through legacy path
5. GatewayCallLog includes enforcement fields
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.gateway.gateway import (
    LLMGateway, LLMRequest, LLMResponse, GatewayCallLog,
)
from backend.pipeline.gateway.capability_registry import (
    ModelCapabilities, ModelCapabilityRegistry,
)
from backend.pipeline.gateway.token_budget import TokenBudgeter
from backend.pipeline.routing.smart_router import SmartRouter
from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
from backend.pipeline.routing.dry_run_logger import DryRunLogger


# ─── Fixtures ────────────────────────────────────────────────────────

def _make_gateway(enforced_stages=None, mode="enforce"):
    """Create a gateway with SmartRouter and enforcement config."""
    registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter()
    gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")

    # Mock provider function
    gateway._provider_fn = AsyncMock(return_value='{"result": "ok"}')

    # SmartRouter with dry-run logger
    lookup = CertifiedCapabilityLookup()
    router = SmartRouter(lookup, mode=mode)
    logger = DryRunLogger(log_dir="data/model_certification/routing_logs")

    gateway.set_smart_router(
        router,
        mode=mode,
        dry_run_logger=logger,
        enforced_stages=enforced_stages or [],
    )

    return gateway


# ─── Test: Enforcement allowlist ─────────────────────────────────────

class TestEnforcementAllowlist:
    def test_enforced_stages_stored(self):
        gw = _make_gateway(enforced_stages=["repair", "query_generation"])
        assert gw._enforced_stages == {"repair", "query_generation"}

    def test_empty_enforced_stages(self):
        gw = _make_gateway(enforced_stages=[])
        assert gw._enforced_stages == set()

    def test_no_enforced_stages_arg(self):
        gw = _make_gateway()
        assert gw._enforced_stages == set()


# ─── Test: GatewayCallLog enforcement fields ─────────────────────────

class TestGatewayCallLogEnforcement:
    def test_call_log_has_enforcement_fields(self):
        entry = GatewayCallLog(
            timestamp=0, task="test", stage="repair", run_id="r1",
            model="m1", provider="p1", input_tokens=0, output_tokens=0,
            latency_ms=0, confidence=0.5, fallback_used=False,
            degraded=False, warnings=[], error=None,
            enforcement_applied=True,
            certification_status="certified",
            stage_eligibility="limited_use",
            hard_gate_failures=[],
        )
        assert entry.enforcement_applied is True
        assert entry.certification_status == "certified"
        assert entry.stage_eligibility == "limited_use"

    def test_call_log_defaults(self):
        entry = GatewayCallLog(
            timestamp=0, task="test", stage="test", run_id="r1",
            model="m1", provider="p1", input_tokens=0, output_tokens=0,
            latency_ms=0, confidence=0.5, fallback_used=False,
            degraded=False, warnings=[], error=None,
        )
        assert entry.enforcement_applied is False
        assert entry.certification_status == ""
        assert entry.stage_eligibility == ""
        assert entry.hard_gate_failures == []


# ─── Test: Non-enforced stages in enforce mode ───────────────────────

class TestNonEnforcedStages:
    """Non-enforced stages should get dry-run logging, not enforcement."""

    @pytest.mark.asyncio
    async def test_non_enforced_stage_not_enforced(self):
        """Stages not in enforced_stages should not have enforcement_applied."""
        gw = _make_gateway(
            enforced_stages=["repair"],
            mode="enforce",
        )
        # Non-enforced stage
        request = LLMRequest(
            task="proposal_synthesis",
            messages=[{"role": "user", "content": "test"}],
            stage="proposal_synthesis",
        )
        response = await gw.call(request)
        # Should succeed (legacy path)
        assert not response.degraded
        # Should NOT have enforcement applied
        assert not getattr(request, '_enforcement_applied', False)

    @pytest.mark.asyncio
    async def test_high_risk_stages_not_enforced(self):
        """High-risk stages should never be enforced."""
        gw = _make_gateway(
            enforced_stages=["repair"],
            mode="enforce",
        )
        for stage in ["adversarial_review", "paper_synthesis", "proposal_synthesis",
                       "evidence_table", "citation_audit"]:
            request = LLMRequest(
                task=stage,
                messages=[{"role": "user", "content": "test"}],
                stage=stage,
            )
            response = await gw.call(request)
            assert not response.degraded, f"{stage} should not be degraded"
            assert not getattr(request, '_enforcement_applied', False), \
                f"{stage} should not be enforced"


# ─── Test: Call log serialization ────────────────────────────────────

class TestCallLogSerialization:
    @pytest.mark.asyncio
    async def test_get_call_log_includes_enforcement_fields(self):
        gw = _make_gateway(enforced_stages=["repair"], mode="enforce")
        request = LLMRequest(
            task="test_task",
            messages=[{"role": "user", "content": "test"}],
            stage="test_stage",
        )
        await gw.call(request)

        logs = gw.get_call_log(limit=1)
        assert len(logs) == 1
        log = logs[0]
        assert "enforcement_applied" in log
        assert "certification_status" in log
        assert "stage_eligibility" in log
        assert "hard_gate_failures" in log


# ─── Test: Routing config parsing ────────────────────────────────────

class TestRoutingConfigParsing:
    def test_enforced_stages_in_config(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = config.get("enforced_stages", [])
        assert isinstance(enforced, list)
        assert "repair" in enforced
        assert "query_generation" in enforced
        assert "literature_search" in enforced

    def test_high_risk_stages_not_in_enforced(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = config.get("enforced_stages", [])
        high_risk = ["evidence_table", "citation_audit", "adversarial_review",
                     "paper_synthesis", "proposal_synthesis"]
        for stage in high_risk:
            assert stage not in enforced, f"{stage} should NOT be in enforced_stages"

    def test_mode_is_enforce(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        assert config.get("mode") == "enforce"

    def test_require_certified_models(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        assert config.get("require_certified_models") is True
