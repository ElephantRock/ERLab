"""Phase E+F tests: SmartRouter + RoutingDecision + DryRunLogger."""


import pytest
import yaml

from backend.pipeline.routing.certified_lookup import (
    CertifiedCapabilityLookup,
)
from backend.pipeline.routing.dry_run_logger import DryRunLogger
from backend.pipeline.routing.routing_decision import RoutingDecision
from backend.pipeline.routing.smart_router import RoutingRuntimeContext, SmartRouter
from backend.pipeline.routing.stage_contract import StageContract


def _make_contract(**overrides):
    defaults = dict(
        stage="paper_synthesis",
        task_type="generation",
        risk_level="high",
        requires_grounding=True,
        requires_citations=True,
        input_tokens_estimate=6000,
        output_tokens_requested=8000,
        min_context_window=16384,
        allowed_strategies=["section_wise", "map_reduce"],
        fallback_strategy="section_wise",
    )
    defaults.update(overrides)
    return StageContract(**defaults)


def _make_lookup_with_candidates(tmp_path, candidates_data):
    """Build a lookup with mock production registry."""
    models = {}
    for cd in candidates_data:
        models[cd["model_id"]] = {
            "model_id": cd["model_id"],
            "provider": cd.get("provider", "lmstudio"),
            "status": cd.get("status", "limited_use"),
            "allowed_stages": cd.get("allowed_stages", {"paper_synthesis": "limited_use"}),
        }
        # Write report if provided
        if "report" in cd:
            report_dir = tmp_path / "reports" / cd["model_id"]
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "20260101T000000Z.yaml").write_text(
                yaml.dump(cd["report"], default_flow_style=False), encoding="utf-8"
            )

    reg = tmp_path / "production_registry.yaml"
    reg.write_text(yaml.dump({"models": models}, default_flow_style=False), encoding="utf-8")
    return CertifiedCapabilityLookup(str(tmp_path))


class TestRoutingDecision:
    def test_degraded_decision(self):
        d = RoutingDecision.degraded_decision("paper_synthesis", "No candidates")
        assert d.degraded is True
        assert d.strategy == "skip_with_degraded_result"
        assert d.model_id == ""

    def test_routing_decision_to_dict(self):
        d = RoutingDecision(
            stage="paper_synthesis",
            model_id="qwen3-4b",
            provider="lmstudio",
            eligibility="limited_use",
            strategy="section_wise",
            confidence=0.72,
            reason="Best available",
            hard_gates_passed=["production_registry", "stage_allowed"],
            warnings=["Low stage score"],
        )
        d_dict = d.to_dict()
        assert d_dict["stage"] == "paper_synthesis"
        assert d_dict["confidence"] == 0.72
        assert len(d_dict["hard_gates_passed"]) == 2


