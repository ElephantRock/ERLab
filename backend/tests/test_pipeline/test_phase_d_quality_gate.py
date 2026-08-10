"""Tests for Phase D — quality gate integration, typed stage wiring, full metadata.

Key invariants:
1. Quality gate consumes validator output, never recomputes
2. overclaim > 30% → always draft
3. CitationAuditStage uses typed validator when structured_claims exist
4. CitationAuditStage falls back cleanly when only prose exists
5. Full metadata includes all required fields
"""

import pytest

from backend.pipeline.gateway.claim_type_validator import (
    ClaimClassification,
    ClaimTypeValidator,
    EpistemicMetrics,
    ValidatedClaim,
)
from backend.pipeline.gateway.evidence_repair import ExportQualityGate

# ═══════════════════════════════════════════════════════════════════════════
# Quality Gate: Three-Metric Classification
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGateThreeMetrics:

    def test_overclaim_gt_30_always_draft(self):
        """Hard gate: overclaim > 30% forces draft regardless of other metrics."""
        m = EpistemicMetrics(
            direct_support_rate=0.80,
            epistemic_acceptability_rate=0.95,
            overclaim_rate=0.35,
            speculative_honesty=0.99,
            total_claims=100,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "draft"

    def test_overclaim_exactly_30_not_draft_but_blocked(self):
        """At exactly 30%, hard gate doesn't fire (> not >=).
        But reviewable requires overclaim <= 0.15, so 0.30 still = draft."""
        m = EpistemicMetrics(
            direct_support_rate=0.60,
            epistemic_acceptability_rate=0.80,
            overclaim_rate=0.30,
            speculative_honesty=0.90,
            total_claims=10,
        )
        level = ExportQualityGate.classify_from_metrics(m)
        # 0.30 is NOT > 0.30 so hard gate doesn't fire
        # But 0.30 > 0.15 so reviewable is also blocked
        assert level == "draft"

    def test_overclaim_31_is_draft(self):
        m = EpistemicMetrics(
            direct_support_rate=0.90,
            epistemic_acceptability_rate=0.95,
            overclaim_rate=0.31,
            speculative_honesty=0.99,
            total_claims=100,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "draft"

    def test_reviewable_requirements(self):
        """epistemic >= 0.55 and overclaim <= 0.15 → reviewable."""
        m = EpistemicMetrics(
            direct_support_rate=0.30,
            epistemic_acceptability_rate=0.60,
            overclaim_rate=0.10,
            speculative_honesty=0.70,
            total_claims=10,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "reviewable"

    def test_reviewable_low_epistemic_is_draft(self):
        """epistemic < 0.55 → draft even with low overclaim."""
        m = EpistemicMetrics(
            direct_support_rate=0.20,
            epistemic_acceptability_rate=0.40,
            overclaim_rate=0.10,
            speculative_honesty=0.50,
            total_claims=10,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "draft"

    def test_submission_candidate_requirements(self):
        """epistemic >= 0.75 AND direct >= 0.50 AND overclaim <= 0.15."""
        m = EpistemicMetrics(
            direct_support_rate=0.55,
            epistemic_acceptability_rate=0.80,
            overclaim_rate=0.05,
            speculative_honesty=0.95,
            total_claims=20,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "submission_candidate"

    def test_submission_needs_high_direct_support(self):
        """direct_support < 0.50 prevents submission even with high epistemic."""
        m = EpistemicMetrics(
            direct_support_rate=0.45,
            epistemic_acceptability_rate=0.80,
            overclaim_rate=0.05,
            speculative_honesty=0.90,
            total_claims=20,
        )
        assert ExportQualityGate.classify_from_metrics(m) == "reviewable"

    def test_submission_blocked_by_overclaim_is_draft(self):
        """overclaim > 0.15 prevents reviewable (not just submission)."""
        m = EpistemicMetrics(
            direct_support_rate=0.60,
            epistemic_acceptability_rate=0.80,
            overclaim_rate=0.16,
            speculative_honesty=0.90,
            total_claims=20,
        )
        # 0.16 > 0.15 so reviewable blocked, 0.16 NOT > 0.30 so hard gate ok
        # But reviewable requires <= 0.15, so draft
        assert ExportQualityGate.classify_from_metrics(m) == "draft"


# ═══════════════════════════════════════════════════════════════════════════
# Quality Gate: Banner Formatting
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGateBanner:

    def test_banner_includes_all_metrics(self):
        m = EpistemicMetrics(
            direct_support_rate=0.40,
            epistemic_acceptability_rate=0.60,
            overclaim_rate=0.10,
            speculative_honesty=0.80,
            total_claims=10,
        )
        banner = ExportQualityGate.get_banner_from_metrics(m)
        assert "direct_support=40%" in banner
        assert "epistemic_acceptability=60%" in banner
        assert "overclaim=10%" in banner
        assert "speculative_honesty=80%" in banner

    def test_draft_banner_mentions_not_suitable(self):
        m = EpistemicMetrics(
            direct_support_rate=0.10,
            epistemic_acceptability_rate=0.30,
            overclaim_rate=0.40,
            speculative_honesty=0.50,
            total_claims=10,
        )
        banner = ExportQualityGate.get_banner_from_metrics(m)
        assert "DIAGNOSTIC DRAFT" in banner
        assert "Not suitable" in banner

    def test_submission_banner(self):
        m = EpistemicMetrics(
            direct_support_rate=0.60,
            epistemic_acceptability_rate=0.80,
            overclaim_rate=0.05,
            speculative_honesty=0.95,
            total_claims=20,
        )
        banner = ExportQualityGate.get_banner_from_metrics(m)
        assert "SUBMISSION CANDIDATE" in banner

    def test_legacy_banner_still_works(self):
        banner = ExportQualityGate.get_banner(0.50)
        assert "REVIEWABLE DRAFT" in banner


# ═══════════════════════════════════════════════════════════════════════════
# Quality Gate: Consumes Validator Output
# ═══════════════════════════════════════════════════════════════════════════


class TestQualityGateConsumesValidatorOutput:

    def test_gate_uses_precomputed_metrics(self):
        """Gate must use metrics from validator, not recompute."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "X improves Y. [SOURCE-1]",
             "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False},
            {"claim_id": "C2", "text": "We hypothesize Z.",
             "type": "hypothesis", "evidence_ids": [], "speculative": True},
            {"claim_id": "C3", "text": "This achieves SOTA.",
             "type": "method_claimed_benefit", "evidence_ids": [], "speculative": False},
        ]
        support = {"C1": "strong", "C2": "none", "C3": "none"}
        validated, metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, support,
        )

        # Gate must use THESE metrics, not recompute
        level = ExportQualityGate.classify_from_metrics(metrics)
        banner = ExportQualityGate.get_banner_from_metrics(metrics)

        # Verify the gate consumed the validator's numbers
        assert f"{metrics.direct_support_rate:.0%}" in banner

    def test_end_to_end_classify_flow(self):
        """Full flow: raw claims → validate → metrics → quality gate."""
        validator = ClaimTypeValidator()
        claims = [
            {"claim_id": "C1", "text": "Smith showed X [SOURCE-1].",
             "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False},
            {"claim_id": "C2", "text": "We propose method Y.",
             "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False},
            {"claim_id": "C3", "text": "We hypothesize improvement.",
             "type": "hypothesis", "evidence_ids": [], "speculative": True},
        ]
        support = {"C1": "strong", "C2": "none", "C3": "none"}

        validated, metrics = validator.validate_and_compute_metrics(
            "proposed_method", claims, support,
        )

        # C1=supported, C2=design_justified, C3=correctly_marked_hypothesis
        assert metrics.total_claims == 3
        assert metrics.overclaim_rate == 0.0
        assert metrics.direct_support_rate == pytest.approx(1/3, abs=0.01)
        assert metrics.epistemic_acceptability_rate == 1.0

        level = ExportQualityGate.classify_from_metrics(metrics)
        # direct_support=0.33 < 0.50 → can't be submission_candidate
        # epistemic=1.0 >= 0.55 and overclaim=0.0 <= 0.15 → reviewable
        assert level == "reviewable"


# ═══════════════════════════════════════════════════════════════════════════
# Stage Helpers: Structured Claim Collection
# ═══════════════════════════════════════════════════════════════════════════


class TestStageHelperCollection:

    def test_collect_structured_claims_from_metadata(self):
        from backend.pipeline.stages import CitationAuditStage

        metadata = {
            "full_paper": {
                "section_drafts": [
                    {
                        "section_id": "proposed_method",
                        "structured_claims": [
                            {"claim_id": "C001", "text": "We propose X.", "type": "method_proposed_mechanism"},
                        ],
                        "generation_mode": "structured",
                    },
                    {
                        "section_id": "related_work",
                        "structured_claims": [
                            {"claim_id": "C002", "text": "Smith showed Y.", "type": "background"},
                        ],
                        "generation_mode": "structured",
                    },
                    {
                        "section_id": "discussion",
                        "structured_claims": None,
                        "generation_mode": "prose_fallback",
                    },
                ],
            },
        }

        claims = CitationAuditStage._collect_structured_claims(metadata)
        assert "proposed_method" in claims
        assert "related_work" in claims
        assert "discussion" not in claims
        assert len(claims["proposed_method"]) == 1

    def test_collect_empty_when_no_full_paper(self):
        from backend.pipeline.stages import CitationAuditStage

        claims = CitationAuditStage._collect_structured_claims({})
        assert claims == {}

    def test_count_prose_fallbacks(self):
        from backend.pipeline.stages import CitationAuditStage

        metadata = {
            "full_paper": {
                "section_drafts": [
                    {"section_id": "abstract", "generation_mode": "structured"},
                    {"section_id": "method", "generation_mode": "prose_fallback"},
                    {"section_id": "eval", "generation_mode": "prose_fallback"},
                    {"section_id": "conclusion", "generation_mode": "structured"},
                ],
            },
        }

        count = CitationAuditStage._count_prose_fallbacks(metadata)
        assert count == 2

    def test_collect_assumptions(self):
        from backend.pipeline.stages import CitationAuditStage

        metadata = {
            "full_paper": {
                "section_drafts": [
                    {
                        "section_id": "proposed_method",
                        "assumptions": [
                            {"text": "We assume X approximates Y.", "basis": "analogical", "risk": "medium"},
                        ],
                    },
                    {
                        "section_id": "evaluation_plan",
                        "assumptions": [
                            {"text": "We assume benchmarks are representative.", "basis": "empirical", "risk": "low"},
                        ],
                    },
                ],
            },
        }

        assumptions = CitationAuditStage._collect_assumptions(metadata)
        assert len(assumptions) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Stage Helpers: Typed Validation
# ═══════════════════════════════════════════════════════════════════════════


class TestTypedValidation:

    def test_run_typed_validation_with_structured_claims(self):
        from backend.pipeline.stages import CitationAuditStage

        structured = {
            "proposed_method": [
                {"claim_id": "C1", "text": "Smith showed X [SOURCE-1].",
                 "type": "background", "evidence_ids": ["SOURCE-1"], "speculative": False,
                 "rationale": "test"},
                {"claim_id": "C2", "text": "We propose method Y.",
                 "type": "method_proposed_mechanism", "evidence_ids": [], "speculative": False,
                 "rationale": "test"},
            ],
        }
        corpus = {"SOURCE-1": "Smith demonstrated that X is effective in controlled settings."}

        metrics, validated_by_section = CitationAuditStage._run_typed_validation(
            structured, corpus,
        )

        assert metrics.total_claims == 2
        assert "proposed_method" in validated_by_section
        assert len(validated_by_section["proposed_method"]) == 2

    def test_run_typed_validation_empty_claims(self):
        from backend.pipeline.stages import CitationAuditStage

        metrics, validated = CitationAuditStage._run_typed_validation({}, {})
        assert metrics.total_claims == 0


# ═══════════════════════════════════════════════════════════════════════════
# Full Metadata Check
# ═══════════════════════════════════════════════════════════════════════════


class TestFullMetadata:

    def test_export_quality_has_all_required_fields(self):
        """Verify the metadata schema after typed repair."""
        from backend.pipeline.stages import CitationAuditStage

        # Minimal validated claims
        validated = {
            "proposed_method": [
                ValidatedClaim(
                    claim_id="C1", text="Test", declared_type="background",
                    section="proposed_method", evidence_ids=["SOURCE-1"],
                    speculative=False,
                    classification=ClaimClassification.SUPPORTED,
                ),
            ],
        }
        metrics = EpistemicMetrics(
            direct_support_rate=1.0,
            epistemic_acceptability_rate=1.0,
            overclaim_rate=0.0,
            speculative_honesty=1.0,
            total_claims=1,
            supported=1,
        )

        metadata = {}
        CitationAuditStage._run_typed_repair_and_quality_gate(
            idx=0,
            metrics=metrics,
            validated_by_section=validated,
            corpus={"SOURCE-1": "test evidence"},
            metadata=metadata,
            full_paper=None,
            assumption_register=[{"text": "We assume X.", "basis": "theoretical", "risk": "medium"}],
            prose_fallback_count=1,
            structured_claims_by_section={"proposed_method": [{"claim_id": "C1"}]},
        )

        # Check all required fields
        eq = metadata.get("export_quality", {})
        required_keys = [
            "level", "banner", "direct_support_rate",
            "epistemic_acceptability_rate", "overclaim_rate",
            "speculative_honesty", "prose_fallback_count",
            "contradiction_count", "assumption_count",
            "per_section_breakdown", "per_type_breakdown",
        ]
        for key in required_keys:
            assert key in eq, f"Missing export_quality field: {key}"

        # Check values
        assert eq["direct_support_rate"] == 1.0
        assert eq["overclaim_rate"] == 0.0
        assert eq["prose_fallback_count"] == 1
        assert eq["contradiction_count"] == 0
        assert eq["assumption_count"] == 1
        assert "proposed_method" in eq["per_section_breakdown"]
        assert "background" in eq["per_type_breakdown"]

        # Check epistemic metrics stored
        em = metadata.get("epistemic_metrics", {})
        assert em["direct_support_rate"] == 1.0
        assert em["overclaim_rate"] == 0.0

        # Check assumption register stored
        assert len(metadata.get("assumption_register", [])) == 1

        # Quality level
        assert eq["level"] == "submission_candidate"


# ═══════════════════════════════════════════════════════════════════════════
# Regression: Legacy Path Still Works
# ═══════════════════════════════════════════════════════════════════════════


class TestLegacyFallback:

    def test_legacy_classify_still_works(self):
        assert ExportQualityGate.classify(0.80) == "submission"
        assert ExportQualityGate.classify(0.60) == "reviewable"
        assert ExportQualityGate.classify(0.30) == "draft"

    def test_legacy_banner_still_works(self):
        banner = ExportQualityGate.get_banner(0.80)
        assert "SUBMISSION GRADE" in banner

    def test_classify_from_metrics_with_zero_claims(self):
        m = EpistemicMetrics(total_claims=0)
        assert ExportQualityGate.classify_from_metrics(m) == "draft"
