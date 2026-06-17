"""Tests for backend.api.quality_checks — quality checks, remediation hints, citation audit."""

import pytest

from backend.api.quality_checks import (
    compute_quality_checks,
    compute_remediation_hints,
    audit_citations,
)


class TestComputeQualityChecks:
    """Tests for deterministic quality check computation on persisted sections."""

    def test_returns_none_for_none_input(self):
        assert compute_quality_checks(None) is None

    def test_returns_none_for_empty_dict(self):
        assert compute_quality_checks({}) is None

    def test_returns_none_for_non_dict_input(self):
        assert compute_quality_checks("not a dict") is None

    def test_all_sections_passing(self):
        """A well-formed proposal should have all sections pass."""
        sections = {
            "abstract": "word " * 160,
            "introduction": "Our contributions include novelty. " * 100,
            "related_work": "Some prior work [1] by Smith (2024). " * 50,
            "proposed_method": (
                "We define the loss function $$L = \\sum x^2$$ "
                "and optimize using Adam optimizer. "
                "We use $w$ as weights on GPU A100. "
            ) * 35,
            "expected_contributions": "contribution " * 200,
            "evaluation_plan": (
                "We compare against a baseline with ablation "
                "and a naive cross-domain retrieval without alignment "
                "using accuracy and F1 metric. "
            ) * 20,
            "timeline": "We need GPU A100 7B model compute. " * 20,
            "risk_mitigation": "risk " * 200,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        assert len(result) == len({r["section"] for r in result})
        passing = [r for r in result if r["passed"]]
        assert len(passing) == len(result), "All sections should pass"

    def test_short_section_fails_word_count(self):
        """A section below the word-count threshold should fail."""
        sections = {
            "abstract": "short",  # 1 word, min 150
        }
        result = compute_quality_checks(sections)
        assert result is not None
        abstract_check = next(r for r in result if r["section"] == "abstract")
        assert not abstract_check["meets_word_count"]
        assert not abstract_check["passed"]
        assert any("word count" in f for f in abstract_check["failures"])

    def test_missing_section_marked_not_present(self):
        """A section key absent from the dict should be marked not present."""
        sections = {"abstract": "word " * 160}
        result = compute_quality_checks(sections)
        assert result is not None
        intro_check = next(r for r in result if r["section"] == "introduction")
        assert not intro_check["present"]
        assert not intro_check["passed"]
        assert intro_check["word_count"] == 0

    def test_present_but_empty_string_is_not_present(self):
        """An empty or whitespace-only string counts as not present."""
        sections = {"abstract": "   "}
        result = compute_quality_checks(sections)
        assert result is not None
        abstract_check = next(r for r in result if r["section"] == "abstract")
        assert not abstract_check["present"]

    def test_pattern_check_failure_detected(self):
        """proposed_method without loss function should fail pattern check."""
        sections = {
            "proposed_method": "word " * 700,  # enough words but no patterns
        }
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        assert method_check["present"]
        assert method_check["meets_word_count"]
        assert not method_check["passed"]
        # Should have pattern failures
        assert len(method_check["failures"]) > 0
        assert any("missing" in f for f in method_check["failures"])

    def test_evaluation_plan_pattern_checks(self):
        """evaluation_plan should check for baselines, ablation, metrics."""
        sections = {
            "evaluation_plan": "We test with a baseline and ablation and metric. " * 15,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        eval_check = next(r for r in result if r["section"] == "evaluation_plan")
        # "baseline", "ablation", "metric" all present, but "naive cross-domain" may fail
        checks_by_name = {c["name"]: c["passed"] for c in eval_check["checks"]}
        assert checks_by_name.get("named baselines") is True
        assert checks_by_name.get("ablation experiments") is True

    def test_ignores_non_prose_keys(self):
        """ensemble_review, references, title should not be checked."""
        sections = {
            "title": "Test",
            "references": [{"raw": "[1] Test"}],
            "ensemble_review": {"overall_score": 0.8},
        }
        result = compute_quality_checks(sections)
        assert result is not None
        section_keys = {r["section"] for r in result}
        assert "ensemble_review" not in section_keys
        assert "references" not in section_keys
        assert "title" not in section_keys

    def test_each_result_has_required_fields(self):
        sections = {"abstract": "word " * 160}
        result = compute_quality_checks(sections)
        assert result is not None
        for r in result:
            assert "section" in r
            assert "label" in r
            assert "present" in r
            assert "word_count" in r
            assert "min_words" in r
            assert "meets_word_count" in r
            assert "checks" in r
            assert "passed" in r
            assert "failures" in r
            assert isinstance(r["failures"], list)
            assert isinstance(r["checks"], list)

    def test_label_is_human_readable(self):
        sections = {"proposed_method": "x"}
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        assert method_check["label"] == "Proposed Method"

    def test_list_section_word_count(self):
        """Word count should handle list values (e.g., references as dicts)."""
        sections = {
            "expected_contributions": [
                {"text": "one two three four five"},
                {"text": "six seven eight nine ten"},
            ] * 20,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        ec_check = next(r for r in result if r["section"] == "expected_contributions")
        assert ec_check["word_count"] > 0
        assert ec_check["present"]

    # --- DOTALL fix: multi-line $$...$$ must match ---

    def test_multiline_display_equation_matches(self):
        """proposed_method with dollar-dollar on separate lines must pass.

        Regression test: the old pattern r'[$][$].*[$][$]' without re.DOTALL
        failed to match display equations where the delimiter is on its own line.
        """
        sections = {
            "proposed_method": (
                "We optimize the model. The loss function is:\n"
                "$$\n"
                "L = \\sum_{i=1}^{N} x_i^2\n"
                "$$\n"
                "We use $w$ as weights on GPU A100. "
            ) * 10,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        checks_by_name = {c["name"]: c["passed"] for c in method_check["checks"]}
        assert checks_by_name.get("formal loss function ($$...$$ display equation)") is True

    def test_inline_math_notation_matches_across_newlines(self):
        """proposed_method with $...$ notation spanning lines must match."""
        sections = {
            "proposed_method": (
                "The value $x$ is computed as $y = f(x)$\n"
                "where loss is minimized with GPU A100 compute. "
            ) * 20,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        method_check = next(r for r in result if r["section"] == "proposed_method")
        checks_by_name = {c["name"]: c["passed"] for c in method_check["checks"]}
        assert checks_by_name.get("mathematical notation ($...$)") is True

    # --- Citation pattern broadening: [SOURCE-N] ---

    def test_source_n_citation_markers_accepted(self):
        """related_work with [SOURCE-N] markers must pass the citation check.

        [SOURCE-N] is the pipeline's internal citation format before
        sanitization replaces unverifiable citations.
        """
        sections = {
            "related_work": (
                "Prior work [SOURCE-1] demonstrated this approach. "
                "Other methods [SOURCE-3] use different techniques. "
            ) * 30,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        rw_check = next(r for r in result if r["section"] == "related_work")
        checks_by_name = {c["name"]: c["passed"] for c in rw_check["checks"]}
        assert checks_by_name.get(
            "citation markers ([1], [SOURCE-N], or Author, Year)"
        ) is True

    def test_traditional_numbered_citations_still_accepted(self):
        """Standard [1] numbered citations must still pass."""
        sections = {
            "related_work": "Important work [1] showed results. See also [2]. " * 30,
        }
        result = compute_quality_checks(sections)
        assert result is not None
        rw_check = next(r for r in result if r["section"] == "related_work")
        checks_by_name = {c["name"]: c["passed"] for c in rw_check["checks"]}
        assert checks_by_name.get(
            "citation markers ([1], [SOURCE-N], or Author, Year)"
        ) is True


# ---------------------------------------------------------------------------
# compute_remediation_hints
# ---------------------------------------------------------------------------

_PASSING_SECTIONS = {
    "abstract": " ".join(["word"] * 200),
    "introduction": " ".join(["word"] * 500) + " Our contributions are novel.",
    "related_work": " ".join(["word"] * 400) + " [1] [2] (Smith, 2020)",
    "proposed_method": " ".join(["word"] * 700) + " $$L = loss$$ $x$ GPU A100",
    "expected_contributions": " ".join(["word"] * 200),
    "evaluation_plan": " ".join(["word"] * 400) + " baseline ablation accuracy cross-domain without alignment",
    "timeline": " ".join(["word"] * 150) + " A100 GPU 7B",
    "risk_mitigation": " ".join(["word"] * 200),
}


class TestRemediationHints:
    """Tests for deterministic remediation hint generation."""

    def test_returns_none_for_no_sections(self):
        assert compute_remediation_hints(None) is None

    def test_returns_none_when_all_checks_pass(self):
        assert compute_remediation_hints(dict(_PASSING_SECTIONS)) is None

    def test_word_count_hint(self):
        sections = dict(_PASSING_SECTIONS)
        sections["abstract"] = "short text"
        hints = compute_remediation_hints(sections)
        assert hints is not None
        wc_hints = [h for h in hints if h["issue_type"] == "word_count"]
        assert len(wc_hints) == 1
        assert wc_hints[0]["section"] == "abstract"
        assert "Expand" in wc_hints[0]["suggestion"]
        assert "150" in wc_hints[0]["suggestion"]

    def test_missing_pattern_hint_citations(self):
        sections = dict(_PASSING_SECTIONS)
        sections["related_work"] = " ".join(["word"] * 400)
        hints = compute_remediation_hints(sections)
        assert hints is not None
        citation_hints = [
            h for h in hints
            if h["section"] == "related_work" and h["issue_type"] == "missing_pattern"
        ]
        assert len(citation_hints) == 1
        assert "reference" in citation_hints[0]["suggestion"].lower()

    def test_missing_section_hint(self):
        sections = dict(_PASSING_SECTIONS)
        del sections["risk_mitigation"]
        hints = compute_remediation_hints(sections)
        assert hints is not None
        missing_hints = [h for h in hints if h["issue_type"] == "missing_section"]
        assert len(missing_hints) == 1
        assert missing_hints[0]["section"] == "risk_mitigation"
        assert missing_hints[0]["severity"] == "error"

    def test_all_hints_have_required_fields(self):
        sections = {k: "short" for k in _PASSING_SECTIONS}
        hints = compute_remediation_hints(sections)
        assert hints is not None
        for h in hints:
            assert "section" in h
            assert "label" in h
            assert "issue_type" in h
            assert "severity" in h
            assert "message" in h
            assert "suggestion" in h
            assert "refinement_available" in h
            assert h["refinement_available"] is True

    def test_accepts_precomputed_quality_checks(self):
        qc = compute_quality_checks({"abstract": "short text"})
        hints = compute_remediation_hints(None, qc)
        assert hints is not None
        assert all(h["section"] == "abstract" for h in hints if h["issue_type"] == "word_count")

    def test_multiple_failure_types_for_one_section(self):
        sections = dict(_PASSING_SECTIONS)
        sections["related_work"] = "short no citations"
        hints = compute_remediation_hints(sections)
        rw_hints = [h for h in hints if h["section"] == "related_work"]
        assert len(rw_hints) == 2
        issue_types = {h["issue_type"] for h in rw_hints}
        assert "word_count" in issue_types
        assert "missing_pattern" in issue_types


# ---------------------------------------------------------------------------
# audit_citations
# ---------------------------------------------------------------------------

class TestAuditCitations:
    """Tests for citation health auditing."""

    def test_returns_none_for_no_sections(self):
        assert audit_citations(None) is None

    def test_detects_citation_needed_markers(self):
        sections = dict(_PASSING_SECTIONS)
        sections["related_work"] = "Some text [Citation needed: Liu et al., 2023] here. " * 30
        result = audit_citations(sections)
        rw = [e for e in result if e["section"] == "related_work"][0]
        assert rw["citation_needed_count"] == 30
        assert rw["has_citation_issues"] is True

    def test_counts_valid_citations(self):
        sections = dict(_PASSING_SECTIONS)
        sections["related_work"] = "Text with [1], [2], [SOURCE-3], and (Smith, 2020) refs. " * 20
        result = audit_citations(sections)
        rw = [e for e in result if e["section"] == "related_work"][0]
        assert rw["valid_citation_count"] == 80  # 4 per repeat × 20 repeats
        assert rw["citation_needed_count"] == 0
        assert rw["has_citation_issues"] is False

    def test_summary_entry(self):
        sections = dict(_PASSING_SECTIONS)
        sections["related_work"] = "Text [Citation needed: X, 2020] and [1]. " * 20
        sections["introduction"] = "More [Citation needed: Y, 2021] text [2]. " * 20
        result = audit_citations(sections)
        summary = [e for e in result if e["section"] == "_summary"][0]
        assert summary["citation_needed_count"] == 40  # 2 per repeat × 20
        assert summary["valid_citation_count"] == 40  # 2 per repeat × 20
        assert summary["has_citation_issues"] is True

    def test_includes_reference_resolution_counts(self):
        sections = dict(_PASSING_SECTIONS)
        refs = [
            {"raw": "ref1", "resolved": True},
            {"raw": "ref2", "resolved": True},
            {"raw": "ref3", "resolved": False},
        ]
        result = audit_citations(sections, proposal_references=refs)
        rw = [e for e in result if e["section"] == "related_work"][0]
        assert rw["resolved_reference_count"] == 2
        assert rw["unresolved_reference_count"] == 1

    def test_no_reference_resolution_without_refs_param(self):
        result = audit_citations(dict(_PASSING_SECTIONS))
        rw = [e for e in result if e["section"] == "related_work"][0]
        assert "resolved_reference_count" not in rw
        assert "unresolved_reference_count" not in rw

    def test_clean_sections_report_zero_issues(self):
        result = audit_citations(dict(_PASSING_SECTIONS))
        summary = [e for e in result if e["section"] == "_summary"][0]
        assert summary["citation_needed_count"] == 0
        assert summary["valid_citation_count"] == 3  # [1], [2], (Smith, 2020)
        assert summary["has_citation_issues"] is False
