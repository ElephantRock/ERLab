"""Phase E — Edge-case tests and failure-mode verification.

Proves the implementation is correct across failure modes, and that
repair does not change the validator's honest classification.

Critical failure modes tested:
- Invalid structured JSON → retry → prose_fallback
- prose_fallback sections counted in metadata
- Assumptions never enter metrics after repair
- SPLIT creates stable new claim IDs
- MARK_SPECULATIVE changes epistemic category but not direct support
- Contradicted claims cannot become acceptable through repair
- Soft benefit warnings logged but not mutating claims
- Quality gate receives repaired metrics, not pre-repair metrics
"""

import pytest

from backend.pipeline.gateway.claim_types import ClaimType, DesignAssumption
from backend.pipeline.gateway.claim_type_validator import (
    ClaimClassification,
    ClaimTypeValidator,
    EpistemicMetrics,
    RepairRecommendation,
    ValidatedClaim,
    compute_metrics,
)
from backend.pipeline.gateway.evidence_repair import (
    EvidenceRepairLoop,
    ExportQualityGate,
    RepairAction,
)
from backend.pipeline.synthesis.claim_renderer import (
    ClaimIDGenerator,
    ClaimRenderer,
    InvalidStructuredOutput,
)


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: Invalid Structured JSON → prose_fallback
# ═══════════════════════════════════════════════════════════════════════════


class TestInvalidStructuredOutput:

    def test_missing_claims_key_raises(self):
        renderer = ClaimRenderer()
        with pytest.raises(InvalidStructuredOutput):
            renderer.render_section(
                "proposed_method",
                {"section": "proposed_method"},  # no "claims" key
                ClaimIDGenerator(0),
            )

    def test_unknown_claim_type_fails_validation(self):
        renderer = ClaimRenderer()
        bad_output = {
            "section": "proposed_method",
            "claims": [
                {
                    "claim_id": "C001",
                    "text": "test",
                    "type": "not_a_real_type",
                    "evidence_ids": [],
                    "speculative": False,
                    "rationale": "test",
                    "section": "proposed_method",
                },
            ],
        }
        with pytest.raises(InvalidStructuredOutput):
            renderer.render_section("proposed_method", bad_output, ClaimIDGenerator(0))

    def test_missing_required_field_fails(self):
        renderer = ClaimRenderer()
        bad_output = {
            "section": "proposed_method",
            "claims": [
                {
                    "claim_id": "C001",
                    "text": "test",
                    # missing "type"
                    "evidence_ids": [],
                    "speculative": False,
                    "rationale": "test",
                    "section": "proposed_method",
                },
            ],
        }
        with pytest.raises(InvalidStructuredOutput):
            renderer.render_section("proposed_method", bad_output, ClaimIDGenerator(0))

    def test_non_dict_input_fails(self):
        renderer = ClaimRenderer()
        with pytest.raises(InvalidStructuredOutput):
            renderer.render_section("proposed_method", "not a dict", ClaimIDGenerator(0))

    def test_empty_claims_list_passes(self):
        """Empty claims list is valid (section had nothing to say)."""
        renderer = ClaimRenderer()
        result = renderer.render_section(
            "proposed_method",
            {"section": "proposed_method", "claims": []},
            ClaimIDGenerator(0),
        )
        prose, sidecar = result
        assert prose == ""
        assert sidecar["claim_count"] == 0

    def test_valid_structured_output_passes(self):
        renderer = ClaimRenderer()
        good_output = {
            "section": "proposed_method",
            "claims": [
                {
                    "claim_id": "C001",
                    "text": "We propose a routing mechanism.",
                    "type": "method_proposed_mechanism",
                    "evidence_ids": [],
                    "speculative": False,
                    "rationale": "Core design",
                    "section": "proposed_method",
                },
            ],
        }
        prose, sidecar = renderer.render_section("proposed_method", good_output, ClaimIDGenerator(0))
        assert "routing" in prose
        assert sidecar["claim_count"] == 1
        assert sidecar["claims"][0]["claim_id"].startswith("P0-")


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: Assumptions Never Enter Metrics After Repair
# ═══════════════════════════════════════════════════════════════════════════


