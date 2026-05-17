"""Phase B tests: CertifiedCapabilityLookup."""

import pytest
from pathlib import Path

import yaml

from backend.pipeline.routing.certified_lookup import (
    CertifiedCapabilityLookup,
    CertifiedModelCandidate,
)


def _write_production_registry(tmp_path, models: dict):
    """Write a production_registry.yaml."""
    reg = tmp_path / "production_registry.yaml"
    reg.write_text(yaml.dump({"models": models}, default_flow_style=False), encoding="utf-8")


def _write_report(tmp_path, model_id: str, report_data: dict):
    """Write a capability report for a model."""
    report_dir = tmp_path / "reports" / model_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "20260101T000000Z.yaml").write_text(
        yaml.dump(report_data, default_flow_style=False), encoding="utf-8"
    )


class TestCertifiedLookup:
    def test_lookup_loads_production_registry(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {
                "model_id": "qwen3-4b",
                "provider": "lmstudio",
                "status": "approved_for_limited_use",
                "allowed_stages": {
                    "query_generation": "approved",
                    "repair": "approved",
                },
            }
        })
        lookup = CertifiedCapabilityLookup(str(tmp_path))
        candidates = lookup.get_candidates_for_stage("query_generation")
        assert len(candidates) == 1
        assert candidates[0].model_id == "qwen3-4b"

    def test_lookup_prefers_v2_eligibility(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {
                "model_id": "qwen3-4b",
                "provider": "lmstudio",
                "status": "approved_for_limited_use",
                "allowed_stages": {
                    "paper_synthesis": "limited_use",
                },
            }
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.2",
            "status": "approved_for_limited_use",
            "safe_context_window": 8192,
            "safe_output_tokens": 2048,
            "stage_eligibility": {"paper_synthesis": "limited_use"},
            "stage_eligibility_v2": {
                "paper_synthesis": {
                    "eligibility": "limited_use",
                    "score": 0.78,
                },
            },
            "stage_eval": {
                "paper_synthesis": {
                    "stage": "paper_synthesis",
                    "aggregate_score": 0.78,
                    "grounding_metrics": {
                        "claim_support_rate": 0.65,
                        "citation_fabrication_rate": 0.0,
                    },
                },
            },
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        candidates = lookup.get_candidates_for_stage("paper_synthesis")
        assert len(candidates) == 1
        assert candidates[0].eval_version == "0.2"
        assert candidates[0].stage_score == 0.78

    def test_lookup_falls_back_to_v1_when_v2_missing(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {
                "model_id": "qwen3-4b",
                "provider": "lmstudio",
                "status": "approved_for_limited_use",
                "allowed_stages": {"repair": "approved"},
            }
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.1",
            "status": "approved_for_limited_use",
            "stage_eligibility": {"repair": "approved"},
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        candidates = lookup.get_candidates_for_stage("repair")
        assert len(candidates) == 1
        assert candidates[0].eval_version == "0.1"

    def test_lookup_returns_empty_for_empty_registry(self, tmp_path):
        # No production_registry.yaml
        lookup = CertifiedCapabilityLookup(str(tmp_path))
        candidates = lookup.get_candidates_for_stage("any_stage")
        assert candidates == []

    def test_lookup_gets_latest_report(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {"model_id": "qwen3-4b", "provider": "lmstudio",
                          "status": "approved", "allowed_stages": {"repair": "approved"}},
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.1",
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        report = lookup.get_latest_report("qwen3-4b")
        assert report is not None
        assert report.model_id == "qwen3-4b"

    def test_lookup_gets_stage_scorecard_from_v2_report(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {"model_id": "qwen3-4b", "provider": "lmstudio",
                          "status": "approved", "allowed_stages": {"repair": "approved"}},
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.2",
            "stage_eval": {
                "repair": {
                    "stage": "repair",
                    "aggregate_score": 0.92,
                    "cases_run": 5,
                },
            },
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        card = lookup.get_stage_scorecard("qwen3-4b", "repair")
        assert card is not None
        assert card.aggregate_score == 0.92

    def test_lookup_returns_none_scorecard_for_v1_only_report(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {"model_id": "qwen3-4b", "provider": "lmstudio",
                          "status": "approved", "allowed_stages": {"repair": "approved"}},
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.1",
            "stage_eligibility": {"repair": "approved"},
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        card = lookup.get_stage_scorecard("qwen3-4b", "repair")
        assert card is None

    def test_lookup_excludes_not_approved_v2_stage(self, tmp_path):
        _write_production_registry(tmp_path, {
            "qwen3-4b": {
                "model_id": "qwen3-4b",
                "provider": "lmstudio",
                "status": "approved_for_limited_use",
                "allowed_stages": {"paper_synthesis": "limited_use"},
            }
        })
        _write_report(tmp_path, "qwen3-4b", {
            "model_id": "qwen3-4b",
            "eval_version": "0.2",
            "stage_eligibility_v2": {
                "paper_synthesis": {"eligibility": "not_approved"},
            },
        })

        lookup = CertifiedCapabilityLookup(str(tmp_path))
        candidates = lookup.get_candidates_for_stage("paper_synthesis")
        assert candidates == []
