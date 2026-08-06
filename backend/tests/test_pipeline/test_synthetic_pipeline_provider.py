"""Unit tests for the deterministic synthetic downstream provider.

Exercises every stage route independently before the provider is used in
the post-gap E2E test (Commit 6). Each route is deterministic, schema-
conformant, and run-scoped.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from backend.tests.support.synthetic_pipeline_provider import (
    SUPPORTED_STAGES,
    SyntheticPipelineProvider,
)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def provider():
    p = SyntheticPipelineProvider(run_id="unit-run")
    return p


class TestRouting:
    def test_set_context_records_stage_and_run(self, provider):
        provider.set_context("novelty_checking", "unit-run")
        assert provider._stage == "novelty_checking"
        assert provider._run_id == "unit-run"

    def test_supported_stages_cover_downstream(self):
        for s in [
            "idea_generation", "novelty_checking", "feasibility_scoring",
            "proposal_synthesis", "adversarial_review", "evaluation",
            "paper_synthesis", "citation_audit", "proposal_deepening",
        ]:
            assert s in SUPPORTED_STAGES

    def test_ideator_route(self, provider):
        provider.set_context("idea_generation", "unit-run")
        r = _run(provider.structured_output([], {"properties": {"ideas": {}}}))
        assert "ideas" in r
        assert len(r["ideas"]) == 2
        assert r["ideas"][0]["title"]

    def test_critic_route(self, provider):
        provider.set_context("idea_generation", "unit-run")
        r = _run(provider.structured_output([], {"properties": {"critiques": {}}}))
        assert "critiques" in r
        assert len(r["critiques"]) == 2

    def test_novelty_route(self, provider):
        provider.set_context("novelty_checking", "unit-run")
        r = _run(provider.structured_output([], {}))
        for k in ("method_novelty", "problem_novelty", "domain_transfer",
                  "combination_novelty", "overall_score", "strategic_direction"):
            assert k in r
        assert 0.0 <= r["overall_score"] <= 1.0

    def test_feasibility_route_uses_zero_to_ten(self, provider):
        provider.set_context("feasibility_scoring", "unit-run")
        r = _run(provider.structured_output([], {}))
        for k in ("data_availability", "computational_requirements",
                  "methodological_complexity", "evaluation_plan",
                  "novelty_grounding", "impact_potential"):
            assert 0 <= r[k] <= 10
        assert isinstance(r["key_risks"], list)

    def test_adversarial_route_uses_one_to_ten_int(self, provider):
        provider.set_context("adversarial_review", "unit-run")
        r = _run(provider.structured_output([], {}))
        for k in ("soundness", "novelty", "feasibility", "clarity"):
            assert isinstance(r[k], int)
            assert 1 <= r[k] <= 10


class TestTextRoutes:
    def test_evaluation_text_has_seven_dimensions(self, provider):
        provider.set_context("evaluation", "unit-run")
        text = _run(provider.complete([]))
        for d in ("NOVELTY", "FEASIBILITY", "COMPLETENESS", "RIGOR",
                  "CLARITY", "BASELINE_ADEQUACY", "COMPUTE_REALISM"):
            assert f"{d}_SCORE:" in text
            assert f"{d}_JUSTIFICATION:" in text
        assert "OVERALL_SCORE:" in text

    def test_paper_markdown_has_source_markers_and_length(self, provider):
        provider.set_context("paper_synthesis", "unit-run")
        md = _run(provider.complete([]))
        assert "[SOURCE-1]" in md
        assert "[SOURCE-2]" in md
        # Exceeds a minimum paper threshold.
        assert len(md.split()) > 400
        assert "## Abstract" in md

    def test_proposal_markdown_has_required_sections(self, provider):
        provider.set_context("proposal_synthesis", "unit-run")
        md = _run(provider.complete([]))
        for section in ("## Title", "## Abstract", "## Introduction",
                        "## Proposed Method", "## References"):
            assert section in md

    def test_citation_audit_returns_valid_json(self, provider):
        provider.set_context("citation_audit", "unit-run")
        text = _run(provider.complete([]))
        parsed = json.loads(text)
        assert parsed["context_verified"] is True
        assert "trust_contribution" in parsed

    def test_reflection_text_has_required_tags(self, provider):
        provider.set_context("idea_reflection", "unit-run")
        text = _run(provider.complete([]))
        assert "SCORE:" in text
        assert "PASSED:" in text


class TestDeterminism:
    def test_repeated_calls_are_identical(self, provider):
        provider.set_context("novelty_checking", "unit-run")
        r1 = _run(provider.structured_output([], {}))
        r2 = _run(provider.structured_output([], {}))
        assert r1 == r2

    def test_paper_markdown_stable(self, provider):
        provider.set_context("paper_synthesis", "unit-run")
        a = _run(provider.complete([]))
        b = _run(provider.complete([]))
        assert a == b


class TestLedger:
    def test_ledger_records_every_call(self, provider):
        provider.set_context("feasibility_scoring", "unit-run")
        _run(provider.structured_output([], {}))
        provider.set_context("evaluation", "unit-run")
        _run(provider.complete_with_usage([]))
        assert len(provider.call_ledger) == 2
        for entry in provider.call_ledger:
            assert "stage" in entry
            assert "method" in entry
            assert "run_id" in entry
            assert "input_tokens" in entry
            assert "output_tokens" in entry
            assert entry["run_id"] == "unit-run"

    def test_all_calls_share_one_run(self, provider):
        provider.set_context("novelty_checking", "shared-run")
        _run(provider.structured_output([], {}))
        provider.set_context("evaluation", "shared-run")
        _run(provider.complete([]))
        assert {e["run_id"] for e in provider.call_ledger} == {"shared-run"}

    def test_token_totals_reconcile(self, provider):
        provider.set_context("evaluation", "unit-run")
        _run(provider.complete_with_usage([], max_tokens=100))
        _run(provider.complete_with_usage([], max_tokens=100))
        total_in = sum(e["input_tokens"] for e in provider.call_ledger)
        total_out = sum(e["output_tokens"] for e in provider.call_ledger)
        assert total_in >= 0
        assert total_out > 0


class TestNetworkFree:
    def test_no_network_attribute(self, provider):
        # The provider performs no I/O. Assert it has no socket/requests deps
        # bound as instance state.
        assert not hasattr(provider, "_session")
        assert not hasattr(provider, "_client")
