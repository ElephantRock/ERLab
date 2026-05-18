"""Tests for real pipeline integration of SmartRouter enforcement.

Validates:
- JSON extraction with LLM repair fallback (stage=repair)
- Literature search query expansion (stage=query_generation)
- Enforcement behavior for both paths
- Non-enforced stages remain dry-run
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field

from backend.pipeline.utils.json_extraction import (
    extract_json,
    extract_json_with_llm_repair,
    RepairLog,
    JsonExtractionError,
)


# ─── Fixtures ────────────────────────────────────────────────────────

def _make_gateway(enforced_stages=None, mode="enforce"):
    """Create a gateway with SmartRouter enforcement."""
    from backend.pipeline.gateway.gateway import LLMGateway
    from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
    from backend.pipeline.gateway.token_budget import TokenBudgeter
    from backend.pipeline.routing.smart_router import SmartRouter
    from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
    from backend.pipeline.routing.dry_run_logger import DryRunLogger

    registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter()
    gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
    gateway._provider_fn = AsyncMock(return_value='{"title": "Repaired", "authors": []}')

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


# ─── Test: extract_json_with_llm_repair ──────────────────────────────

class TestExtractJsonWithLlmRepair:
    """Test the async JSON extraction with LLM repair fallback."""

    @pytest.mark.asyncio
    async def test_mechanical_succeeds_no_llm_call(self):
        """When mechanical extraction works, LLM repair is NOT called."""
        text = '{"title": "Test", "authors": ["Alice"]}'
        result, log = await extract_json_with_llm_repair(text, gateway=None)
        assert result["title"] == "Test"
        assert log.repair_method == "mechanical"
        assert log.repair_attempted is False

    @pytest.mark.asyncio
    async def test_mechanical_fails_llm_repair_succeeds(self):
        """When mechanical fails, LLM repair is attempted."""
        broken = '{"title": "Test", "authors": ["Alice", missing'
        gateway = _make_gateway(enforced_stages=["repair"], mode="enforce")
        gateway._provider_fn = AsyncMock(return_value='{"title": "Test", "authors": ["Alice"]}')

        result, log = await extract_json_with_llm_repair(
            broken, gateway=gateway, run_id="test"
        )
        assert result["title"] == "Test"
        assert log.repair_method == "llm_repair"
        assert log.repair_attempted is True
        assert log.enforcement_applied is True

    @pytest.mark.asyncio
    async def test_schema_validation_on_repaired_output(self):
        """Repaired output is validated against schema."""
        broken = '{"title": "Test", bad_field'
        gateway = _make_gateway(enforced_stages=["repair"], mode="enforce")
        gateway._provider_fn = AsyncMock(
            return_value='{"title": "Test", "year": 2024}'
        )

        schema = {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "year": {"type": "number"},
            },
        }

        result, log = await extract_json_with_llm_repair(
            broken, gateway=gateway, schema=schema, run_id="test"
        )
        assert log.repair_method == "llm_repair"
        assert log.schema_valid_after_repair is True

    @pytest.mark.asyncio
    async def test_degraded_repair_returns_failure(self):
        """Degraded LLM repair returns empty dict, not fake data."""
        broken = '{"title": "Test", missing'

        # Empty lookup → no certified candidates → degraded
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.smart_router import SmartRouter
        from backend.pipeline.gateway.gateway import LLMGateway
        from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
        from backend.pipeline.gateway.token_budget import TokenBudgeter
        from backend.pipeline.routing.dry_run_logger import DryRunLogger

        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter()
        gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
        gw._provider_fn = AsyncMock(return_value='{"title": "Fixed"}')

        empty_lookup = CertifiedCapabilityLookup()
        empty_lookup.get_candidates_for_stage = lambda stage: []
        empty_router = SmartRouter(empty_lookup, mode="enforce")

        gw.set_smart_router(
            empty_router, mode="enforce",
            dry_run_logger=DryRunLogger(log_dir="data/model_certification/routing_logs"),
            enforced_stages=["repair"],
        )

        result, log = await extract_json_with_llm_repair(broken, gateway=gw)
        assert result == {}
        assert log.repair_method == "failed"
        assert log.degraded is True

    @pytest.mark.asyncio
    async def test_no_gateway_returns_empty(self):
        """Without gateway, LLM repair is skipped entirely."""
        broken = '{not valid json at all'
        result, log = await extract_json_with_llm_repair(broken, gateway=None)
        assert result == {}
        assert log.repair_method == "failed"
        assert log.repair_error == "no_gateway_provided"

    @pytest.mark.asyncio
    async def test_strict_mode_raises(self):
        """Strict mode raises JsonExtractionError on total failure."""
        broken = '{not valid'
        with pytest.raises(JsonExtractionError):
            await extract_json_with_llm_repair(broken, gateway=None, strict=True)

    @pytest.mark.asyncio
    async def test_original_json_preserved_in_log(self):
        """Original invalid JSON is preserved in RepairLog."""
        broken = '{"title": "X", "authors": [missing'
        gateway = _make_gateway(enforced_stages=["repair"])
        gateway._provider_fn = AsyncMock(return_value='{"title": "X", "authors": []}')

        _, log = await extract_json_with_llm_repair(broken, gateway=gateway)
        assert broken[:500] == log.original_invalid_json

    @pytest.mark.asyncio
    async def test_enforcement_fields_captured(self):
        """Enforcement fields are captured in RepairLog."""
        broken = '{"broken'
        gateway = _make_gateway(enforced_stages=["repair"])
        gateway._provider_fn = AsyncMock(return_value='{"repaired": true}')

        _, log = await extract_json_with_llm_repair(broken, gateway=gateway, run_id="test")
        assert log.enforcement_applied is True
        assert "routed_model" in log.llm_repair_log_fields
        assert "certification_status" in log.llm_repair_log_fields


# ─── Test: LLMQueryGenerator integration ────────────────────────────

class TestQueryGenerationIntegration:
    """Test query generation in the context of literature search."""

    @pytest.mark.asyncio
    async def test_query_generation_enforced(self):
        """query_generation calls go through gateway with enforcement."""
        from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator

        gateway = _make_gateway(enforced_stages=["query_generation"])
        gateway._provider_fn = AsyncMock(
            return_value='["query 1", "query 2", "query 3"]'
        )

        gen = LLMQueryGenerator(gateway)
        queries = await gen.generate_queries(
            domain="AI", topic="transformers", run_id="test"
        )

        assert len(queries) == 3
        call_log = gateway.get_call_log(limit=5)
        qg_calls = [c for c in call_log if c.get("stage") == "query_generation"]
        assert len(qg_calls) >= 1
        assert qg_calls[0]["enforcement_applied"] is True

    @pytest.mark.asyncio
    async def test_llm_returns_valid_queries(self):
        """LLMQueryGenerator returns all valid JSON array entries."""
        from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator

        gateway = _make_gateway(enforced_stages=["query_generation"])
        gateway._provider_fn = AsyncMock(
            return_value='["machine learning efficiency", "neural architecture search", "model compression"]'
        )

        gen = LLMQueryGenerator(gateway)
        queries = await gen.generate_queries(
            domain="AI", topic="test", run_id="test"
        )

        assert len(queries) == 3
        assert "machine learning efficiency" in queries

    @pytest.mark.asyncio
    async def test_degraded_falls_back_to_original(self):
        """Degraded query generation returns empty list, stage uses original queries."""
        from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator
        from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
        from backend.pipeline.routing.smart_router import SmartRouter
        from backend.pipeline.gateway.gateway import LLMGateway
        from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
        from backend.pipeline.gateway.token_budget import TokenBudgeter
        from backend.pipeline.routing.dry_run_logger import DryRunLogger

        registry = ModelCapabilityRegistry()
        budgeter = TokenBudgeter()
        gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
        gw._provider_fn = AsyncMock(return_value='[]')

        empty_lookup = CertifiedCapabilityLookup()
        empty_lookup.get_candidates_for_stage = lambda stage: []
        empty_router = SmartRouter(empty_lookup, mode="enforce")

        gw.set_smart_router(
            empty_router, mode="enforce",
            dry_run_logger=DryRunLogger(log_dir="data/model_certification/routing_logs"),
            enforced_stages=["query_generation"],
        )

        gen = LLMQueryGenerator(gw)
        queries = await gen.generate_queries(domain="AI", topic="test")
        assert queries == []


# ─── Test: LiteratureSearchStage query filtering ─────────────────────

class TestLiteratureSearchQueryFiltering:
    """Test query filtering logic that runs in LiteratureSearchStage."""

    def test_short_queries_rejected(self):
        """Queries shorter than 5 chars are rejected."""
        queries = ["AI", "x", "valid query about transformers"]
        # Simulate the filtering logic from LiteratureSearchStage
        accepted = [q for q in queries if q.strip() and len(q.strip()) >= 5 and len(q.strip()) <= 200]
        assert len(accepted) == 1
        assert "valid query about transformers" in accepted

    def test_long_queries_rejected(self):
        """Queries longer than 200 chars are rejected."""
        queries = ["short query", "x" * 201]
        accepted = [q for q in queries if q.strip() and len(q.strip()) >= 5 and len(q.strip()) <= 200]
        assert len(accepted) == 1

    def test_empty_queries_rejected(self):
        """Empty queries are rejected."""
        queries = ["", "   ", "valid query"]
        accepted = [q for q in queries if q.strip() and len(q.strip()) >= 5 and len(q.strip()) <= 200]
        assert len(accepted) == 1

    def test_duplicate_queries_rejected(self):
        """Duplicate queries (case-insensitive) are rejected."""
        existing = {"machine learning", "neural networks"}
        new_queries = ["Machine Learning", "deep learning"]
        accepted = [q for q in new_queries if q.lower().strip() not in existing]
        assert len(accepted) == 1
        assert "deep learning" in accepted


# ─── Test: Routing contract ──────────────────────────────────────────

class TestRoutingContractEnforcement:
    """Verify only repair and query_generation are enforced."""

    def test_only_repair_and_query_generation_enforced(self):
        from backend.pipeline.routing.stage_contract import get_smart_router_config
        config = get_smart_router_config()
        enforced = config.get("enforced_stages", [])
        assert set(enforced) == {"repair", "query_generation"}

    @pytest.mark.asyncio
    async def test_high_risk_stages_dry_run(self):
        """High-risk stages remain dry-run even in enforce mode."""
        from backend.pipeline.gateway.gateway import LLMRequest

        gateway = _make_gateway(enforced_stages=["repair", "query_generation"])
        for stage in ["evidence_table", "citation_audit", "adversarial_review",
                      "paper_synthesis", "proposal_synthesis", "idea_generation",
                      "gap_analysis", "feasibility_scoring", "proposal_deepening"]:
            request = LLMRequest(
                task=stage,
                messages=[{"role": "user", "content": "test"}],
                stage=stage,
            )
            response = await gateway.call(request)
            assert not response.degraded, f"{stage} should not be degraded"

            # Check call log for enforcement
            logs = gateway.get_call_log(limit=1)
            assert not logs[0].get("enforcement_applied"), \
                f"{stage} should NOT have enforcement_applied"


# ─── Test: RepairLog dataclass ───────────────────────────────────────

class TestRepairLog:
    def test_defaults(self):
        log = RepairLog()
        assert log.repair_attempted is False
        assert log.repair_method == ""
        assert log.enforcement_applied is False
        assert log.degraded is False
        assert log.schema_valid_after_repair is False
        assert log.original_invalid_json == ""
        assert log.llm_repair_log_fields == {}

    def test_fields_set(self):
        log = RepairLog(
            repair_attempted=True,
            repair_method="llm_repair",
            enforcement_applied=True,
            routed_model="qwen3-4b-2507",
            schema_valid_after_repair=True,
        )
        assert log.repair_method == "llm_repair"
        assert log.enforcement_applied is True
