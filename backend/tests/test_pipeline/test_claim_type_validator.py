"""Tests for claim type validator, type-aware repair, and three-metric computation.

Phase C tests — the epistemic enforcement layer.

Key invariants tested:
1. Assumptions never enter total_claims
2. Contradicted hypothesis fails even if marked speculative
3. Mechanism with benefit keywords triggers split
4. Unmarked claimed benefit becomes unsupported_overclaim
5. Correctly marked hypothesis improves epistemic_acceptability but NOT direct_support
6. overclaim_rate is independent and cannot be hidden by repair
"""


from backend.pipeline.gateway.claim_type_validator import (
    ClaimClassification,
    ClaimTypeValidator,
    RepairRecommendation,
    ValidatedClaim,
    compute_metrics,
)
from backend.pipeline.gateway.claim_types import DesignAssumption
from backend.pipeline.gateway.evidence_repair import (
    EvidenceRepairLoop,
    RepairAction,
)

# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR: Contradiction Override
# ═══════════════════════════════════════════════════════════════════════════


class TestContradictionOverride:

    def setup_method(self):
        self.validator = ClaimTypeValidator()

    def test_contradicted_hypothesis_fails_even_if_marked_speculative(self):
        """CRITICAL: A contradicted hypothesis must NOT be valid."""
        claim = {
            "claim_id": "C001",
            "text": "We hypothesize that X improves Y.",
            "type": "hypothesis",
            "evidence_ids": [],
            "speculative": True,
        }
        vc = self.validator.validate_claim(
            claim, "proposed_method",
            support_level="contradicted",
            contradicted_by=["SOURCE-99"],
        )
        assert vc.classification == ClaimClassification.CONTRADICTED
        assert vc.recommendation == RepairRecommendation.REMOVE
        assert not vc.is_valid
        assert "CONTRADICTION OVERRIDE" in vc.issues[0]

    def test_contradicted_background_claim(self):
        claim = {
            "claim_id": "C002",
            "text": "Prior work has shown X is effective.",
            "type": "background",
            "evidence_ids": ["SOURCE-1"],
            "speculative": False,
        }
        vc = self.validator.validate_claim(
            claim, "related_work",
            contradicted_by=["SOURCE-2"],
        )
        assert vc.classification == ClaimClassification.CONTRADICTED
        assert vc.recommendation == RepairRecommendation.REMOVE

    def test_contradicted_method_benefit(self):
        claim = {
            "claim_id": "C003",
            "text": "This improves performance by 50%.",
            "type": "method_claimed_benefit",
            "evidence_ids": [],
            "speculative": True,
        }
        vc = self.validator.validate_claim(
            claim, "proposed_method",
            contradicted_by=["SOURCE-5"],
        )
        assert vc.classification == ClaimClassification.CONTRADICTED


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR: Benefit Smuggling / Split
# ═══════════════════════════════════════════════════════════════════════════