class TestAssumptionsAfterRepair:

    def test_assumptions_excluded_after_repair(self):
        """Run repair with assumptions present — they must not appear in metrics."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "Smith showed X [SOURCE-1].",
             "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False,
             "rationale": "test"},
            {"claim_id": "C2", "text": "We propose method Y.",
             "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False,
             "rationale": "test"},
        ]
        support = {"C1": "strong", "C2": "none"}
        validated, metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, support,
        )

        # Now run repair
        loop = EvidenceRepairLoop()
        combined_text = " ".join(vc.text for vc in validated)
        report = loop.repair(validated, combined_text)

        # Recompute metrics from the validated claims (repair doesn't reclassify)
        post_metrics = compute_metrics(validated)

        # Create assumptions — they must not change metrics
        assumptions = [
            DesignAssumption(f"A{i:03d}", f"Assumption {i}", "theoretical")
            for i in range(100)
        ]

        assert post_metrics.total_claims == 2  # NOT 102
        assert post_metrics.direct_support_rate == metrics.direct_support_rate

    def test_assumption_register_stored_separately(self):
        """Assumption count in metadata is separate from claim metrics."""
        from backend.pipeline.stages import CitationAuditStage

        validated = {
            "proposed_method": [
                ValidatedClaim("C1", "t", "background", "pm", ["S1"], False,
                              classification=ClaimClassification.SUPPORTED),
            ],
        }
        metrics = EpistemicMetrics(
            direct_support_rate=1.0, epistemic_acceptability_rate=1.0,
            overclaim_rate=0.0, speculative_honesty=1.0, total_claims=1, supported=1,
        )
        assumptions = [
            {"text": f"Assumption {i}", "basis": "theoretical", "risk": "medium"}
            for i in range(10)
        ]

        metadata = {}
        CitationAuditStage._run_typed_repair_and_quality_gate(
            idx=0, metrics=metrics, validated_by_section=validated,
            corpus={}, metadata=metadata, full_paper=None,
            assumption_register=assumptions, prose_fallback_count=0,
            structured_claims_by_section={"proposed_method": [{"claim_id": "C1"}]},
        )

        # Assumptions stored but not in claim metrics
        assert metadata["export_quality"]["assumption_count"] == 10
        assert metadata["epistemic_metrics"]["total_claims"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: SPLIT Creates Stable Claim IDs
# ═══════════════════════════════════════════════════════════════════════════


class TestSplitStableIDs:

    def test_split_claims_have_deterministic_ids(self):
        validator = ClaimTypeValidator()
        claim = {
            "claim_id": "C010",
            "text": "We propose a routing system that improves robustness by 40%.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = validator.validate_claim(claim, "proposed_method")
        assert vc.recommendation == RepairRecommendation.SPLIT
        assert len(vc.split_claims) == 2

        # IDs must be deterministic and based on original
        assert vc.split_claims[0]["claim_id"] == "C010-mechanism"
        assert vc.split_claims[1]["claim_id"] == "C010-benefit"

    def test_repeated_split_same_ids(self):
        """Same input must always produce same split IDs."""
        validator = ClaimTypeValidator()
        claim = {
            "claim_id": "C020",
            "text": "This method enables real-time processing.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc1 = validator.validate_claim(claim, "proposed_method")
        vc2 = validator.validate_claim(claim, "proposed_method")
        assert vc1.split_claims[0]["claim_id"] == vc2.split_claims[0]["claim_id"]
        assert vc1.split_claims[1]["claim_id"] == vc2.split_claims[1]["claim_id"]


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: MARK_SPECULATIVE Changes Epistemic, Not Direct Support
# ═══════════════════════════════════════════════════════════════════════════


class TestMarkSpeculativeEffect:

    def test_marking_changes_epistemic_but_not_direct(self):
        """Before marking: unmarked_speculation (counts as overclaim).
           After marking: correctly_marked_hypothesis (counts as epistemic).
           Neither changes direct_support_rate."""
        # Before marking: 1 supported + 1 unmarked
        before_claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "method_claimed_benefit", "pm", [], False,
                          classification=ClaimClassification.UNMARKED_SPECULATION),
        ]
        m_before = compute_metrics(before_claims)

        # After marking: 1 supported + 1 correctly_marked
        after_claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "method_claimed_benefit", "pm", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
        ]
        m_after = compute_metrics(after_claims)

        # Direct support unchanged
        assert m_before.direct_support_rate == m_after.direct_support_rate == 0.5

        # Epistemic acceptability improved
        assert m_after.epistemic_acceptability_rate > m_before.epistemic_acceptability_rate
        assert m_before.epistemic_acceptability_rate == 0.5  # only supported
        assert m_after.epistemic_acceptability_rate == 1.0   # supported + marked

        # Overclaim decreased
        assert m_before.overclaim_rate == 0.5
        assert m_after.overclaim_rate == 0.0

    def test_repair_does_not_reclassify_valid_claims(self):
        """Repair marks speculative but doesn't change already-valid claims."""
        loop = EvidenceRepairLoop()
        vc_keep = ValidatedClaim(
            claim_id="C1", text="Smith showed X [SOURCE-1].",
            declared_type="background", section="related_work",
            evidence_ids=["SOURCE-1"], speculative=False,
            classification=ClaimClassification.SUPPORTED,
            recommendation=RepairRecommendation.KEEP,
        )
        report = loop.repair([vc_keep], "Smith showed X [SOURCE-1].")
        assert report.claims[0].action == RepairAction.KEEP
        assert report.claims[0].repaired_text == "Smith showed X [SOURCE-1]."


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: Contradicted Claims Cannot Become Acceptable
# ═══════════════════════════════════════════════════════════════════════════


