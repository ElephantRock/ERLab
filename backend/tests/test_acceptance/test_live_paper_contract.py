"""Tests for the typed live-paper acceptance contract.

Validates the manifest model and every rejection rule from the plan:
unknown fields, blank identifiers, negative budgets, unsupported artifact
classes, live mode without provider/model, frozen-corpus mode without a
corpus manifest, and mismatched search/network policies.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.acceptance.live_paper_contract import (
    AcceptanceGates,
    ArtifactClass,
    CorpusMode,
    GenerationParameters,
    LivePaperAcceptanceCase,
    NetworkPolicy,
    Strategy,
)

CASE_PATH = Path(__file__).resolve().parents[3] / "acceptance" / "cases" / "live_paper_frozen_corpus_v1.json"


def _valid_case_dict(**over) -> dict:
    """A minimal valid case dict, overridable per test."""
    base = {
        "schema_version": "erlab.live-paper-acceptance.v1",
        "case_id": "test-case-1",
        "artifact_class": "non_empirical_research_synthesis",
        "research_domain": "low-resource MT",
        "research_question": "How can transfer help low-resource MT?",
        "expected_code_sha": "abcdef1234567890abcdef1234567890abcdef12",
        "strategy": "deep_research",
        "corpus_mode": "frozen_real",
        "corpus_manifest_path": "acceptance/corpora/x/manifest.json",
        "provider": "zai",
        "model": "glm-4.6",
        "embedding_provider": "lmstudio",
        "embedding_model": "text-embedding-qwen3-embedding-0.6b",
        "generation_parameters": {"generation_rounds": 1, "ideas_per_round": 1, "max_gaps": 3},
        "budget": {
            "maximum_cost_usd": 5.0, "maximum_provider_calls": 200,
            "maximum_input_tokens": 1000, "maximum_output_tokens": 500,
            "maximum_duration_seconds": 1800,
        },
        "execution": {"network_policy": "provider_only"},
        "gates": {},
    }
    base.update(over)
    return base


# ── Happy path ───────────────────────────────────────────────────────


class TestContractValidates:
    def test_case_file_loads_and_validates(self):
        case = LivePaperAcceptanceCase.load(CASE_PATH)
        assert case.case_id == "live_paper_frozen_corpus_v1"
        assert case.artifact_class is ArtifactClass.NON_EMPIRICAL_RESEARCH_SYNTHESIS
        assert case.corpus_mode is CorpusMode.FROZEN_REAL
        assert case.strategy is Strategy.DEEP_RESEARCH

    def test_minimal_valid_case(self):
        case = LivePaperAcceptanceCase.model_validate(_valid_case_dict())
        assert case.budget.maximum_cost_usd == 5.0

    def test_generation_parameters_defaults(self):
        gp = GenerationParameters()
        assert gp.export_format == "markdown"
        assert gp.generation_rounds >= 1

    def test_gates_default_all_active(self):
        gates = AcceptanceGates()
        # All 12 gates active by default.
        active = [v for v in gates.model_dump().values() if v is True]
        assert len(active) == 12


# ── Rejection rules ──────────────────────────────────────────────────


class TestRejectsUnknownFields:
    def test_unknown_top_level_field_rejected(self):
        d = _valid_case_dict(unknown_field="x")
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_unknown_budget_field_rejected(self):
        d = _valid_case_dict(budget={**_valid_case_dict()["budget"], "extra": 1})
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)


class TestRejectsBlankIdentifiers:
    @pytest.mark.parametrize("field", [
        "case_id", "research_domain", "research_question", "provider",
        "model", "embedding_provider", "embedding_model",
    ])
    def test_blank_string_rejected(self, field):
        d = _valid_case_dict(**{field: "   "})
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_blank_expected_code_sha_rejected(self):
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(_valid_case_dict(expected_code_sha="   "))


class TestRejectsBadSha:
    def test_short_sha_rejected(self):
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(_valid_case_dict(expected_code_sha="abc12"))

    def test_non_hex_sha_rejected(self):
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(
                _valid_case_dict(expected_code_sha="zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
            )


class TestRejectsNegativeBudgets:
    def test_negative_cost_rejected(self):
        d = _valid_case_dict()
        d["budget"]["maximum_cost_usd"] = -1.0
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_zero_calls_rejected(self):
        d = _valid_case_dict()
        d["budget"]["maximum_provider_calls"] = 0
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)


class TestRejectsUnsupportedArtifactClass:
    def test_unsupported_class_rejected(self):
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(
                _valid_case_dict(artifact_class="empirical_benchmark_paper")
            )


class TestCorpusPolicyConsistency:
    def test_frozen_real_without_corpus_manifest_rejected(self):
        d = _valid_case_dict(corpus_manifest_path=None)
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_synthetic_does_not_require_corpus_manifest(self):
        d = _valid_case_dict(corpus_mode="synthetic", corpus_manifest_path=None,
                             execution={"network_policy": "hermetic"})
        case = LivePaperAcceptanceCase.model_validate(d)
        assert case.corpus_mode is CorpusMode.SYNTHETIC

    def test_live_search_with_hermetic_network_rejected(self):
        d = _valid_case_dict(corpus_mode="live_search", corpus_manifest_path=None,
                             execution={"network_policy": "hermetic"})
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_live_search_with_provider_only_network_rejected(self):
        d = _valid_case_dict(corpus_mode="live_search", corpus_manifest_path=None,
                             execution={"network_policy": "provider_only"})
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(d)

    def test_live_search_with_provider_and_search_accepted(self):
        d = _valid_case_dict(corpus_mode="live_search", corpus_manifest_path=None,
                             execution={"network_policy": "provider_and_search"})
        case = LivePaperAcceptanceCase.model_validate(d)
        assert case.execution.network_policy is NetworkPolicy.PROVIDER_AND_SEARCH


class TestStrategyFrozen:
    def test_only_deep_research_supported(self):
        with pytest.raises(ValidationError):
            LivePaperAcceptanceCase.model_validate(_valid_case_dict(strategy="quick"))
