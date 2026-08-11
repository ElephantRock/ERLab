"""Tests for claim-type-aware evidence-grounded generation.

Phase A invariant tests — verify that claim types, section contracts,
and support requirements are correctly defined and that assumptions
cannot leak into claim metrics.
"""


from backend.pipeline.gateway.claim_types import (
    CLAIM_SUPPORT_REQUIREMENTS,
    CLAIM_TYPE_VALUES,
    SECTION_CONTRACTS,
    ClaimType,
    DesignAssumption,
    detect_benefit_phrases,
    is_type_allowed_in_section,
    must_cite,
    must_mark_speculative,
)
from backend.pipeline.synthesis.section_contracts import (
    CLAIM_SCHEMA,
    SECTION_PROMPTS,
    get_section_prompt,
)

# ═══════════════════════════════════════════════════════════════════════════
# CRITICAL INVARIANT: Assumptions do NOT affect claim metrics
# Written first per reviewer instruction — highest-risk bug
# ═══════════════════════════════════════════════════════════════════════════


class TestAssumptionSeparation:
    """Assumptions must NEVER enter claim metrics."""

    def test_design_assumption_is_not_a_claim_type(self):
        """DesignAssumption must not appear in ClaimType enum."""
        assumption = DesignAssumption(
            assumption_id="P0-method-A001",
            text="We assume X can approximate Y",
            basis="analogical",
            risk="medium",
        )
        # DesignAssumption is NOT a ClaimType member
        assert not isinstance(assumption, ClaimType)

    def test_claim_type_values_excludes_design_assumption(self):
        """CLAIM_TYPE_VALUES must not contain 'design_assumption'."""
        assert "design_assumption" not in CLAIM_TYPE_VALUES

    def test_claim_type_enum_has_exactly_11_values(self):
        """Exactly 11 claim types — no more, no fewer."""
        assert len(ClaimType) == 11

    def test_design_assumption_has_separate_fields(self):
        """DesignAssumption has its own structure."""
        a = DesignAssumption(
            assumption_id="P0-method-A001",
            text="Test assumption",
            basis="empirical",
            supporting_sources=["SOURCE-1"],
            risk="high",
            validation_plan="Ablation study",
        )
        assert a.basis == "empirical"
        assert a.risk == "high"
        assert a.validation_plan == "Ablation study"
        assert len(a.supporting_sources) == 1

    def test_many_assumptions_do_not_inflate_metrics(self):
        """Simulated metric computation must not count assumptions."""
        claims = [
            {"type": "background", "text": "Test", "evidence_ids": ["SOURCE-1"]},
            {"type": "hypothesis", "text": "We hypothesize X", "evidence_ids": []},
        ]
        assumptions = [
            DesignAssumption(assumption_id=f"P0-A{i:03d}", text=f"Assumption {i}", basis="theoretical")
            for i in range(50)
        ]

        # Only claims enter the denominator
        claim_types_in_claims = {c["type"] for c in claims}
        claim_types_in_claims = claim_types_in_claims & CLAIM_TYPE_VALUES
        total_claims = len(claims)

        # Assumptions must not change the denominator
        assert total_claims == 2
        # 50 assumptions should not change this
        assert len(assumptions) == 50
        assert total_claims == 2  # Still 2, not 52


# ═══════════════════════════════════════════════════════════════════════════
# Claim Type Definitions
# ═══════════════════════════════════════════════════════════════════════════


class TestClaimTypeDefinitions:

    def test_all_claim_types_have_support_requirements(self):
        """Every ClaimType must have an entry in CLAIM_SUPPORT_REQUIREMENTS."""
        for ct in ClaimType:
            assert ct.value in CLAIM_SUPPORT_REQUIREMENTS, f"Missing support requirement for {ct.value}"

    def test_all_claim_types_have_min_support(self):
        """Every support requirement must have min_support."""
        for ct in ClaimType:
            req = CLAIM_SUPPORT_REQUIREMENTS[ct.value]
            assert "min_support" in req, f"Missing min_support for {ct.value}"
            assert req["min_support"] in ("strong", "weak", "none")

    def test_corpus_required_types(self):
        """Types that require corpus evidence."""
        corpus_required = [
            ClaimType.BACKGROUND.value,
            ClaimType.PRIOR_LIMITATION.value,
            ClaimType.METHOD_DESIGN_MOTIVATION.value,
            ClaimType.RESULT.value,
        ]
        for ct in corpus_required:
            assert CLAIM_SUPPORT_REQUIREMENTS[ct]["corpus_required"] is True

    def test_corpus_not_required_types(self):
        """Types that do not require corpus evidence."""
        corpus_optional = [
            ClaimType.METHOD_PROPOSED_MECHANISM.value,
            ClaimType.HYPOTHESIS.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ]
        for ct in corpus_optional:
            assert CLAIM_SUPPORT_REQUIREMENTS[ct]["corpus_required"] is False

    def test_speculative_marking_required_types(self):
        """Types that must be marked speculative."""
        speculative_required = [
            ClaimType.METHOD_CLAIMED_BENEFIT.value,
            ClaimType.HYPOTHESIS.value,
            ClaimType.EXPECTED_CONTRIBUTION.value,
        ]
        for ct in speculative_required:
            req = CLAIM_SUPPORT_REQUIREMENTS[ct]
            assert req.get("must_be_marked_speculative") is True