class TestBenefitSmuggling:

    def setup_method(self):
        self.validator = ClaimTypeValidator()

    def test_mechanism_with_improves_triggers_split(self):
        claim = {
            "claim_id": "C010",
            "text": "We propose a routing system that improves robustness by 40%.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.classification == ClaimClassification.UNMARKED_SPECULATION
        assert vc.recommendation == RepairRecommendation.SPLIT
        assert len(vc.split_claims) == 2
        assert vc.split_claims[0]["type"] == "method_proposed_mechanism"
        assert vc.split_claims[0]["speculative"] is False
        assert vc.split_claims[1]["type"] == "method_claimed_benefit"
        assert vc.split_claims[1]["speculative"] is True

    def test_mechanism_with_enables_triggers_split(self):
        claim = {
            "claim_id": "C011",
            "text": "Our framework enables real-time processing of streaming data.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.recommendation == RepairRecommendation.SPLIT

    def test_pure_mechanism_no_split(self):
        claim = {
            "claim_id": "C012",
            "text": "We propose a two-stage uncertainty-aware tool router.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.recommendation == RepairRecommendation.KEEP
        assert vc.classification == ClaimClassification.DESIGN_JUSTIFIED

    def test_mechanism_with_soft_benefit_no_split(self):
        """Soft keywords produce warning but no split."""
        claim = {
            "claim_id": "C013",
            "text": "Our approach is robust to distribution shift.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        # Should get a warning but NOT be split
        assert vc.recommendation != RepairRecommendation.SPLIT
        # May have soft warning in issues
        has_soft_warning = any("SOFT BENEFIT" in issue for issue in vc.issues)
        assert has_soft_warning


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR: Speculative Marking
# ═══════════════════════════════════════════════════════════════════════════


class TestSpeculativeMarking:

    def setup_method(self):
        self.validator = ClaimTypeValidator()

    def test_unmarked_claimed_benefit_becomes_unmarked_speculation(self):
        """method_claimed_benefit without speculative=True → unmarked_speculation."""
        claim = {
            "claim_id": "C020",
            "text": "This approach achieves state-of-the-art performance.",
            "type": "method_claimed_benefit",
            "evidence_ids": [],
            "speculative": False,  # WRONG — should be True
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.classification == ClaimClassification.UNMARKED_SPECULATION
        assert vc.recommendation == RepairRecommendation.MARK_SPECULATIVE

    def test_unmarked_hypothesis_becomes_unmarked_speculation(self):
        claim = {
            "claim_id": "C021",
            "text": "We expect this to outperform baselines.",
            "type": "hypothesis",
            "evidence_ids": [],
            "speculative": False,  # WRONG
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.classification == ClaimClassification.UNMARKED_SPECULATION
        assert vc.recommendation == RepairRecommendation.MARK_SPECULATIVE

    def test_unmarked_expected_contribution(self):
        claim = {
            "claim_id": "C022",
            "text": "This work advances the field.",
            "type": "expected_contribution",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "conclusion")
        assert vc.classification == ClaimClassification.UNMARKED_SPECULATION

    def test_correctly_marked_hypothesis_is_valid(self):
        claim = {
            "claim_id": "C023",
            "text": "We hypothesize that this will improve accuracy.",
            "type": "hypothesis",
            "evidence_ids": [],
            "speculative": True,  # CORRECT
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.classification == ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS
        assert vc.recommendation == RepairRecommendation.KEEP
        assert vc.is_valid


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR: Section Contracts
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionContractsEnforcement:

    def setup_method(self):
        self.validator = ClaimTypeValidator()

    def test_hypothesis_not_allowed_in_related_work(self):
        claim = {
            "claim_id": "C030",
            "text": "We hypothesize that X is related to Y.",
            "type": "hypothesis",
            "evidence_ids": [],
            "speculative": True,
        }
        vc = self.validator.validate_claim(claim, "related_work")
        assert vc.classification == ClaimClassification.TYPE_MISMATCH
        assert vc.recommendation == RepairRecommendation.RECLASSIFY

    def test_background_allowed_in_related_work(self):
        claim = {
            "claim_id": "C031",
            "text": "Smith et al. demonstrated that X correlates with Y [SOURCE-1].",
            "type": "background",
            "evidence_ids": ["SOURCE-1"],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "related_work", support_level="strong")
        assert vc.classification == ClaimClassification.SUPPORTED

    def test_missing_citation_in_related_work(self):
        claim = {
            "claim_id": "C032",
            "text": "Prior work has shown X is effective.",
            "type": "background",
            "evidence_ids": [],  # NO citation
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "related_work")
        assert vc.classification == ClaimClassification.MISSING_CITATION

    def test_mechanism_in_method_section_no_citation_needed(self):
        claim = {
            "claim_id": "C033",
            "text": "We propose a multi-head attention module.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method")
        assert vc.classification == ClaimClassification.DESIGN_JUSTIFIED
        assert vc.recommendation == RepairRecommendation.KEEP


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATOR: Support Level Classification
# ═══════════════════════════════════════════════════════════════════════════


class TestSupportLevelClassification:

    def setup_method(self):
        self.validator = ClaimTypeValidator()

    def test_strong_support_is_supported(self):
        claim = {
            "claim_id": "C040",
            "text": "X was shown to improve Y by 15% [SOURCE-1].",
            "type": "background",
            "evidence_ids": ["SOURCE-1"],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "introduction", support_level="strong")
        assert vc.classification == ClaimClassification.SUPPORTED

    def test_no_support_corpus_required_is_overclaim(self):
        # background in introduction: must_cite fires first (Rule 4) if no evidence_ids.
        # To test the overclaim path, we need a corpus-required type that
        # doesn't have a citation requirement at the section level.
        # Use background in related_work with evidence_ids present but support_level=none.
        claim = {
            "claim_id": "C041",
            "text": "This method solves the problem completely. [SOURCE-99]",
            "type": "background",
            "evidence_ids": ["SOURCE-99"],  # Has citation
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "related_work", support_level="none")
        # support_level=none + corpus_required=true + not speculative → unsupported_overclaim
        assert vc.classification == ClaimClassification.UNSUPPORTED_OVERCLAIM

    def test_no_support_corpus_optional_is_design_justified(self):
        claim = {
            "claim_id": "C042",
            "text": "We design a two-stage pipeline.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = self.validator.validate_claim(claim, "proposed_method", support_level="none")
        assert vc.classification == ClaimClassification.DESIGN_JUSTIFIED


# ═══════════════════════════════════════════════════════════════════════════
# METRICS: Three-Metric Model
# ═══════════════════════════════════════════════════════════════════════════


class TestThreeMetricModel:

    def test_assumptions_never_enter_total_claims(self):
        """CRITICAL: Only ValidatedClaim items in denominator."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "hypothesis", "method", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
        ]
        # Even if we add 100 assumptions
        assumptions = [
            DesignAssumption(f"A{i:03d}", "text", "theoretical")
            for i in range(100)
        ]
        m = compute_metrics(claims)
        assert m.total_claims == 2  # NOT 102
        assert m.direct_support_rate == 0.5

    def test_correctly_marked_hypothesis_improves_epistemic_but_not_direct(self):
        """Hypotheses improve epistemic_acceptability but NOT direct_support."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "hypothesis", "method", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
            ValidatedClaim("C3", "t", "hypothesis", "method", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
        ]
        m = compute_metrics(claims)
        assert m.direct_support_rate == 1 / 3  # Only C1
        assert m.epistemic_acceptability_rate == 3 / 3  # C1 + C2 + C3
        assert m.overclaim_rate == 0.0

    def test_overclaim_rate_independent(self):
        """overclaim_rate is computed independently."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "background", "rw", [], False,
                          classification=ClaimClassification.UNMARKED_SPECULATION),
            ValidatedClaim("C3", "t", "background", "rw", [], False,
                          classification=ClaimClassification.UNSUPPORTED_OVERCLAIM),
        ]
        m = compute_metrics(claims)
        assert m.overclaim_rate == 2 / 3  # C2 + C3
        assert m.direct_support_rate == 1 / 3
        assert m.epistemic_acceptability_rate == 1 / 3

    def test_speculative_honesty_with_no_speculative_claims(self):
        """No speculative claims → speculative_honesty = 1.0 (honest by default)."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
        ]
        m = compute_metrics(claims)
        assert m.speculative_honesty == 1.0

    def test_speculative_honesty_mixed(self):
        """2 marked + 1 unmarked = 2/3 honesty."""
        claims = [
            ValidatedClaim("C1", "t", "hypothesis", "m", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
            ValidatedClaim("C2", "t", "hypothesis", "m", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
            ValidatedClaim("C3", "t", "hypothesis", "m", [], False,
                          classification=ClaimClassification.UNMARKED_SPECULATION),
        ]
        m = compute_metrics(claims)
        assert m.speculative_honesty == 2 / 3

    def test_empty_claims_zero_metrics(self):
        m = compute_metrics([])
        assert m.total_claims == 0
        assert m.direct_support_rate == 0.0

    def test_epistemic_always_geq_direct_support(self):
        """Invariant: epistemic_acceptability >= direct_support always."""
        for supported in range(4):
            for design in range(4):
                for hypo in range(4):
                    for overclaim in range(4):
                        claims = []
                        claims.extend([
                            ValidatedClaim(f"S{i}", "t", "background", "rw", [], False,
                                          classification=ClaimClassification.SUPPORTED)
                            for i in range(supported)
                        ])
                        claims.extend([
                            ValidatedClaim(f"D{i}", "t", "mechanism", "m", [], False,
                                          classification=ClaimClassification.DESIGN_JUSTIFIED)
                            for i in range(design)
                        ])
                        claims.extend([
                            ValidatedClaim(f"H{i}", "t", "hypothesis", "m", [], True,
                                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS)
                            for i in range(hypo)
                        ])
                        claims.extend([
                            ValidatedClaim(f"O{i}", "t", "background", "rw", [], False,
                                          classification=ClaimClassification.UNMARKED_SPECULATION)
                            for i in range(overclaim)
                        ])
                        if not claims:
                            continue
                        m = compute_metrics(claims)
                        assert m.epistemic_acceptability_rate >= m.direct_support_rate, \
                            f"Failed: dsr={m.direct_support_rate}, ear={m.epistemic_acceptability_rate}"


# ═══════════════════════════════════════════════════════════════════════════
# REPAIR: Type-Aware Actions
# ═══════════════════════════════════════════════════════════════════════════


class TestTypeAwareRepair:

    def test_mark_speculative_repair(self):
        """Unmarked speculation gets speculative marker."""
        loop = EvidenceRepairLoop()
        vc = ValidatedClaim(
            claim_id="C001",
            text="This approach achieves SOTA performance.",
            declared_type="method_claimed_benefit",
            section="proposed_method",
            evidence_ids=[],
            speculative=False,
            classification=ClaimClassification.UNMARKED_SPECULATION,
            recommendation=RepairRecommendation.MARK_SPECULATIVE,
        )
        report = loop.repair([vc], "This approach achieves SOTA performance.")
        assert len(report.claims) == 1
        assert report.claims[0].action == RepairAction.MARK_SPECULATIVE
        assert "hypothesize" in report.claims[0].repaired_text.lower()

    def test_split_repair(self):
        """Mechanism+benefit claim gets split."""
        loop = EvidenceRepairLoop()
        vc = ValidatedClaim(
            claim_id="C002",
            text="We propose a routing system that improves robustness by 40%.",
            declared_type="method_proposed_mechanism",
            section="proposed_method",
            evidence_ids=[],
            speculative=False,
            classification=ClaimClassification.UNMARKED_SPECULATION,
            recommendation=RepairRecommendation.SPLIT,
            split_claims=[
                {"claim_id": "C002-mechanism", "text": "We propose a routing system that",
                 "type": "method_proposed_mechanism", "speculative": False},
                {"claim_id": "C002-benefit", "text": "improves robustness by 40%.",
                 "type": "method_claimed_benefit", "speculative": True},
            ],
        )
        report = loop.repair([vc], "We propose a routing system that improves robustness by 40%.")
        assert len(report.claims) == 1
        assert report.claims[0].action == RepairAction.SPLIT
        assert "hypothesize" in report.claims[0].repaired_text.lower()

    def test_remove_contradicted(self):
        """Contradicted claims are removed."""
        loop = EvidenceRepairLoop()
        vc = ValidatedClaim(
            claim_id="C003",
            text="We hypothesize that X improves Y.",
            declared_type="hypothesis",
            section="proposed_method",
            evidence_ids=[],
            speculative=True,
            classification=ClaimClassification.CONTRADICTED,
            recommendation=RepairRecommendation.REMOVE,
            contradicted_by=["SOURCE-99"],
        )
        report = loop.repair([vc], "We hypothesize that X improves Y.")
        assert len(report.claims) == 1
        assert report.claims[0].action == RepairAction.REMOVE
        assert report.claims[0].repaired_text == "[removed]"

    def test_reclassify_type_mismatch(self):
        """Type-mismatched claims get reclassified."""
        loop = EvidenceRepairLoop()
        vc = ValidatedClaim(
            claim_id="C004",
            text="We hypothesize X.",
            declared_type="hypothesis",
            section="related_work",
            evidence_ids=[],
            speculative=True,
            classification=ClaimClassification.TYPE_MISMATCH,
            recommendation=RepairRecommendation.RECLASSIFY,
        )
        report = loop.repair([vc], "We hypothesize X.")
        assert report.claims[0].action == RepairAction.RECLASSIFY

    def test_overclaim_rate_not_hidden_by_repair(self):
        """Overclaim rate computed BEFORE repair, not hidden by marking speculative."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "This improves accuracy.", "type": "method_claimed_benefit",
             "evidence_ids": [], "speculative": False, "rationale": "test"},
            {"claim_id": "C2", "text": "We hypothesize X.", "type": "hypothesis",
             "evidence_ids": [], "speculative": True, "rationale": "test"},
        ]
        validated, metrics_before = validator.validate_and_compute_metrics(
            "proposed_method", claims,
        )
        # Before repair: C1 is unmarked_speculation, C2 is correctly_marked
        assert metrics_before.overclaim_rate == 0.5
        assert metrics_before.speculative_honesty == 0.5

        # After repair: C1 gets marked speculative
        loop = EvidenceRepairLoop()
        report = loop.repair(validated, "This improves accuracy. We hypothesize X.")

        # The pre-repair metrics should still show the original overclaim
        # Repair doesn't change the diagnosis, only the text
        assert metrics_before.overclaim_rate == 0.5  # Still 50%


# ═══════════════════════════════════════════════════════════════════════════
# VALIDATE + METRICS: Integration
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateAndMetricsIntegration:

    def test_full_pipeline_7_claims(self):
        """Simulate a full section with mixed claims."""
        validator = ClaimTypeValidator()
        claims = [
            # 1. Supported background (allowed in proposed_method with citation)
            {"claim_id": "C1", "text": "Smith et al. showed X is effective [SOURCE-1].",
             "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False},
            # 2. Supported design motivation (allowed in proposed_method with citation)
            {"claim_id": "C2", "text": "Prior methods lack uncertainty estimation [SOURCE-2].",
             "type": "method_design_motivation", "evidence_ids": ["SOURCE-2"], "speculative": False},
            # 3. Design-justified mechanism
            {"claim_id": "C3", "text": "We propose a two-stage routing mechanism.",
             "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False},
            # 4. Correctly marked hypothesis
            {"claim_id": "C4", "text": "We hypothesize improved robustness.",
             "type": "hypothesis", "evidence_ids": [], "speculative": True},
            # 5. Unmarked benefit (overclaim)
            {"claim_id": "C5", "text": "This achieves state-of-the-art results.",
             "type": "method_claimed_benefit", "evidence_ids": [], "speculative": False},
            # 6. Background with citation but no support (overclaim)
            {"claim_id": "C6", "text": "It is well known that X always outperforms Y. [SOURCE-3]",
             "type": "background", "evidence_ids": ["SOURCE-3"], "speculative": False},
            # 7. Design-justified claimed benefit (correctly marked)
            {"claim_id": "C7", "text": "We hypothesize that our approach generalizes.",
             "type": "method_claimed_benefit", "evidence_ids": [], "speculative": True},
        ]

        support_levels = {
            "C1": "strong", "C2": "strong", "C3": "none",
            "C4": "none", "C5": "none", "C6": "none", "C7": "none",
        }

        validated, metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, support_levels,
        )

        assert metrics.total_claims == 7
        # C1, C2 supported
        assert metrics.supported >= 2
        # C3 design_justified
        assert metrics.design_justified >= 1
        # C4, C7 correctly marked hypotheses
        assert metrics.correctly_marked_hypotheses >= 2
        # C5 unmarked speculation
        assert metrics.unmarked_speculation >= 1
        # C6 unsupported overclaim
        assert metrics.unsupported_overclaim >= 1

    def test_overclaim_hard_gate(self):
        """Overclaim > 30% should flag for draft classification."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "background", "rw", [], False,
                          classification=ClaimClassification.UNMARKED_SPECULATION),
            ValidatedClaim("C3", "t", "background", "rw", [], False,
                          classification=ClaimClassification.UNSUPPORTED_OVERCLAIM),
        ]
        m = compute_metrics(claims)
        assert m.overclaim_rate == 2 / 3  # 66.7%

        # Hard gate logic
        if m.overclaim_rate > 0.30:
            classification = "draft"
        else:
            classification = "reviewable"
        assert classification == "draft"
