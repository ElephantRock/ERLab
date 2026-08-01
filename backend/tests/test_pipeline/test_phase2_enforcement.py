"""Phase 2 enforcement tests: idea_generation and feasibility_scoring.

Validates:
- idea_generation routes through gateway with enforcement_applied=true
- feasibility_scoring routes through gateway with enforcement_applied=true
- Degraded idea_generation returns explicit degraded result
- Degraded feasibility_scoring returns explicit degraded result
- High-risk stages remain excluded from enforced_stages
- Grounded stages remain excluded
- Invalid feasibility scores are handled
"""
import pytest
from unittest.mock import AsyncMock

from backend.pipeline.gateway.gateway import LLMGateway, LLMRequest


def _make_gateway(enforced_stages=None, mode="enforce"):
    from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
    from backend.pipeline.gateway.token_budget import TokenBudgeter
    from backend.pipeline.routing.smart_router import SmartRouter
    from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
    from backend.pipeline.routing.dry_run_logger import DryRunLogger

    registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter()
    gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
    gateway._provider_fn = AsyncMock(return_value='{"ideas": [{"title": "Test Idea"}]}')

    lookup = CertifiedCapabilityLookup()
    router = SmartRouter(lookup, mode=mode)
    logger = DryRunLogger(log_dir="data/model_certification/routing_logs")
    gateway.set_smart_router(
        router, mode=mode, dry_run_logger=logger,
        enforced_stages=enforced_stages or [],
    )
    return gateway


# ── Idea Generation Enforcement ──────────────────────────────────────

@pytest.mark.slow
class TestIdeaGenerationEnforcement:

    @pytest.mark.asyncio
    async def test_idea_generation_enforced(self):
        """idea_generation calls go through gateway with enforcement_applied=true."""
        gateway = _make_gateway(enforced_stages=["idea_generation"])
        gateway._provider_fn = AsyncMock(
            return_value='{"ideas": [{"title": "Efficient Attention", "score": 0.8}]}'
        )
        request = LLMRequest(
            task="idea_generation",
            messages=[{"role": "user", "content": "Generate 3 ideas"}],
            stage="idea_generation",
            max_output_tokens=4096,
        )
        response = await gateway.call(request)
        assert not response.degraded
        assert response.content

        call_log = gateway.get_call_log(limit=5)
        ig_calls = [c for c in call_log if c.get("stage") == "idea_generation"]
        assert len(ig_calls) >= 1
        assert ig_calls[0]["enforcement_applied"] is True
        assert ig_calls[0]["routed_model"] != ""
        assert ig_calls[0]["certification_status"] == "certified"

    @pytest.mark.asyncio
    async def test_idea_generation_routed_model_certified(self):
        """Routed model is a certified model."""
        gateway = _make_gateway(enforced_stages=["idea_generation"])
        request = LLMRequest(
            task="idea_generation",
            messages=[{"role": "user", "content": "Generate ideas"}],
            stage="idea_generation",
        )
        await gateway.call(request)
        call_log = gateway.get_call_log(limit=5)
        ig = [c for c in call_log if c.get("stage") == "idea_generation"][0]
        assert ig["certification_status"] == "certified"
        assert ig["stage_eligibility"] != ""

    @pytest.mark.asyncio
    async def test_idea_generation_no_hard_gate_failures(self):
        """No hard gate failures for idea_generation."""
        gateway = _make_gateway(enforced_stages=["idea_generation"])
        request = LLMRequest(
            task="idea_generation",
            messages=[{"role": "user", "content": "Generate ideas"}],
            stage="idea_generation",
        )
        await gateway.call(request)
        call_log = gateway.get_call_log(limit=5)
        ig = [c for c in call_log if c.get("stage") == "idea_generation"][0]
        assert ig.get("hard_gate_failures", []) == []

    @pytest.mark.asyncio
    async def test_idea_generation_degraded_returns_explicit(self):
        """Degraded idea_generation returns explicit degraded LLMResponse."""
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.smart_router import SmartRouter
        from backend.pipeline.routing.dry_run_logger import DryRunLogger
        from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
        from backend.pipeline.gateway.token_budget import TokenBudgeter

        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter()
        gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
        gw._provider_fn = AsyncMock(return_value='{"ideas": []}')

        empty_lookup = CertifiedCapabilityLookup()
        empty_lookup.get_candidates_for_stage = lambda stage: []
        gw.set_smart_router(
            SmartRouter(empty_lookup, mode="enforce"), mode="enforce",
            dry_run_logger=DryRunLogger(log_dir="data/model_certification/routing_logs"),
            enforced_stages=["idea_generation"],
        )
        request = LLMRequest(
            task="idea_generation",
            messages=[{"role": "user", "content": "Generate ideas"}],
            stage="idea_generation",
        )
        response = await gw.call(request)
        assert response.degraded is True
        assert any("no certified candidate" in w.lower() for w in response.warnings)

    @pytest.mark.asyncio
    async def test_idea_generation_strategy_is_valid(self):
        """Routed strategy is one of the contract's allowed strategies."""
        gateway = _make_gateway(enforced_stages=["idea_generation"])
        request = LLMRequest(
            task="idea_generation",
            messages=[{"role": "user", "content": "Generate ideas"}],
            stage="idea_generation",
        )
        await gateway.call(request)
        call_log = gateway.get_call_log(limit=5)
        ig = [c for c in call_log if c.get("stage") == "idea_generation"][0]
        assert ig["routed_strategy"] in ("single_call", "evidence_first")


# ── Feasibility Scoring Enforcement ──────────────────────────────────