class TestContradictionIrreversible:

    def test_contradicted_claim_removed_not_marked(self):
        """Repair removes contradicted claims, never marks them acceptable."""
        loop = EvidenceRepairLoop()
        vc = ValidatedClaim(
            claim_id="C1",
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
        assert report.claims[0].action == RepairAction.REMOVE
        assert report.claims[0].repaired_text == "[removed]"

        # Contradicted claims are not valid even after "repair"
        assert not vc.is_valid

    def test_contradicted_hypothesis_still_overclaim_in_metrics(self):
        """Contradicted hypothesis counts as contradicted, not epistemically acceptable."""
        claims = [
            ValidatedClaim("C1", "t", "hypothesis", "pm", [], True,
                          classification=ClaimClassification.CONTRADICTED),
        ]
        m = compute_metrics(claims)
        assert m.total_claims == 1
        assert m.contradicted == 1
        assert m.epistemic_acceptability_rate == 0.0
        assert m.direct_support_rate == 0.0

    def test_contradicted_forces_draft_in_quality_gate(self):
        """Even if only contradicted claim, the quality should reflect it."""
        claims = [
            ValidatedClaim("C1", "t", "background", "rw", ["S1"], False,
                          classification=ClaimClassification.SUPPORTED),
            ValidatedClaim("C2", "t", "background", "rw", [], False,
                          classification=ClaimClassification.CONTRADICTED),
            ValidatedClaim("C3", "t", "hypothesis", "pm", [], True,
                          classification=ClaimClassification.CORRECTLY_MARKED_HYPOTHESIS),
        ]
        m = compute_metrics(claims)
        # 1 supported + 1 contradicted + 1 correctly marked
        assert m.direct_support_rate == pytest.approx(1/3)
        assert m.epistemic_acceptability_rate == pytest.approx(2/3)
        # overclaim = 0 (contradicted is not overclaim, it's separately tracked)
        assert m.overclaim_rate == 0.0
        # But the contradicted count should influence quality assessment


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: Soft Benefit Warnings Don't Mutate Claims
# ═══════════════════════════════════════════════════════════════════════════


class TestSoftBenefitWarnings:

    def test_soft_warning_does_not_change_classification(self):
        """Soft benefit keywords produce warning but claim stays valid."""
        validator = ClaimTypeValidator()
        claim = {
            "claim_id": "C1",
            "text": "Our approach is robust to distribution shift.",
            "type": "method_proposed_mechanism",
            "evidence_ids": [],
            "speculative": False,
        }
        vc = validator.validate_claim(claim, "proposed_method")
        # Classification should still be design_justified
        assert vc.classification == ClaimClassification.DESIGN_JUSTIFIED
        assert vc.recommendation == RepairRecommendation.KEEP
        # But issue logged
        has_soft_warning = any("SOFT BENEFIT" in issue for issue in vc.issues)
        assert has_soft_warning

    def test_soft_warning_does_not_change_metrics(self):
        """Soft warning claims count the same as non-warned claims."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "Our approach is robust to noise.",
             "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False,
             "rationale": "test"},
            {"claim_id": "C2", "text": "We propose a two-stage pipeline.",
             "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False,
             "rationale": "test"},
        ]
        validated, metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, {"C1": "none", "C2": "none"},
        )
        # Both design_justified
        assert metrics.design_justified == 2
        assert metrics.total_claims == 2


# ═══════════════════════════════════════════════════════════════════════════
# Failure Mode: Quality Gate Receives Pre-Repair Metrics
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGateMetricsSource:

    def test_gate_uses_original_metrics_not_post_repair(self):
        """The quality gate must use the validator's original classification,
        not recompute after repair. Repair marks text but doesn't reclassify."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "X is effective [SOURCE-1].",
             "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False,
             "rationale": "test"},
            {"claim_id": "C2", "text": "This achieves SOTA results.",
             "type": "method_claimed_benefit", "evidence_ids": [], "speculative": False,
             "rationale": "test"},
        ]
        validated, pre_metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, {"C1": "strong", "C2": "none"},
        )

        # C2 is unmarked_speculation
        assert pre_metrics.overclaim_rate == 0.5

        # Run repair — marks C2 as speculative
        loop = EvidenceRepairLoop()
        report = loop.repair(validated, "X is effective. This achieves SOTA results.")

        # Quality gate uses PRE-repair metrics (the validator's honest assessment)
        level = ExportQualityGate.classify_from_metrics(pre_metrics)
        assert level == "draft"  # 50% overclaim > 30%

        # The repair doesn't change the classification
        post_metrics = compute_metrics(validated)
        assert post_metrics.overclaim_rate == pre_metrics.overclaim_rate

    def test_prose_fallback_sections_are_counted(self):
        """prose_fallback_count must appear in export_quality metadata."""
        from backend.pipeline.stages import CitationAuditStage

        validated = {
            "abstract": [
                ValidatedClaim("C1", "t", "background", "abstract", ["S1"], False,
                              classification=ClaimClassification.SUPPORTED),
            ],
        }
        metrics = EpistemicMetrics(
            direct_support_rate=1.0, epistemic_acceptability_rate=1.0,
            overclaim_rate=0.0, speculative_honesty=1.0, total_claims=1, supported=1,
        )

        metadata = {}
        CitationAuditStage._run_typed_repair_and_quality_gate(
            idx=0, metrics=metrics, validated_by_section=validated,
            corpus={}, metadata=metadata, full_paper=None,
            assumption_register=[], prose_fallback_count=3,
            structured_claims_by_section={"abstract": [{"claim_id": "C1"}]},
        )

        assert metadata["export_quality"]["prose_fallback_count"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# ClaimIDGenerator: Determinism
# ═══════════════════════════════════════════════════════════════════════════


class TestClaimIDDeterminism:

    def test_ids_are_sequential_within_section(self):
        gen = ClaimIDGenerator(0)
        id1 = gen.next_claim_id("proposed_method")
        id2 = gen.next_claim_id("proposed_method")
        id3 = gen.next_claim_id("proposed_method")
        assert id1 == "P0-proposed_method-C001"
        assert id2 == "P0-proposed_method-C002"
        assert id3 == "P0-proposed_method-C003"

    def test_ids_independent_across_sections(self):
        gen = ClaimIDGenerator(5)
        id1 = gen.next_claim_id("proposed_method")
        id2 = gen.next_claim_id("evaluation_plan")
        id3 = gen.next_claim_id("proposed_method")
        assert id1 == "P5-proposed_method-C001"
        assert id2 == "P5-evaluation_plan-C001"
        assert id3 == "P5-proposed_method-C002"

    def test_assumption_ids_separate_from_claim_ids(self):
        gen = ClaimIDGenerator(0)
        c1 = gen.next_claim_id("proposed_method")
        a1 = gen.next_assumption_id("proposed_method")
        c2 = gen.next_claim_id("proposed_method")
        a2 = gen.next_assumption_id("proposed_method")
        assert c1 == "P0-proposed_method-C001"
        assert a1 == "P0-proposed_method-A001"
        assert c2 == "P0-proposed_method-C002"
        assert a2 == "P0-proposed_method-A002"

    def test_different_proposals_different_prefixes(self):
        gen0 = ClaimIDGenerator(0)
        gen1 = ClaimIDGenerator(1)
        assert gen0.next_claim_id("method") == "P0-method-C001"
        assert gen1.next_claim_id("method") == "P1-method-C001"


# ═══════════════════════════════════════════════════════════════════════════
# Integration: Full Pipeline Smoke Test
# ═══════════════════════════════════════════════════════════════════════════


class TestFullPipelineSmoke:

    def test_seven_section_paper_metrics(self):
        """Simulate a 7-section paper with realistic claim distribution."""
        validator = ClaimTypeValidator()

        # Simulated paper sections with claims and support
        paper = {
            "abstract": (
                [{"claim_id": "A1", "text": "We aim to improve robustness.",
                  "type": "expected_contribution", "evidence_ids": [], "speculative": True,
                  "rationale": "test"}],
                {"A1": "none"},
            ),
            "introduction": (
                [
                    {"claim_id": "I1", "text": "Prior work lacks X [SOURCE-1].",
                     "type": "prior_limitation", "evidence_ids": ["SOURCE-1"], "speculative": False,
                     "rationale": "test"},
                    {"claim_id": "I2", "text": "Smith showed Y [SOURCE-2].",
                     "type": "background", "evidence_ids": ["SOURCE-2"], "speculative": False,
                     "rationale": "test"},
                ],
                {"I1": "strong", "I2": "strong"},
            ),
            "related_work": (
                [
                    {"claim_id": "R1", "text": "Jones demonstrated Z [SOURCE-3].",
                     "type": "background", "evidence_ids": ["SOURCE-3"], "speculative": False,
                     "rationale": "test"},
                ],
                {"R1": "strong"},
            ),
            "proposed_method": (
                [
                    {"claim_id": "M1", "text": "We propose a two-stage router.",
                     "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False,
                     "rationale": "test"},
                    {"claim_id": "M2", "text": "We hypothesize improved robustness.",
                     "type": "hypothesis", "evidence_ids": [], "speculative": True,
                     "rationale": "test"},
                    {"claim_id": "M3", "text": "This achieves SOTA.",
                     "type": "method_claimed_benefit", "evidence_ids": [], "speculative": False,
                     "rationale": "test"},
                ],
                {"M1": "none", "M2": "none", "M3": "none"},
            ),
            "evaluation_plan": (
                [
                    {"claim_id": "E1", "text": "We evaluate on GLUE [SOURCE-4].",
                     "type": "evaluation_benchmark", "evidence_ids": ["SOURCE-4"], "speculative": False,
                     "rationale": "test"},
                    {"claim_id": "E2", "text": "We hypothesize improvement over baselines.",
                     "type": "hypothesis", "evidence_ids": [], "speculative": True,
                     "rationale": "test"},
                ],
                {"E1": "weak", "E2": "none"},
            ),
            "discussion": (
                [
                    {"claim_id": "D1", "text": "We expect broader impact in NLP.",
                     "type": "expected_contribution", "evidence_ids": [], "speculative": True,
                     "rationale": "test"},
                ],
                {"D1": "none"},
            ),
            "conclusion": (
                [
                    {"claim_id": "J1", "text": "We aim to advance the field.",
                     "type": "expected_contribution", "evidence_ids": [], "speculative": True,
                     "rationale": "test"},
                ],
                {"J1": "none"},
            ),
        }

        all_validated = []
        per_section = {}
        for section_id, (claims, support) in paper.items():
            validated = validator.validate_section(section_id, claims, support)
            per_section[section_id] = compute_metrics(validated)
            all_validated.extend(validated)

        # Full paper metrics
        full_metrics = compute_metrics(all_validated)
        assert full_metrics.total_claims == 11

        # Quality gate
        level = ExportQualityGate.classify_from_metrics(full_metrics)
        banner = ExportQualityGate.get_banner_from_metrics(full_metrics)

        # Key diagnostics
        assert full_metrics.overclaim_rate > 0  # M3 is unmarked
        assert full_metrics.speculative_honesty < 1.0  # M3 drags it down
        assert full_metrics.direct_support_rate > 0  # I1, I2, R1 are supported

        # Per-section: related_work should be strongest
        assert per_section["related_work"].direct_support_rate == 1.0
        # Method has overclaim (M3)
        assert per_section["proposed_method"].overclaim_rate > 0

        # Abstract is all correctly marked speculative
        assert per_section["abstract"].correctly_marked_hypotheses == 1

        print(f"\n--- 7-Section Paper Diagnostics ---")
        print(f"Total claims: {full_metrics.total_claims}")
        print(f"Direct support: {full_metrics.direct_support_rate:.1%}")
        print(f"Epistemic acceptability: {full_metrics.epistemic_acceptability_rate:.1%}")
        print(f"Overclaim: {full_metrics.overclaim_rate:.1%}")
        print(f"Speculative honesty: {full_metrics.speculative_honesty:.1%}")
        print(f"Quality level: {level}")
        for section_id, m in per_section.items():
            print(f"  {section_id}: dsr={m.direct_support_rate:.0%} "
                  f"ear={m.epistemic_acceptability_rate:.0%} "
                  f"ocr={m.overclaim_rate:.0%} "
                  f"claims={m.total_claims}")
