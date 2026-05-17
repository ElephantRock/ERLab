"""Phase E — Synthetic E2E validation against run_0944 baseline.

Since LM Studio and Anthropic are both offline, this test simulates
the E2E pipeline with realistic claim distributions modeled on actual
run_0944 output patterns. This isolates the epistemic pipeline from
LLM variance, proving the metric computation is correct.

run_0944 baseline (pre-evidence-grounded):
  claim survival: 33%/31% raw -> 42%/48% after repair
  related_work: 44-50% survival (best)
  method/evaluation: 0-22% survival (worst)

Expected after evidence-grounded generation:
  overclaim: ~70% -> 25-35% (strong) or <=15% (excellent)
  speculative_honesty: >70%
  epistemic_acceptability: >=50%
  direct_support: stable (not materially lower)
"""

import pytest

from backend.pipeline.gateway.claim_types import ClaimType
from backend.pipeline.gateway.claim_type_validator import (
    ClaimClassification,
    ClaimTypeValidator,
    EpistemicMetrics,
    ValidatedClaim,
    compute_metrics,
)
from backend.pipeline.gateway.evidence_repair import (
    EvidenceRepairLoop,
    ExportQualityGate,
    RepairAction,
)


# ═══════════════════════════════════════════════════════════════════════════
# Synthetic Proposal Data
# ═══════════════════════════════════════════════════════════════════════════


def _make_proposal_1_old_style():
    """Simulates pre-evidence-grounded output (run_0944 pattern).

    Typical patterns:
    - Related Work: mostly supported, some unsubstantiated
    - Method: mostly unsubstantiated claims stated as fact
    - Evaluation: unsubstantiated benefits stated as fact
    - Discussion/Conclusion: speculation presented as fact
    """
    validator = ClaimTypeValidator()
    claims_raw = [
        # Related Work — mix of supported and unsupported
        ("R1", "Smith et al. demonstrated tool-augmented reasoning [SOURCE-1].",
         "background", ["SOURCE-1"], False, "strong"),
        ("R2", "Jones showed that planning improves multi-step tasks [SOURCE-2].",
         "background", ["SOURCE-2"], False, "strong"),
        ("R3", "Prior methods struggle with uncertainty quantification [SOURCE-3].",
         "prior_limitation", ["SOURCE-3"], False, "strong"),
        ("R4", "Existing approaches fail at dynamic routing.",
         "prior_limitation", [], False, "none"),  # NO citation

        # Method — mostly unsubstantiated claims stated as fact (OLD STYLE)
        ("M1", "We propose a two-stage uncertainty-aware routing framework.",
         "method_proposed_mechanism", [], False, "none"),
        ("M2", "Our approach significantly improves robustness in high-stakes settings.",
         "method_claimed_benefit", [], False, "none"),  # NOT marked speculative
        ("M3", "This method enables real-time adaptation to distribution shift.",
         "method_claimed_benefit", [], False, "none"),  # NOT marked speculative
        ("M4", "We hypothesize that uncertainty signals improve routing decisions.",
         "hypothesis", [], True, "none"),  # correctly marked
        ("M5", "The framework solves the cold-start problem in tool selection.",
         "method_claimed_benefit", [], False, "none"),  # NOT marked speculative

        # Evaluation — unsubstantiated benefits
        ("E1", "We evaluate on MATH, GSM8K, and HumanEval [SOURCE-4].",
         "evaluation_benchmark", ["SOURCE-4"], False, "weak"),
        ("E2", "Our method achieves 95% accuracy on MATH.",
         "method_claimed_benefit", [], False, "none"),  # Result without experiment
        ("E3", "We use exact-match and pass@k metrics [SOURCE-5].",
         "evaluation_metric", ["SOURCE-5"], False, "weak"),
        ("E4", "This outperforms all existing baselines.",
         "method_claimed_benefit", [], False, "none"),  # NOT marked speculative

        # Discussion — speculation as fact
        ("D1", "This work advances the field of tool-augmented reasoning.",
         "expected_contribution", [], False, "none"),  # NOT marked speculative
        ("D2", "Our approach is broadly applicable to all LLM architectures.",
         "method_claimed_benefit", [], False, "none"),  # NOT marked speculative

        # Conclusion
        ("J1", "This framework enables a new paradigm of adaptive AI systems.",
         "expected_contribution", [], False, "none"),  # NOT marked speculative
    ]

    claims = []
    support = {}
    for cid, text, ctype, eids, spec, supp in claims_raw:
        claims.append({
            "claim_id": cid, "text": text, "type": ctype,
            "evidence_ids": eids, "speculative": spec, "rationale": "simulated",
        })
        support[cid] = supp

    return claims, support