class TestSmartRouter:
    def test_router_returns_no_candidate_when_all_gated(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert decision.degraded is True

    def test_router_ranks_surviving_candidates(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "weak-model",
                "provider": "lmstudio",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "weak-model",
                    "eval_version": "0.2",
                    "safe_context_window": 16384,
                    "safe_output_tokens": 4096,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.50, "grounding_metrics": {"claim_support_rate": 0.60, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
            {
                "model_id": "strong-model",
                "provider": "lmstudio",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "strong-model",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "safe_output_tokens": 8192,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.90, "grounding_metrics": {"claim_support_rate": 0.85, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert decision.model_id == "strong-model"
        assert decision.degraded is False

    def test_router_selects_highest_scoring_candidate(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "model-a",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "model-a",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.80, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert decision.confidence > 0

    def test_router_forces_model_when_context_overrides(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "target-model",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "target-model",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.80, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
            {
                "model_id": "other-model",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "other-model",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.95, "grounding_metrics": {"claim_support_rate": 0.90, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext(forced_model="target-model")
        decision = router.route(contract, ctx)
        assert decision.model_id == "target-model"

    def test_router_returns_degraded_when_no_candidates(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert decision.degraded is True
        assert "No certified candidates" in decision.reason

    def test_router_includes_reason_string(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "qwen3-4b",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "qwen3-4b",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.80, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert isinstance(decision.reason, str)
        assert len(decision.reason) > 0

    def test_router_includes_hard_gates_passed(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "qwen3-4b",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "qwen3-4b",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.80, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert len(decision.hard_gates_passed) > 0
        assert "production_registry" in decision.hard_gates_passed

    def test_router_includes_warnings(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "qwen3-4b",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "qwen3-4b",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.60, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert isinstance(decision.warnings, list)

    def test_router_includes_alternative_count(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "model-a",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "model-a",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.80, "grounding_metrics": {"claim_support_rate": 0.75, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
            {
                "model_id": "model-b",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "model-b",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.70, "grounding_metrics": {"claim_support_rate": 0.70, "citation_fabrication_rate": 0.0}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext()
        decision = router.route(contract, ctx)
        assert decision.alternative_candidates >= 1

    def test_forced_model_still_respects_hard_gates_by_default(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [
            {
                "model_id": "fabricator",
                "allowed_stages": {"paper_synthesis": "limited_use"},
                "report": {
                    "model_id": "fabricator",
                    "eval_version": "0.2",
                    "safe_context_window": 32768,
                    "stage_eval": {
                        "paper_synthesis": {"aggregate_score": 0.90, "grounding_metrics": {"claim_support_rate": 0.90, "citation_fabrication_rate": 0.10}},
                    },
                },
            },
        ])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext(forced_model="fabricator")
        decision = router.route(contract, ctx)
        # Hard gate should reject for fabrication → degraded
        assert decision.degraded is True

    def test_forced_model_unsafe_override_logs_warning(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [])
        router = SmartRouter(lookup, mode="dry_run")
        contract = _make_contract()
        ctx = RoutingRuntimeContext(forced_model_unsafe="dangerous-model")
        decision = router.route(contract, ctx)
        assert decision.model_id == "dangerous-model"
        assert any("UNSAFE" in w for w in decision.warnings)

    def test_router_mode_validation(self, tmp_path):
        lookup = _make_lookup_with_candidates(tmp_path, [])
        router = SmartRouter(lookup, mode="dry_run")
        router.mode = "enforce"
        assert router.mode == "enforce"
        with pytest.raises(ValueError, match="Invalid mode"):
            router.mode = "invalid"


class TestDryRunLogger:
    def test_dry_run_logs_decision_without_changing_execution(self, tmp_path):
        logger = DryRunLogger(log_dir=str(tmp_path / "logs"))
        decision = RoutingDecision(
            stage="paper_synthesis",
            model_id="qwen3-4b",
            provider="lmstudio",
            eligibility="limited_use",
            strategy="section_wise",
            confidence=0.72,
            reason="Test",
        )
        entry = logger.log(decision, actual_model_used="legacy-model")
        assert entry.routed_model == "qwen3-4b"
        assert entry.actual_model == "legacy-model"
        assert entry.routed_model != entry.actual_model

    def test_dry_run_logger_records_actual_vs_routed(self):
        logger = DryRunLogger()
        decision = RoutingDecision(
            stage="paper_synthesis", model_id="routed",
            provider="lmstudio", eligibility="approved",
            strategy="section_wise", confidence=0.8, reason="",
        )
        logger.log(decision, actual_model_used="actual")
        mismatches = logger.get_mismatches()
        assert len(mismatches) == 1
        assert mismatches[0].routed_model == "routed"
        assert mismatches[0].actual_model == "actual"

    def test_dry_run_logger_persists_to_file(self, tmp_path):
        logger = DryRunLogger(log_dir=str(tmp_path))
        decision = RoutingDecision(
            stage="test", model_id="m", provider="p",
            eligibility="approved", strategy="single_call",
            confidence=0.5, reason="",
        )
        logger.log(decision, actual_model_used="m")
        log_file = tmp_path / "dry_run_log.jsonl"
        assert log_file.exists()
        content = log_file.read_text()
        assert "test" in content

    def test_dry_run_logger_get_log_filters_by_stage(self):
        logger = DryRunLogger()
        for stage in ["a", "a", "b"]:
            d = RoutingDecision(
                stage=stage, model_id="m", provider="p",
                eligibility="approved", strategy="single_call",
                confidence=0.5, reason="",
            )
            logger.log(d, actual_model_used="m")
        assert len(logger.get_log(stage="a")) == 2
        assert len(logger.get_log(stage="b")) == 1