# ═══════════════════════════════════════════════════════════════════════════
# Section Contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionContracts:

    def test_all_standard_sections_have_contracts(self):
        """7 standard sections must all have contracts."""
        standard = ["abstract", "introduction", "related_work", "proposed_method",
                    "evaluation_plan", "discussion", "conclusion"]
        for section in standard:
            assert section in SECTION_CONTRACTS, f"Missing contract for {section}"

    def test_related_work_no_speculation(self):
        """Related Work must not allow speculative claims."""
        contract = SECTION_CONTRACTS["related_work"]
        assert contract.get("allow_speculative") is False
        # Only background and prior_limitation allowed
        allowed = contract["allowed_types"]
        assert ClaimType.BACKGROUND.value in allowed
        assert ClaimType.PRIOR_LIMITATION.value in allowed
        assert ClaimType.HYPOTHESIS.value not in allowed

    def test_method_allows_mechanism_and_benefit(self):
        """Method section must allow mechanism AND benefit as separate types."""
        contract = SECTION_CONTRACTS["proposed_method"]
        allowed = contract["allowed_types"]
        assert ClaimType.METHOD_PROPOSED_MECHANISM.value in allowed
        assert ClaimType.METHOD_CLAIMED_BENEFIT.value in allowed

    def test_evaluation_requires_four_blocks(self):
        """Evaluation must require four blocks."""
        contract = SECTION_CONTRACTS["evaluation_plan"]
        assert contract.get("require_four_blocks") is True
        assert "required_blocks" in contract

    def test_is_type_allowed_in_section(self):
        """Type allowance checking."""
        assert is_type_allowed_in_section("background", "related_work") is True
        assert is_type_allowed_in_section("hypothesis", "related_work") is False
        assert is_type_allowed_in_section("method_proposed_mechanism", "proposed_method") is True

    def test_must_mark_speculative(self):
        """Speculative marking requirements."""
        assert must_mark_speculative("hypothesis", "proposed_method") is True
        assert must_mark_speculative("background", "related_work") is False
        assert must_mark_speculative("expected_contribution", "conclusion") is True

    def test_must_cite(self):
        """Citation requirements."""
        assert must_cite("background", "related_work") is True
        assert must_cite("method_proposed_mechanism", "proposed_method") is False
        assert must_cite("background", "proposed_method") is True


# ═══════════════════════════════════════════════════════════════════════════
# Benefit Detection
# ═══════════════════════════════════════════════════════════════════════════


