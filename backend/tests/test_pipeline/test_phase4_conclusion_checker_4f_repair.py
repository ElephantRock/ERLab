"""Phase 4 / 4F repair tests — conclusion checker must scan abstract + conclusion.

The independent audit found the 4F gate caught only 1/5 overstatement cases.
Root cause: (1) has_empirical_results false-positive from evaluation-planning
sections (## Evaluation as a PLAN, not results); (2) abstract not always
extracted; (3) empirical assertions in the abstract not checked against actual
reported methods.

These tests use REDUCED FIXTURES from the 6 live papers — linguistic/structural
conditions, not hard-coded IDs or titles.
"""

from backend.pipeline.evaluation.conclusion_checker import classify_conclusion_support


class TestAbstractOverclaimDetection:
    """The checker must catch 'we demonstrate' in the ABSTRACT, not just conclusion."""

    def test_abstract_demonstrate_with_no_results_is_overstated(self):
        """Abstract says 'we demonstrate' but paper has only Expected Results."""
        abstract = (
            "We propose a novel framework. We demonstrate that our approach "
            "significantly improves detection of anomalies compared to baselines."
        )
        conclusion = (
            "We have outlined the theoretical formulation and expected outcomes. "
            "We hypothesize the approach will outperform traditional methods."
        )
        # Paper has an "## Evaluation" heading but it describes the PLAN, not results.
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,  # explicitly no results
        )
        assert result.classification == "overstated"

    def test_abstract_experimental_results_indicate_is_overstated(self):
        """Abstract says 'experimental results indicate' with no experiments."""
        abstract = (
            "Experimental results on benchmark datasets indicate that our method "
            "achieves comparable accuracy while significantly reducing overhead."
        )
        conclusion = "We expect our approach to reduce convergence time."
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_abstract_validation_demonstrates_is_overstated(self):
        """Abstract says 'experimental validation demonstrates' — most flagrant."""
        abstract = (
            "Experimental validation on retrospective cohorts demonstrates that "
            "the framework achieves superior diagnostic accuracy."
        )
        conclusion = "The expected results demonstrate it is possible to mitigate bias."
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_properly_hedged_abstract_is_supported(self):
        """Abstract that hedges with 'expected results indicate' is NOT overstated."""
        abstract = (
            "We propose a novel consensus protocol. Expected results indicate "
            "a substantial reduction in convergence time compared to baselines."
        )
        conclusion = (
            "We expect to demonstrate that this approach potentially reduces "
            "convergence time without sacrificing accuracy."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "supported_by_paper"


class TestEmpiricalDetectionPrecision:
    """has_empirical_results must not false-positive on evaluation-PLAN sections."""

    def test_evaluation_heading_does_not_mean_results(self):
        """A paper with '## Evaluation' as a planning section has no results.

        The heuristic previously checked for heading strings like '## evaluation'
        in the paper body, which false-positive'd on design papers that describe
        their evaluation PLAN."""
        abstract = "We demonstrate that our method outperforms baselines."
        conclusion = "We have designed an evaluation framework."
        # The paper has NO actual results — the evaluation section is a plan.
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_expected_results_section_means_no_empirical(self):
        """An 'Expected Results' section explicitly means no experiments were run."""
        abstract = "We demonstrate significant improvements."
        conclusion = (
            "Our expected results suggest the approach will work. "
            "We hypothesize faster convergence."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"


class TestAttributedDemonstrationNotFlagged:
    """'Do not flag discussion of what another cited paper demonstrated.'"""

    def test_cited_source_demonstration_not_flagged(self):
        """'[SOURCE-3] demonstrates X' is the source's claim, not the paper's."""
        abstract = (
            "We propose a new method building on prior work. "
            "Our approach is conceptually sound."
        )
        conclusion = (
            "As [SOURCE-3] demonstrates, deep learning excels at medical imaging. "
            "Our method extends this conceptually."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "supported_by_paper"

    def test_self_claim_demonstrate_still_flagged(self):
        """'We demonstrate' (self-claim) is still flagged even with cited demonstrations."""
        abstract = "We demonstrate that our novel method achieves 95% accuracy."
        conclusion = (
            "[SOURCE-5] also demonstrates the value of this approach. "
            "Our results confirm the hypothesis."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"


class TestFullPaperFixtures:
    """Reduced fixtures representing the 6 live papers' linguistic conditions."""

    def test_fixture_overstated_abstract_demonstrate(self):
        """Represents idea_47/49/51/52 pattern: abstract says 'demonstrate'."""
        abstract = (
            "We propose a novel architecture. We demonstrate that incorporating "
            "domain knowledge significantly improves detection compared to "
            "standard methods."
        )
        conclusion = (
            "We have outlined the theoretical formulation and expected outcomes. "
            "Future work may focus on extending the framework."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_fixture_overstated_experimental_validation(self):
        """Represents idea_48 pattern: 'experimental validation demonstrates'."""
        abstract = (
            "Experimental validation on retrospective cohorts demonstrates "
            "superior diagnostic accuracy and reduced performance gaps."
        )
        conclusion = "The expected results demonstrate mitigation of bias."
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "overstated"

    def test_fixture_supported_properly_hedged(self):
        """Represents idea_50 pattern: properly hedged, no false empirical claims."""
        abstract = (
            "We propose a protocol. Expected results indicate a substantial "
            "reduction in convergence time."
        )
        conclusion = (
            "We expect to demonstrate that this approach potentially reduces "
            "convergence time without sacrificing accuracy."
        )
        result = classify_conclusion_support(
            abstract=abstract, conclusion=conclusion,
            has_empirical_results=False,
        )
        assert result.classification == "supported_by_paper"