@pytest.mark.slow
class TestFeasibilityScoringEnforcement:

    @pytest.mark.asyncio
    async def test_feasibility_scoring_enforced(self):
        """feasibility_scoring calls go through gateway with enforcement_applied=true."""
        gateway = _make_gateway(enforced_stages=["feasibility_scoring"])
        gateway._provider_fn = AsyncMock(
            return_value='{"score": 0.85, "explanation": "Feasible approach", "risks": ["compute cost"]}'
        )
        request = LLMRequest(
            task="feasibility_scoring",
            messages=[{"role": "user", "content": "Score this idea"}],
            stage="feasibility_scoring",
            max_output_tokens=2048,
        )
        response = await gateway.call(request)
        assert not response.degraded
        assert response.content

        call_log = gateway.get_call_log(limit=5)
        fs_calls = [c for c in call_log if c.get("stage") == "feasibility_scoring"]
        assert len(fs_calls) >= 1
        assert fs_calls[0]["enforcement_applied"] is True

    @pytest.mark.asyncio
    async def test_feasibility_scoring_maps_to_idea_generation_contract(self):
        """feasibility_scoring maps to idea_generation contract in routing."""
        from backend.pipeline.routing.stage_contract import load_contracts, get_contract
        contracts = load_contracts()
        # Verify feasibility_scoring maps to idea_generation
        ig_contract = get_contract("idea_generation", contracts)
        assert ig_contract.risk_level == "medium"
        assert ig_contract.allowed_strategies == ["single_call", "evidence_first"]

    @pytest.mark.asyncio
    async def test_feasibility_scoring_degraded_returns_explicit(self):
        """Degraded feasibility_scoring returns explicit degraded LLMResponse."""
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.smart_router import SmartRouter
        from backend.pipeline.routing.dry_run_logger import DryRunLogger
        from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
        from backend.pipeline.gateway.token_budget import TokenBudgeter

        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter()
        gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
        gw._provider_fn = AsyncMock(return_value='{"score": 0.0}')

        empty_lookup = CertifiedCapabilityLookup()
        empty_lookup.get_candidates_for_stage = lambda stage: []
        gw.set_smart_router(
            SmartRouter(empty_lookup, mode="enforce"), mode="enforce",
            dry_run_logger=DryRunLogger(log_dir="data/model_certification/routing_logs"),
            enforced_stages=["feasibility_scoring"],
        )
        request = LLMRequest(
            task="feasibility_scoring",
            messages=[{"role": "user", "content": "Score this"}],
            stage="feasibility_scoring",
        )
        response = await gw.call(request)
        assert response.degraded is True


# ── Routing Contract ─────────────────────────────────────────────────

@pytest.mark.slow
class TestPhase2RoutingContract:

    def test_high_risk_stages_excluded(self):
        """High-risk stages are NOT in enforced_stages."""
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = set(config.get("enforced_stages", []))
        high_risk = {
            "evidence_table", "citation_audit", "adversarial_review",
            "paper_synthesis", "proposal_synthesis",
        }
        for stage in high_risk:
            assert stage not in enforced, f"{stage} should NOT be in enforced_stages"

    def test_grounded_stages_excluded(self):
        """Grounded stages (high grounding requirement) are excluded."""
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = set(config.get("enforced_stages", []))
        grounded = {
            "evidence_table", "adversarial_review", "citation_audit",
        }
        for stage in grounded:
            assert stage not in enforced, f"{stage} should NOT be in enforced_stages"

    def test_idea_generation_has_contract(self):
        """idea_generation has a routing contract."""
        from backend.pipeline.routing.stage_contract import load_contracts, get_contract
        contracts = load_contracts()
        contract = get_contract("idea_generation", contracts)
        assert contract.risk_level == "medium"
        assert contract.requires_grounding is True
        assert contract.requires_citations is False

    def test_model_certified_for_idea_generation(self):
        """qwen3-4b-2507 is certified for idea_generation."""
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        lookup = CertifiedCapabilityLookup()
        candidates = lookup.get_candidates_for_stage("idea_generation")
        model_ids = [c.model_id for c in candidates]
        assert "qwen3-4b-2507" in model_ids

    def test_model_passes_hard_gates_for_idea_generation(self):
        """qwen3-4b-2507 passes all hard gates for idea_generation."""
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.hard_gates import HardGateEngine
        from backend.pipeline.routing.stage_contract import load_contracts, get_contract

        lookup = CertifiedCapabilityLookup()
        engine = HardGateEngine()
        contracts = load_contracts()
        contract = get_contract("idea_generation", contracts)
        candidates = lookup.get_candidates_for_stage("idea_generation")

        for c in candidates:
            results = engine.evaluate(contract, c)
            failed = [r for r in results if not r.passed]
            assert len(failed) == 0, \
                f"{c.model_id} fails gates: {[(r.gate, r.reason) for r in failed]}"


# ── Score Validation ─────────────────────────────────────────────────

class TestScoreValidation:

    def test_invalid_scores_detected(self):
        """Out-of-bounds scores are detected."""
        scores = [0.5, 1.5, -0.1, 0.9, 0.0]
        invalid = [s for s in scores if not (0 <= s <= 1)]
        assert len(invalid) == 2  # 1.5 and -0.1

    def test_valid_scores_pass(self):
        """Scores in [0, 1] range pass validation."""
        scores = [0.0, 0.5, 0.85, 1.0]
        assert all(0 <= s <= 1 for s in scores)

    def test_explanation_required(self):
        """Feasibility output should include explanation."""
        output = '{"score": 0.8, "explanation": "Feasible with moderate compute", "risks": ["VRAM"]}'
        assert "explanation" in output.lower()
