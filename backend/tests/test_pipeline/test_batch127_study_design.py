"""BATCH-127 Tests — Study Design with MVP."""

from backend.pipeline.claims.study_designer import StudyDesign, StudyDesigner


class TestStudyDesigner:
    def _sample_idea(self):
        return {
            "title": "Graph-of-Thought for Multi-Step Reasoning",
            "problem_statement": "LLMs struggle with complex multi-step reasoning tasks",
            "proposed_method": "Graph-of-Thought reasoning",
        }

    def test_design_from_idea(self):
        """TEST-127-01: StudyDesigner creates full StudyDesign."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert isinstance(design, StudyDesign)
        assert design.idea_title != ""
        assert design.hypothesis_main != ""
        assert design.mvp_experiment is not None

    def test_mvp_experiment_has_pseudocode(self):
        """TEST-127-02: MVP experiment includes pseudocode."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert design.mvp_experiment.pseudocode != ""
        assert "#" in design.mvp_experiment.pseudocode  # Has code comments

    def test_go_no_go_criteria(self):
        """TEST-127-03: Go/no-go criteria are defined."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert len(design.go_no_go) > 0
        assert design.go_no_go[0].metric != ""
        assert design.go_no_go[0].threshold != ""

    def test_risk_assessment(self):
        """TEST-127-04: Risk assessment includes known risks."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert len(design.risk_assessment) > 0

    def test_timeline(self):
        """TEST-127-05: Timeline is specified."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert design.timeline_weeks > 0

    def test_design_from_gap(self):
        """TEST-127-06: Can create design from gap dict."""
        designer = StudyDesigner()
        design = designer.design_from_gap({
            "title": "Missing evaluation on multilingual data",
            "description": "No work has evaluated X on non-English data",
        })
        assert isinstance(design, StudyDesign)
        assert design.idea_title != ""

    def test_publication_strategy(self):
        """TEST-127-07: Publication strategy is specified."""
        designer = StudyDesigner()
        design = designer.design_from_idea(self._sample_idea())
        assert design.publication_strategy != ""
        assert "paper" in design.publication_strategy.lower()