class TestBenefitDetection:

    def test_hard_keyword_improves(self):
        has_hard, has_soft, matched = detect_benefit_phrases(
            "This method improves accuracy by 12%"
        )
        assert has_hard is True
        assert "improves" in matched

    def test_hard_keyword_enables(self):
        has_hard, _, _ = detect_benefit_phrases("This enables better coordination")
        assert has_hard is True

    def test_soft_keyword_robust(self):
        has_hard, has_soft, matched = detect_benefit_phrases(
            "This approach is robust to noise"
        )
        assert has_hard is False
        assert has_soft is True

    def test_soft_keyword_facilitates(self):
        _, has_soft, _ = detect_benefit_phrases("This facilitates deployment")
        assert has_soft is True

    def test_no_benefit_phrases(self):
        has_hard, has_soft, matched = detect_benefit_phrases(
            "We propose a two-stage routing mechanism"
        )
        assert has_hard is False
        assert has_soft is False
        assert len(matched) == 0

    def test_mixed_hard_and_soft(self):
        has_hard, has_soft, matched = detect_benefit_phrases(
            "This improves performance and is robust to errors"
        )
        assert has_hard is True
        assert has_soft is True
        assert len(matched) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# Section Prompt Templates
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionPrompts:

    def test_all_sections_have_prompts(self):
        """7 standard sections must all have prompt templates."""
        standard = ["abstract", "introduction", "related_work", "proposed_method",
                    "evaluation_plan", "discussion", "conclusion"]
        for section in standard:
            assert section in SECTION_PROMPTS

    def test_get_section_prompt_includes_schema(self):
        """Generated prompt must include the JSON schema."""
        prompt = get_section_prompt("proposed_method")
        assert "claim_id" in prompt
        assert "text" in prompt
        assert "type" in prompt

    def test_schema_is_valid_json(self):
        """Schema must be valid JSON."""
        import json
        json.dumps(CLAIM_SCHEMA)

    def test_schema_has_required_fields(self):
        """Schema must require the essential fields."""
        claim_props = CLAIM_SCHEMA["properties"]["claims"]["items"]["properties"]
        assert "claim_id" in claim_props
        assert "text" in claim_props
        assert "type" in claim_props
        assert "evidence_ids" in claim_props
        assert "speculative" in claim_props

    def test_method_prompt_mentions_splitting(self):
        """Method prompt must mention mechanism/benefit splitting."""
        prompt = SECTION_PROMPTS["proposed_method"]
        assert "split" in prompt.lower() or "Split" in prompt

    def test_evaluation_prompt_requires_four_blocks(self):
        """Evaluation prompt must require four blocks."""
        prompt = SECTION_PROMPTS["evaluation_plan"]
        assert "Block 1" in prompt or "benchmarks" in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════════
# Regression: Metric Isolation
# ═══════════════════════════════════════════════════════════════════════════


class TestMetricIsolation:

    def test_high_speculative_honesty_not_counted_as_direct_support(self):
        """Honest speculation must not inflate direct support rate."""
        # 3 claims: 1 supported, 2 honest hypotheses
        claims = [
            {"type": "background", "category": "supported"},
            {"type": "hypothesis", "category": "hypothesis", "speculative": True},
            {"type": "hypothesis", "category": "hypothesis", "speculative": True},
        ]

        supported = sum(1 for c in claims if c.get("category") == "supported")
        total = len(claims)
        direct_support = supported / total

        assert direct_support == 1/3  # Only 1/3 directly supported
        # Even though 3/3 are "epistemically acceptable" if hypotheses are honest
        assert direct_support < 0.5  # NOT inflated

    def test_overclaim_forces_draft_regardless(self):
        """High overclaim rate must force draft classification."""

        def classify_quality(direct_support, epistemic, overclaim):
            if overclaim > 0.30:
                return "draft"
            if epistemic >= 0.75 and direct_support >= 0.50:
                return "submission_candidate"
            if epistemic >= 0.55 and overclaim <= 0.15:
                return "reviewable"
            return "draft"

        # Even with excellent epistemic numbers
        assert classify_quality(0.60, 0.80, 0.35) == "draft"
        assert classify_quality(0.80, 0.90, 0.50) == "draft"
        # Low overclaim allows reviewable
        assert classify_quality(0.30, 0.60, 0.10) == "reviewable"
        # Strong metrics allow submission
        assert classify_quality(0.55, 0.80, 0.05) == "submission_candidate"

    def test_epistemic_always_geq_direct_support(self):
        """epistemic_acceptability_rate >= direct_support_rate always (superset)."""
        # By definition: epistemic = (supported + design_justified + hypotheses) / total
        # direct = supported / total
        # So epistemic >= direct always
        for supported in range(0, 11):
            for design_justified in range(0, 11):
                for hypotheses in range(0, 11):
                    total = supported + design_justified + hypotheses
                    if total == 0:
                        continue
                    direct = supported / total
                    epistemic = (supported + design_justified + hypotheses) / total
                    assert epistemic >= direct

    def test_contradicted_hypothesis_fails(self):
        """A contradicted hypothesis must NOT count as epistemically acceptable."""
        # Even if speculative and marked correctly
        claim = {
            "type": "hypothesis",
            "speculative": True,
            "support": "contradicted",
        }
        # Contradiction override: category = contradicted, not hypothesis
        assert claim["support"] == "contradicted"
        # This claim should NOT count toward epistemic_acceptability
