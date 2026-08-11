"""Phase C tests: HardGateEngine."""


from backend.pipeline.routing.certified_lookup import CertifiedModelCandidate
from backend.pipeline.routing.hard_gates import HardGateEngine
from backend.pipeline.routing.stage_contract import StageContract


def _make_contract(**overrides):
    defaults = dict(
        stage="paper_synthesis",
        task_type="generation",
        risk_level="high",
        requires_json=False,
        requires_grounding=True,
        requires_citations=True,
        requires_independent_review=False,
        input_tokens_estimate=6000,
        output_tokens_requested=8000,
        min_context_window=16384,
        allowed_strategies=["section_wise", "map_reduce"],
        fallback_strategy="section_wise",
    )
    defaults.update(overrides)
    return StageContract(**defaults)


def _make_candidate(**overrides):
    defaults = dict(
        model_id="qwen3-4b",
        provider="lmstudio",
        allowed_stages=["paper_synthesis", "repair", "query_generation"],
        stage_eligibility="limited_use",
        safe_context_window=16384,
        safe_output_tokens=4096,
        schema_valid_rate=0.90,
        grounding_metrics={
            "claim_support_rate": 0.70,
            "citation_fabrication_rate": 0.0,
        },
    )
    defaults.update(overrides)
    return CertifiedModelCandidate(**defaults)


class TestHardGates:
    def test_gate_passes_all_for_clean_candidate(self):
        engine = HardGateEngine()
        contract = _make_contract(stage="paper_synthesis")
        candidate = _make_candidate()
        results = engine.evaluate(contract, candidate)
        assert engine.all_passed(results), f"Failed: {[r.reason for r in results if not r.passed]}"

    def test_gate_rejects_stage_not_allowed(self):
        engine = HardGateEngine()
        contract = _make_contract(stage="citation_audit")
        candidate = _make_candidate(allowed_stages=["paper_synthesis"])  # no citation_audit
        results = engine.evaluate(contract, candidate)
        assert not engine.all_passed(results)
        gate_names = [r.gate for r in engine.failed_gates(results)]
        assert "stage_allowed" in gate_names

    def test_gate_rejects_context_too_small(self):
        engine = HardGateEngine()
        contract = _make_contract(input_tokens_estimate=8000, output_tokens_requested=12000)
        candidate = _make_candidate(safe_context_window=4096)  # way too small
        results = engine.evaluate(contract, candidate)
        failed = engine.failed_gates(results)
        assert any(r.gate == "context_sufficient" for r in failed)

    def test_gate_rejects_json_incapable_for_json_contract(self):
        engine = HardGateEngine()
        contract = _make_contract(requires_json=True, stage="evidence_table")
        candidate = _make_candidate(schema_valid_rate=0.30)  # below 0.70 threshold
        results = engine.evaluate(contract, candidate)
        failed = engine.failed_gates(results)
        assert any(r.gate == "json_capability" for r in failed)

    def test_gate_rejects_fabrication_for_grounded_contract(self):
        engine = HardGateEngine()
        contract = _make_contract(requires_grounding=True)
        candidate = _make_candidate(grounding_metrics={
            "citation_fabrication_rate": 0.05,  # > 0
            "claim_support_rate": 0.80,
        })
        results = engine.evaluate(contract, candidate)
        failed = engine.failed_gates(results)
        assert any(r.gate == "no_fabrication" for r in failed)

    def test_gate_rejects_same_model_for_review_independence(self):
        engine = HardGateEngine()
        contract = _make_contract(
            stage="adversarial_review",
            requires_independent_review=True,
            requires_grounding=True,
        )
        candidate = _make_candidate(model_id="qwen3-4b")
        results = engine.evaluate(contract, candidate, generator_model_id="qwen3-4b")
        failed = engine.failed_gates(results)
        assert any(r.gate == "review_independence" for r in failed)

    def test_gate_passes_review_with_different_model(self):
        engine = HardGateEngine()
        contract = _make_contract(
            stage="adversarial_review",
            requires_independent_review=True,
            requires_grounding=True,
        )
        candidate = _make_candidate(
            model_id="reviewer-model",
            allowed_stages=["adversarial_review", "paper_synthesis"],  # must include adversarial_review
        )
        results = engine.evaluate(contract, candidate, generator_model_id="generator-model")
        assert engine.all_passed(results), f"Failed: {[r.reason for r in engine.failed_gates(results)]}"

    def test_gate_results_include_reason_strings(self):
        engine = HardGateEngine()
        contract = _make_contract(stage="paper_synthesis")
        candidate = _make_candidate()
        results = engine.evaluate(contract, candidate)
        for r in results:
            assert isinstance(r.reason, str)
            assert len(r.reason) > 0

    def test_gate_respects_synthesis_v2_cap(self):
        engine = HardGateEngine()
        contract = _make_contract(stage="paper_synthesis")
        candidate = _make_candidate()
        results = engine.evaluate(contract, candidate)
        synthesis_gate = [r for r in results if r.gate == "synthesis_v2_cap"]
        assert len(synthesis_gate) == 1
        assert synthesis_gate[0].passed is True

    def test_gate_context_uses_strategy_plan_not_raw_prompt(self):
        """Context gate should use strategy-planned tokens, not raw contract estimates."""
        engine = HardGateEngine()
        contract = _make_contract(
            input_tokens_estimate=15000,  # raw: too large
            output_tokens_requested=8000,
        )
        candidate = _make_candidate(safe_context_window=12000)

        # Without strategy plan → should fail (15000 + 8000 * 1.15 = 26450 > 12000)
        raw_results = engine.evaluate(contract, candidate)
        raw_ctx = [r for r in raw_results if r.gate == "context_sufficient"]
        assert not raw_ctx[0].passed

        # With strategy plan (section_wise: ~35% input + ~40% output)
        # 5250 + 3200 = 8450 * 1.15 = 9718 < 12000 → should pass
        planned_results = engine.evaluate(
            contract, candidate,
            strategy_input_tokens=5250,
            strategy_output_tokens=3200,
        )
        planned_ctx = [r for r in planned_results if r.gate == "context_sufficient"]
        assert planned_ctx[0].passed

    def test_adversarial_review_requires_independent_and_grounded(self):
        engine = HardGateEngine()
        contract = _make_contract(
            stage="adversarial_review",
            requires_grounding=True,
            requires_independent_review=True,
        )
        # Candidate without grounding data
        candidate = _make_candidate(grounding_metrics={
            "citation_fabrication_rate": 0.10,
            "claim_support_rate": 0.30,
        })
        results = engine.evaluate(contract, candidate)
        failed = engine.failed_gates(results)
        assert any(r.gate == "no_fabrication" for r in failed)