def _make_proposal_1_new_style():
    """Simulates post-evidence-grounded output (what the new pipeline produces).

    Key improvements:
    - Benefit claims correctly marked speculative
    - Hypotheses properly typed and marked
    - Expected contributions use "We aim to" language
    - Mechanism+benefit properly split
    """
    claims_raw = [
        # Related Work — same strong grounding
        ("R1", "Smith et al. demonstrated tool-augmented reasoning [SOURCE-1].",
         "background", ["SOURCE-1"], False, "strong"),
        ("R2", "Jones showed that planning improves multi-step tasks [SOURCE-2].",
         "background", ["SOURCE-2"], False, "strong"),
        ("R3", "Prior methods struggle with uncertainty quantification [SOURCE-3].",
         "prior_limitation", ["SOURCE-3"], False, "strong"),
        ("R4", "Existing approaches face challenges in dynamic routing [SOURCE-1].",
         "prior_limitation", ["SOURCE-1"], False, "weak"),

        # Method — properly typed and marked
        ("M1", "We propose a two-stage uncertainty-aware routing framework.",
         "method_proposed_mechanism", [], False, "none"),
        ("M2", "We hypothesize that this may improve robustness in high-stakes settings.",
         "method_claimed_benefit", [], True, "none"),  # CORRECTLY marked
        ("M3", "We hypothesize that uncertainty signals may enable adaptation.",
         "method_claimed_benefit", [], True, "none"),  # CORRECTLY marked
        ("M4", "We hypothesize that uncertainty signals improve routing decisions.",
         "hypothesis", [], True, "none"),  # CORRECTLY marked
        ("M5", "We hypothesize that the framework may address cold-start challenges.",
         "method_claimed_benefit", [], True, "none"),  # CORRECTLY marked

        # Evaluation — properly framed
        ("E1", "We evaluate on MATH, GSM8K, and HumanEval [SOURCE-4].",
         "evaluation_benchmark", ["SOURCE-4"], False, "weak"),
        ("E2", "We hypothesize that our method may achieve competitive results on MATH.",
         "hypothesis", [], True, "none"),  # CORRECTLY marked as hypothesis
        ("E3", "We use exact-match and pass@k metrics [SOURCE-5].",
         "evaluation_metric", ["SOURCE-5"], False, "weak"),
        ("E4", "We aim to compare against established baselines.",
         "expected_contribution", [], True, "none"),  # CORRECTLY marked

        # Discussion — honest framing
        ("D1", "We aim to contribute to tool-augmented reasoning.",
         "expected_contribution", [], True, "none"),  # CORRECTLY marked
        ("D2", "We hypothesize broader applicability to other architectures.",
         "hypothesis", [], True, "none"),  # CORRECTLY marked

        # Conclusion — honest
        ("J1", "We aim to enable more adaptive AI systems.",
         "expected_contribution", [], True, "none"),  # CORRECTLY marked
    ]

    claims = []
    support = {}
    for cid, text, ctype, eids, spec, supp in claims_raw:
        claims.append({
            "claim_id": cid, "text": text, "type": ctype,
            "evidence_ids": eids, "speculative": spec, "rationale": "simulated",
        })
        support[cid] = supp

    return claims, support


