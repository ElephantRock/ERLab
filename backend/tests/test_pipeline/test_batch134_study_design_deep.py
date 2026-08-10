"""BATCH-134 Tests — LLM-Grounded StudyDesigner."""

import json
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.claims.study_designer import StudyDesign, StudyDesigner


def _mock_llm_response():
    return json.dumps({
        "hypothesis_main": "Applying Graph-of-Thought reasoning to multi-step mathematical word problems will reduce error rates by enabling explicit backtracking through reasoning paths",
        "hypothesis_null": "Graph-of-Thought reasoning will not reduce error rates compared to standard chain-of-thought prompting",
        "mechanistic_rationale": "Graph-of-Thought enables non-linear exploration of reasoning paths with explicit backtracking, which directly addresses the failure mode of chain-of-thought where a single wrong step cascades into incorrect answers on multi-step problems",
        "mvp_experiment": {
            "name": "MVP: GoT on GSM8K subset",
            "hypothesis_tested": "Does GoT reduce error rate on multi-step math problems?",
            "pseudocode": "# Load GSM8K 500-problem subset\n# Initialize GraphOfThought(num_branches=3)\n# For each problem:\n#   branches = got.generate_branches(problem, n=3)\n#   best = got.evaluate_and_select(branches)\n#   answer = got.aggregate(best)\n# Compare accuracy to CoT baseline",
            "expected_runtime": "45 minutes",
            "required_resources": "Single GPU (4GB)",
            "success_criteria": "GoT accuracy > CoT accuracy by >=3 percentage points (p < 0.05)",
            "failure_criteria": "GoT accuracy <= CoT accuracy or no significant difference"
        },
        "go_no_go": [{"metric": "Accuracy gap", "threshold": "+3pp with p<0.05", "action_if_pass": "Scale to full GSM8K + MATH datasets", "action_if_fail": "Tune branch count or try different aggregation"}],
        "risk_assessment": ["Branch generation may be too slow for real-time use", "Aggregation may lose critical reasoning steps", "Improvement may not generalize to MATH dataset"],
        "publication_strategy": "EMNLP 2027 findings → NeurIPS 2027 main",
        "timeline_weeks": 10
    })


class TestLLMStudyDesigner:
    def _idea(self):
        return {"title": "GoT for Math Reasoning", "problem_statement": "LLMs struggle with multi-step mathematical word problems", "proposed_method": "Graph-of-Thought reasoning"}

    def test_llm_hypothesis_references_method(self):
        """TEST-134-01: LLM hypothesis contains actual method name."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_mock_llm_response())
        designer = StudyDesigner(provider=provider)
        design = designer.design_from_idea(self._idea())
        assert "Graph-of-Thought" in design.hypothesis_main

    def test_llm_hypothesis_references_problem(self):
        """TEST-134-02: LLM hypothesis references problem domain."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_mock_llm_response())
        designer = StudyDesigner(provider=provider)
        design = designer.design_from_idea(self._idea())
        # Should reference math or multi-step or word problems
        lower = design.hypothesis_main.lower()
        assert any(w in lower for w in ["math", "multi-step", "word problem", "error rate"])

    def test_llm_pseudocode_uses_method_name(self):
        """TEST-134-03: Pseudocode uses actual method name."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_mock_llm_response())
        designer = StudyDesigner(provider=provider)
        design = designer.design_from_idea(self._idea())
        assert design.mvp_experiment is not None
        assert "GraphOfThought" in design.mvp_experiment.pseudocode or "GoT" in design.mvp_experiment.pseudocode

    def test_llm_has_mechanistic_rationale(self):
        """TEST-134-04: Mechanistic rationale is non-trivial."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=_mock_llm_response())
        designer = StudyDesigner(provider=provider)
        design = designer.design_from_idea(self._idea())
        assert len(design.mechanistic_rationale) > 50  # Non-trivial

    def test_fallback_to_template_on_failure(self):
        """TEST-134-05: Falls back to template on LLM failure."""
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("API down"))
        designer = StudyDesigner(provider=provider)
        design = designer.design_from_idea(self._idea())
        assert isinstance(design, StudyDesign)
        assert design.hypothesis_main != ""

    def test_no_provider_uses_template(self):
        """TEST-134-06: Without provider, uses template."""
        designer = StudyDesigner(provider=None)
        design = designer.design_from_idea(self._idea())
        assert "Graph-of-Thought" in design.hypothesis_main

    def test_backward_compat_b127(self):
        """TEST-134-07: B127 test pattern still works."""
        designer = StudyDesigner(provider=None)
        design = designer.design_from_idea({"title": "Test", "problem_statement": "P", "proposed_method": "M"})
        assert design.mvp_experiment is not None
        assert design.timeline_weeks > 0
