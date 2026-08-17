"""Tests for per-stage enforcement in SmartRouter/Gateway.

Validates:
1. Enforced stages get enforcement_applied=True
2. Non-enforced stages get enforcement_applied=False
3. Degraded results for missing candidates on enforced stages
4. Non-enforced stages continue through legacy path
5. GatewayCallLog includes enforcement fields
"""
from unittest.mock import AsyncMock

import pytest

from backend.pipeline.gateway.capability_registry import (
    ModelCapabilityRegistry,
)
from backend.pipeline.gateway.gateway import (
    GatewayCallLog,
    LLMGateway,
    LLMRequest,
)
from backend.pipeline.gateway.token_budget import TokenBudgeter
from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
from backend.pipeline.routing.dry_run_logger import DryRunLogger
from backend.pipeline.routing.smart_router import SmartRouter

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
        assert "idea_generation" in enforced
        assert "feasibility_scoring" in enforced
        # literature_search removed: tool-only, no LLM calls
        assert "literature_search" not in enforced

    def test_high_risk_stages_not_in_enforced(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = config.get("enforced_stages", [])
        high_risk = ["evidence_table", "citation_audit", "adversarial_review",
                     "paper_synthesis", "proposal_synthesis", "literature_search"]
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


# ── Test: LLMRepairService and LLMQueryGenerator ────────────────────

@pytest.mark.slow
class TestLLMRepairService:
    """Test LLMRepairService routes through gateway with stage='repair'."""

    @pytest.mark.asyncio
    async def test_repair_routes_through_gateway(self):
        """Repair calls go through gateway with stage='repair'."""
        from backend.pipeline.gateway.llm_repair_and_query import LLMRepairService

        gateway = _make_gateway(enforced_stages=["repair"], mode="enforce")
        # Mock provider to return valid JSON
        gateway._provider_fn = AsyncMock(return_value='{"title": "Fixed", "authors": []}')

        svc = LLMRepairService(gateway)
        result = await svc.repair_json(
            broken_json='{"title": "Test", missing',
            run_id="test",
        )

        assert result is not None
        assert result["title"] == "Fixed"

        # Verify enforcement was applied
        call_log = gateway.get_call_log(limit=5)
        repair_calls = [c for c in call_log if c.get("stage") == "repair"]
        assert len(repair_calls) >= 1
        assert repair_calls[0]["enforcement_applied"] is True

    @pytest.mark.asyncio
    async def test_repair_raises_on_transport_failure(self):
        """Q2: transport failure raises GatewayTransportError through
        the repair service — no silent None on a dead provider."""
        from backend.pipeline.gateway.llm_repair_and_query import (
            LLMRepairService,
        )
        from backend.pipeline.gateway.transport import (
            GatewayTransportError,
        )

        gateway = _make_gateway(enforced_stages=["repair"], mode="enforce")
        gateway._provider_fn = AsyncMock(side_effect=Exception("LLM failed"))

        svc = LLMRepairService(gateway)
        with pytest.raises(GatewayTransportError, match="LLM failed"):
            await svc.repair_json(
                broken_json='{broken',
                run_id="test",
            )


@pytest.mark.slow
class TestLLMQueryGenerator:
    """Test LLMQueryGenerator routes through gateway with stage='query_generation'."""

    @pytest.mark.asyncio
    async def test_query_gen_routes_through_gateway(self):
        """Query generation calls go through gateway with stage='query_generation'."""
        from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator

        gateway = _make_gateway(enforced_stages=["query_generation"], mode="enforce")
        gateway._provider_fn = AsyncMock(
            return_value='["query 1", "query 2", "query 3"]'
        )

        gen = LLMQueryGenerator(gateway)
        queries = await gen.generate_queries(
            domain="CS", topic="test", run_id="test",
        )

        assert len(queries) == 3
        assert "query 1" in queries

        # Verify enforcement was applied
        call_log = gateway.get_call_log(limit=5)
        qg_calls = [c for c in call_log if c.get("stage") == "query_generation"]
        assert len(qg_calls) >= 1
        assert qg_calls[0]["enforcement_applied"] is True

    @pytest.mark.asyncio
    async def test_query_gen_raises_on_transport_failure(self):
        """Q2: transport failure raises GatewayTransportError through
        query generation — no silent [] on a dead provider."""
        from backend.pipeline.gateway.llm_repair_and_query import (
            LLMQueryGenerator,
        )
        from backend.pipeline.gateway.transport import (
            GatewayTransportError,
        )

        gateway = _make_gateway(
            enforced_stages=["query_generation"], mode="enforce",
        )
        gateway._provider_fn = AsyncMock(side_effect=Exception("LLM failed"))

        gen = LLMQueryGenerator(gateway)
        with pytest.raises(GatewayTransportError, match="LLM failed"):
            await gen.generate_queries(
                domain="CS", topic="test", run_id="test",
            )


# ── Test: Degraded result for empty certified candidates ─────────────

class TestDegradedEnforcement:
    """Test degraded result path when no certified candidates available."""

    @pytest.mark.asyncio
    async def test_degraded_when_no_certified_candidates(self):
        """Enforced stage with empty lookup returns degraded LLMResponse."""
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.smart_router import SmartRouter

        gateway = _make_gateway(enforced_stages=["repair"], mode="enforce")
        gateway._provider_fn = AsyncMock(return_value='{"result": "ok"}')

        # Replace with empty lookup
        empty_lookup = CertifiedCapabilityLookup()
        empty_lookup.get_candidates_for_stage = lambda stage: []
        empty_router = SmartRouter(empty_lookup, mode="enforce")

        gateway.set_smart_router(
            empty_router,
            mode="enforce",
            dry_run_logger=gateway._dry_run_logger,
            enforced_stages=["repair"],
        )

        request = LLMRequest(
            task="repair",
            messages=[{"role": "user", "content": "fix json"}],
            stage="repair",
            max_output_tokens=512,
        )

        response = await gateway.call(request)
        assert response.degraded is True
        assert any("no certified candidate" in w.lower() for w in response.warnings)
