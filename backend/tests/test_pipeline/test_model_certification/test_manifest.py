"""Phase A tests: Manifest + Registries."""

import pytest
import tempfile
from pathlib import Path

from backend.pipeline.model_certification.manifest import CandidateModelManifest
from backend.pipeline.model_certification.registries import (
    CandidateModelRegistry,
    ProductionModelRegistry,
    PromotionDenied,
)


# ── Manifest ──────────────────────────────────────────────────────────


def _make_manifest(**overrides) -> CandidateModelManifest:
    defaults = dict(
        model_id="test-model",
        provider="lmstudio",
        source="local",
        model_family="qwen",
        advertised_context_window=8192,
        advertised_max_output_tokens=4096,
    )
    defaults.update(overrides)
    return CandidateModelManifest(**defaults)


class TestManifest:
    def test_candidate_defaults_to_untested_and_not_allowed(self):
        m = _make_manifest()
        assert m.candidate_status == "untested"
        assert m.allowed_for_pipeline is False

    def test_manifest_validate_rejects_missing_model_id(self):
        m = _make_manifest(model_id="")
        errors = m.validate()
        assert any("model_id" in e for e in errors)

    def test_manifest_validate_rejects_zero_context_window(self):
        m = _make_manifest(advertised_context_window=0)
        errors = m.validate()
        assert any("context_window" in e for e in errors)

    def test_manifest_validate_rejects_invalid_provider(self):
        m = _make_manifest(provider="nonexistent_provider")
        errors = m.validate()
        assert any("provider" in e for e in errors)

    def test_manifest_validate_rejects_output_exceeding_context(self):
        m = _make_manifest(
            advertised_context_window=4096,
            advertised_max_output_tokens=8192,
        )
        errors = m.validate()
        assert any("exceed" in e.lower() for e in errors)

    def test_manifest_validate_passes_for_valid_manifest(self):
        m = _make_manifest()
        assert m.validate() == []

    def test_manifest_yaml_roundtrip(self):
        m = _make_manifest()
        yaml_str = m.to_yaml()
        m2 = CandidateModelManifest.from_yaml(yaml_str)
        assert m2.model_id == m.model_id
        assert m2.provider == m.provider
        assert m2.advertised_context_window == m.advertised_context_window
        assert m2.supports_json_mode == m.supports_json_mode

    def test_manifest_yaml_file_roundtrip(self, tmp_path):
        path = tmp_path / "candidate.yaml"
        m = _make_manifest()
        m.to_yaml_file(path)
        m2 = CandidateModelManifest.from_yaml_file(path)
        assert m2.model_id == m.model_id

    def test_manifest_content_hash_deterministic(self):
        m = _make_manifest()
        h1 = m.content_hash
        h2 = m.content_hash
        assert h1 == h2
        assert len(h1) == 16  # truncated SHA-256

    def test_manifest_content_hash_changes_on_field_change(self):
        m = _make_manifest()
        h1 = m.content_hash
        m.advertised_context_window = 99999
        h2 = m.content_hash
        assert h1 != h2


# ── Registries ────────────────────────────────────────────────────────


class TestCandidateRegistry:
    def test_candidate_registry_add_and_get(self, tmp_path):
        reg = CandidateModelRegistry(path=tmp_path / "candidates.yaml")
        m = _make_manifest()
        reg.add(m)
        got = reg.get("test-model")
        assert got is not None
        assert got.model_id == "test-model"

    def test_candidate_registry_list(self, tmp_path):
        reg = CandidateModelRegistry(path=tmp_path / "candidates.yaml")
        reg.add(_make_manifest(model_id="a"))
        reg.add(_make_manifest(model_id="b"))
        assert len(reg.list_candidates()) == 2

    def test_candidate_registry_rejects_invalid_manifest(self, tmp_path):
        reg = CandidateModelRegistry(path=tmp_path / "candidates.yaml")
        with pytest.raises(ValueError, match="Invalid manifest"):
            reg.add(_make_manifest(model_id=""))

    def test_candidate_registry_persists(self, tmp_path):
        path = tmp_path / "candidates.yaml"
        reg1 = CandidateModelRegistry(path=path)
        reg1.add(_make_manifest())

        reg2 = CandidateModelRegistry(path=path)
        assert reg2.get("test-model") is not None