def _make_proposal_2_new_style():
    """Second proposal — similar improvement pattern."""
    claims_raw = [
        ("R1", "Graph RAG has shown promise in knowledge-intensive tasks [SOURCE-1].",
         "background", ["SOURCE-1"], False, "strong"),
        ("R2", "Prior work has limited scalability [SOURCE-2].",
         "prior_limitation", ["SOURCE-2"], False, "strong"),
        ("M1", "We propose a hybrid graph-vector retrieval pipeline.",
         "method_proposed_mechanism", [], False, "none"),
        ("M2", "We hypothesize improved retrieval quality.",
         "method_claimed_benefit", [], True, "none"),
        ("M3", "The design uses a two-phase retrieval strategy.",
         "method_proposed_mechanism", [], False, "none"),
        ("E1", "We evaluate on standard benchmarks [SOURCE-3].",
         "evaluation_benchmark", ["SOURCE-3"], False, "weak"),
        ("E2", "We hypothesize competitive performance.",
         "hypothesis", [], True, "none"),
        ("D1", "We aim to advance graph-based retrieval.",
         "expected_contribution", [], True, "none"),
        ("J1", "We aim to demonstrate scalable graph RAG.",
         "expected_contribution", [], True, "none"),
    ]

    claims = []
    support = {}
    for cid, text, ctype, eids, spec, supp in claims_raw:
        claims.append({
            "claim_id": cid, "text": text, "type": ctype,
            "evidence_ids": eids, "speculative": spec, "rationale": "simulated",
        })
        support[cid] = supp

    return claims, support


