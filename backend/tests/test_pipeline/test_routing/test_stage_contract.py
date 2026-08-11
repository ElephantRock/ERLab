"""Phase A tests: StageContract."""


import pytest

from backend.pipeline.routing.stage_contract import (
    StageContract,
    get_contract,
    get_smart_router_config,
    load_contracts,
)


def _make_contract(**overrides):
    defaults = dict(
        stage="test_stage",
        task_type="generation",
        risk_level="medium",
        allowed_strategies=["single_call"],
        fallback_strategy="single_call",
    )
    defaults.update(overrides)
    return StageContract(**defaults)


class TestStageContract:
    def test_contract_loads_from_yaml(self):
        contracts = load_contracts()
        assert len(contracts) >= 9  # all pipeline stages
        assert "paper_synthesis" in contracts
        assert "citation_audit" in contracts

    def test_contract_validates_required_fields(self):
        c = StageContract(stage="", task_type="", risk_level="medium")
        errors = c.validate()
        assert any("stage is required" in e for e in errors)
        assert any("task_type is required" in e for e in errors)

    def test_contract_rejects_invalid_risk_level(self):
        c = _make_contract(risk_level="extreme")
        errors = c.validate()
        assert any("risk_level" in e for e in errors)

    def test_contract_rejects_invalid_strategy(self):
        c = _make_contract(allowed_strategies=["nonexistent_strategy"])
        errors = c.validate()
        assert any("Invalid strategies" in e for e in errors)

    def test_all_pipeline_stages_have_contracts(self):
        contracts = load_contracts()
        expected = {
            "literature_search", "idea_generation", "proposal_synthesis",
            "paper_synthesis", "citation_audit", "adversarial_review",
            "evidence_table", "repair", "query_generation",
        }
        assert expected.issubset(set(contracts.keys()))

    def test_contract_roundtrip_yaml(self, tmp_path):
        c = _make_contract()
        d = c.to_dict()
        loaded = StageContract.from_dict(d)
        assert loaded.stage == c.stage
        assert loaded.risk_level == c.risk_level
        assert loaded.allowed_strategies == c.allowed_strategies

    def test_get_contract_raises_for_unknown_stage(self):
        contracts = load_contracts()
        with pytest.raises(KeyError, match="nonexistent"):
            get_contract("nonexistent", contracts)

    def test_default_contracts_have_valid_risk_levels(self):
        contracts = load_contracts()
        for name, c in contracts.items():
            errors = c.validate()
            assert not errors, f"Contract '{name}' has errors: {errors}"

    def test_smart_router_config_loads(self):
        config = get_smart_router_config()
        assert "mode" in config
        assert "ranking_weights" in config
        assert config["mode"] in ("disabled", "dry_run", "enforce")

    def test_adversarial_review_requires_grounding(self):
        contracts = load_contracts()
        ar = contracts["adversarial_review"]
        assert ar.requires_grounding is True
        assert ar.requires_independent_review is True

    def test_paper_synthesis_uses_section_wise(self):
        contracts = load_contracts()
        ps = contracts["paper_synthesis"]
        assert "section_wise" in ps.allowed_strategies

    def test_citation_audit_is_critical(self):
        contracts = load_contracts()
        ca = contracts["citation_audit"]
        assert ca.risk_level == "critical"
        assert ca.requires_json is True