class TestProductionRegistry:
    def _report_eligibility(self, stages: dict[str, str]) -> dict:
        return stages

    def test_production_registry_rejects_rejected_report(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied):
            reg.promote(
                model_id="bad-model",
                status="rejected",
                stage_eligibility={"draft": "approved"},
                promotion_allowed=True,
            )

    def test_production_registry_rejects_manual_review(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied):
            reg.promote(
                model_id="review-model",
                status="requires_manual_review",
                stage_eligibility={"draft": "approved"},
                promotion_allowed=True,
            )

    def test_production_registry_promote_approved_model(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        reg.promote(
            model_id="good-model",
            status="approved_for_production",
            stage_eligibility={"draft": "approved", "repair": "approved"},
            promotion_allowed=True,
            report_path="reports/good-model/report.yaml",
        )
        entry = reg.get("good-model")
        assert entry is not None
        assert "draft" in entry["allowed_stages"]
        assert "repair" in entry["allowed_stages"]

    def test_production_registry_get_allowed_models_filters_by_stage(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        reg.promote(
            model_id="m1",
            status="approved_for_limited_use",
            stage_eligibility={"draft": "approved", "repair": "approved"},
            promotion_allowed=True,
        )
        reg.promote(
            model_id="m2",
            status="approved_for_production",
            stage_eligibility={"draft": "approved", "synthesize": "approved"},
            promotion_allowed=True,
        )
        draft_models = reg.get_allowed_models(stage="draft")
        assert len(draft_models) == 2
        synth_models = reg.get_allowed_models(stage="synthesize")
        assert len(synth_models) == 1
        assert synth_models[0]["model_id"] == "m2"

    def test_limited_use_report_promotes_only_limited_stages(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        eligibility = {
            "draft": "approved",
            "repair": "approved",
            "paper_synthesis": "not_approved",  # v0.1 conservative
            "adversarial_review": "not_approved",
        }
        reg.promote(
            model_id="limited-model",
            status="approved_for_limited_use",
            stage_eligibility=eligibility,
            promotion_allowed=True,
        )
        entry = reg.get("limited-model")
        assert entry is not None
        allowed = entry["allowed_stages"]
        assert "draft" in allowed
        assert "repair" in allowed
        assert "paper_synthesis" not in allowed
        assert "adversarial_review" not in allowed

    def test_promotion_denied_when_no_eligible_stages(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied, match="no promotable stages"):
            reg.promote(
                model_id="empty-model",
                status="approved_for_limited_use",
                stage_eligibility={
                    "paper_synthesis": "not_approved",
                    "adversarial_review": "not_approved",
                },
                promotion_allowed=True,
            )

    def test_promotion_denied_when_promotion_not_allowed(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied, match="promotion_allowed=False"):
            reg.promote(
                model_id="nope",
                status="approved_for_limited_use",
                stage_eligibility={"draft": "approved"},
                promotion_allowed=False,
            )

    def test_limited_use_with_no_allowed_stages_is_not_promotable(self, tmp_path):
        """A model can be APPROVED_FOR_LIMITED_USE but still have no promotable stages."""
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied):
            reg.promote(
                model_id="limited-empty",
                status="approved_for_limited_use",
                stage_eligibility={},  # empty
                promotion_allowed=True,
            )

    def test_repair_only_promotes_only_repair(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        eligibility = {
            "repair": "approved",
            "draft": "not_approved",
            "synthesize": "not_approved",
        }
        reg.promote(
            model_id="repair-model",
            status="approved_for_repair_only",
            stage_eligibility=eligibility,
            promotion_allowed=True,
        )
        entry = reg.get("repair-model")
        assert entry is not None
        assert list(entry["allowed_stages"].keys()) == ["repair"]

    def test_manual_review_never_auto_promotes(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        with pytest.raises(PromotionDenied):
            reg.promote(
                model_id="review-model",
                status="requires_manual_review",
                stage_eligibility={"draft": "approved"},
                promotion_allowed=True,  # even with True, status blocks
            )

    def test_production_registry_rejects_stage_not_in_report(self, tmp_path):
        reg = ProductionModelRegistry(path=tmp_path / "prod.yaml")
        reg.promote(
            model_id="scoped-model",
            status="approved_for_limited_use",
            stage_eligibility={"draft": "approved"},
            promotion_allowed=True,
        )
        # Model is in production but NOT for paper_synthesis
        paper_models = reg.get_allowed_models(stage="paper_synthesis")
        assert len(paper_models) == 0
        draft_models = reg.get_allowed_models(stage="draft")
        assert len(draft_models) == 1