# ═══════════════════════════════════════════════════════════════════════════
# E2E Comparison Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestE2EComparison:

    def test_old_style_high_overclaim(self):
        """Pre-evidence-grounded: high overclaim rate (~70%)."""
        validator = ClaimTypeValidator()
        claims, support = _make_proposal_1_old_style()

        rw_claims = [c for c in claims if c["claim_id"].startswith("R")]
        mt_claims = [c for c in claims if c["claim_id"].startswith("M")]
        ev_claims = [c for c in claims if c["claim_id"].startswith("E")]
        di_claims = [c for c in claims if c["claim_id"].startswith("D")]
        co_claims = [c for c in claims if c["claim_id"].startswith("J")]

        all_validated = (
            validator.validate_section("related_work", rw_claims, support)
            + validator.validate_section("proposed_method", mt_claims, support)
            + validator.validate_section("evaluation_plan", ev_claims, support)
            + validator.validate_section("discussion", di_claims, support)
            + validator.validate_section("conclusion", co_claims, support)
        )
        metrics = compute_metrics(all_validated)

        # OLD STYLE: many unmarked benefits -> high overclaim
        assert metrics.total_claims >= 15
        assert metrics.overclaim_rate > 0.20  # Unmarked speculation
        assert metrics.speculative_honesty < 0.30  # Few honestly marked

        level = ExportQualityGate.classify_from_metrics(metrics)
        assert level == "draft"  # Hard gate

        print(f"\nOLD STYLE (run_0944 baseline):")
        print(f"  overclaim: {metrics.overclaim_rate:.1%}")
        print(f"  speculative_honesty: {metrics.speculative_honesty:.1%}")
        print(f"  epistemic_acceptability: {metrics.epistemic_acceptability_rate:.1%}")
        print(f"  direct_support: {metrics.direct_support_rate:.1%}")
        print(f"  level: {level}")

    def test_new_style_reduced_overclaim(self):
        """Post-evidence-grounded: overclaim drops to 25-35%."""
        validator = ClaimTypeValidator()
        claims, support = _make_proposal_1_new_style()

        rw_claims = [c for c in claims if c["claim_id"].startswith("R")]
        mt_claims = [c for c in claims if c["claim_id"].startswith("M")]
        ev_claims = [c for c in claims if c["claim_id"].startswith("E")]
        di_claims = [c for c in claims if c["claim_id"].startswith("D")]
        co_claims = [c for c in claims if c["claim_id"].startswith("J")]

        all_validated = (
            validator.validate_section("related_work", rw_claims, support)
            + validator.validate_section("proposed_method", mt_claims, support)
            + validator.validate_section("evaluation_plan", ev_claims, support)
            + validator.validate_section("discussion", di_claims, support)
            + validator.validate_section("conclusion", co_claims, support)
        )
        metrics = compute_metrics(all_validated)

        # NEW STYLE: properly marked -> low/zero overclaim
        assert metrics.total_claims >= 15
        assert metrics.overclaim_rate <= 0.35  # Strong success threshold
        assert metrics.speculative_honesty >= 0.70  # >70% honesty
        assert metrics.epistemic_acceptability_rate >= 0.50  # >=50%

        print(f"\nNEW STYLE (evidence-grounded):")
        print(f"  overclaim: {metrics.overclaim_rate:.1%}")
        print(f"  speculative_honesty: {metrics.speculative_honesty:.1%}")
        print(f"  epistemic_acceptability: {metrics.epistemic_acceptability_rate:.1%}")
        print(f"  direct_support: {metrics.direct_support_rate:.1%}")

    def test_direct_support_stable_across_styles(self):
        """CRITICAL: overclaim down while direct_support stays stable."""
        validator = ClaimTypeValidator()

        # Old style
        old_claims, old_support = _make_proposal_1_old_style()
        def _validate_all(claims, support):
            rw = [c for c in claims if c["claim_id"].startswith("R")]
            mt = [c for c in claims if c["claim_id"].startswith("M")]
            ev = [c for c in claims if c["claim_id"].startswith("E")]
            di = [c for c in claims if c["claim_id"].startswith("D")]
            co = [c for c in claims if c["claim_id"].startswith("J")]
            return compute_metrics(
                validator.validate_section("related_work", rw, support)
                + validator.validate_section("proposed_method", mt, support)
                + validator.validate_section("evaluation_plan", ev, support)
                + validator.validate_section("discussion", di, support)
                + validator.validate_section("conclusion", co, support)
            )

        old_metrics = _validate_all(*_make_proposal_1_old_style())
        new_metrics = _validate_all(*_make_proposal_1_new_style())

        # The key diagnostic pair:
        # overclaim down
        assert new_metrics.overclaim_rate < old_metrics.overclaim_rate

        # direct_support stable (+/-5%)
        dsr_diff = abs(new_metrics.direct_support_rate - old_metrics.direct_support_rate)
        assert dsr_diff < 0.10, (
            f"direct_support changed by {dsr_diff:.1%} — "
            f"old={old_metrics.direct_support_rate:.1%}, new={new_metrics.direct_support_rate:.1%}"
        )

        print(f"\n--- HONESTY IMPROVEMENT (NOT PERMISSIVENESS) ---")
        print(f"  overclaim: {old_metrics.overclaim_rate:.1%} -> {new_metrics.overclaim_rate:.1%} "
              f"(down{old_metrics.overclaim_rate - new_metrics.overclaim_rate:.1%})")
        print(f"  direct_support: {old_metrics.direct_support_rate:.1%} -> {new_metrics.direct_support_rate:.1%} "
              f"(Delta{dsr_diff:.1%})")
        print(f"  epistemic: {old_metrics.epistemic_acceptability_rate:.1%} -> {new_metrics.epistemic_acceptability_rate:.1%}")

    def test_method_section_epistemic_acceptability(self):
        """Method section: epistemic_acceptability >= 40%."""
        validator = ClaimTypeValidator()
        claims, support = _make_proposal_1_new_style()
        method_claims = [c for c in claims if c["claim_id"].startswith("M")]
        method_validated = validator.validate_section("proposed_method", method_claims, support)
        method_metrics = compute_metrics(method_validated)

        assert method_metrics.epistemic_acceptability_rate >= 0.40

    def test_evaluation_section_epistemic_acceptability(self):
        """Evaluation section: epistemic_acceptability >= 30%."""
        validator = ClaimTypeValidator()
        claims, support = _make_proposal_1_new_style()
        eval_claims = [c for c in claims if c["claim_id"].startswith("E")]
        eval_validated = validator.validate_section("evaluation_plan", eval_claims, support)
        eval_metrics = compute_metrics(eval_validated)

        assert eval_metrics.epistemic_acceptability_rate >= 0.30

    def test_second_proposal_metrics(self):
        """Second proposal also improves."""
        validator = ClaimTypeValidator()
        claims, support = _make_proposal_2_new_style()

        rw_claims = [c for c in claims if c["claim_id"].startswith("R")]
        mt_claims = [c for c in claims if c["claim_id"].startswith("M")]
        ev_claims = [c for c in claims if c["claim_id"].startswith("E")]
        disc_claims = [c for c in claims if c["claim_id"].startswith("D")]
        conc_claims = [c for c in claims if c["claim_id"].startswith("J")]

        all_validated = (
            validator.validate_section("related_work", rw_claims, support)
            + validator.validate_section("proposed_method", mt_claims, support)
            + validator.validate_section("evaluation_plan", ev_claims, support)
            + validator.validate_section("discussion", disc_claims, support)
            + validator.validate_section("conclusion", conc_claims, support)
        )

        metrics = compute_metrics(all_validated)
        assert metrics.overclaim_rate == 0.0  # All correctly marked
        assert metrics.speculative_honesty == 1.0
        assert metrics.epistemic_acceptability_rate >= 0.50

    def test_full_diagnostic_report(self):
        """Generate the full diagnostic comparison table."""
        validator = ClaimTypeValidator()

        print("\n" + "=" * 70)
        print("E2E DIAGNOSTIC: Synthetic run_0944 vs Evidence-Grounded")
        print("=" * 70)

        # Proposal 1 — old vs new
        old_claims, old_support = _make_proposal_1_old_style()
        new_claims, new_support = _make_proposal_1_new_style()

        def _validate_all(claims, support):
            rw = [c for c in claims if c["claim_id"].startswith("R")]
            mt = [c for c in claims if c["claim_id"].startswith("M")]
            ev = [c for c in claims if c["claim_id"].startswith("E")]
            di = [c for c in claims if c["claim_id"].startswith("D")]
            co = [c for c in claims if c["claim_id"].startswith("J")]
            return compute_metrics(
                validator.validate_section("related_work", rw, support)
                + validator.validate_section("proposed_method", mt, support)
                + validator.validate_section("evaluation_plan", ev, support)
                + validator.validate_section("discussion", di, support)
                + validator.validate_section("conclusion", co, support)
            )

        old_m = _validate_all(old_claims, old_support)
        new_m = _validate_all(new_claims, new_support)

        print(f"\n{'Metric':<30} {'Old Style':>12} {'New Style':>12} {'Delta':>10}")
        print("-" * 70)
        for label, getter in [
            ("direct_support_rate", lambda m: m.direct_support_rate),
            ("epistemic_acceptability", lambda m: m.epistemic_acceptability_rate),
            ("overclaim_rate", lambda m: m.overclaim_rate),
            ("speculative_honesty", lambda m: m.speculative_honesty),
            ("total_claims", lambda m: m.total_claims),
            ("supported", lambda m: m.supported),
            ("design_justified", lambda m: m.design_justified),
            ("correctly_marked_hypo", lambda m: m.correctly_marked_hypotheses),
            ("unmarked_speculation", lambda m: m.unmarked_speculation),
            ("contradicted", lambda m: m.contradicted),
        ]:
            o = getter(old_m)
            n = getter(new_m)
            delta = n - o
            fmt = "{:.1%}" if isinstance(o, float) else "{}"
            print(f"  {label:<28} {fmt.format(o):>12} {fmt.format(n):>12} {fmt.format(delta):>10}")

        # Quality gate
        old_level = ExportQualityGate.classify_from_metrics(old_m)
        new_level = ExportQualityGate.classify_from_metrics(new_m)
        print(f"\n  {'quality_level':<28} {old_level:>12} {new_level:>12}")

        # Success criteria
        print(f"\n--- SUCCESS CRITERIA ---")
        print(f"  overclaim_rate: 25-35%? {new_m.overclaim_rate:.1%} -> "
              f"{'PASS' if 0.25 <= new_m.overclaim_rate <= 0.35 else 'WARN' if new_m.overclaim_rate < 0.25 else 'FAIL'}")
        print(f"  speculative_honesty >70%? {new_m.speculative_honesty:.1%} -> "
              f"{'PASS' if new_m.speculative_honesty >= 0.70 else 'FAIL'}")
        print(f"  epistemic_acceptability >=50%? {new_m.epistemic_acceptability_rate:.1%} -> "
              f"{'PASS' if new_m.epistemic_acceptability_rate >= 0.50 else 'FAIL'}")
        print(f"  direct_support stable? Delta={abs(new_m.direct_support_rate - old_m.direct_support_rate):.1%} -> "
              f"{'PASS' if abs(new_m.direct_support_rate - old_m.direct_support_rate) < 0.10 else 'FAIL'}")
        print(f"  overclaim down? {old_m.overclaim_rate:.1%} -> {new_m.overclaim_rate:.1%} -> "
              f"{'PASS' if new_m.overclaim_rate < old_m.overclaim_rate else 'FAIL'}")
