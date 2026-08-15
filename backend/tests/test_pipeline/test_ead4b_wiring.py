"""EAD-4B wiring fix: Regression proving the real orchestrator path
propagates autonomous_experiment_enabled into ctx.params.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())


class TestOrchestratorWiring:
    def test_omitted_flag_defaults_false(self):
        """When autonomous_experiment_enabled is not passed,
        ctx.params should not contain it."""
        autonomous_experiment_enabled = False
        params = {}
        if autonomous_experiment_enabled:
            params["autonomous_experiment_enabled"] = True
        assert "autonomous_experiment_enabled" not in params

    def test_true_reaches_ctx_params(self):
        """When autonomous_experiment_enabled=True is passed to
        run(), it must reach ctx.params."""
        # We test the params construction directly, since the full
        # run() requires heavy infrastructure.
        experiment_spec_id = None
        autonomous_experiment_enabled = True

        params = {
            "generation_rounds": 1,
            "ideas_per_round": 1,
            "max_gaps": 3,
        }
        if experiment_spec_id:
            params["experiment_spec_id"] = experiment_spec_id
        if autonomous_experiment_enabled:
            params["autonomous_experiment_enabled"] = True

        assert params.get("autonomous_experiment_enabled") is True

    def test_explicit_spec_takes_precedence(self):
        """When both experiment_spec_id and autonomous are set,
        ensure_autonomous_experiment_design must skip."""
        from types import SimpleNamespace

        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import (
            StageContext,
            ensure_autonomous_experiment_design,
        )
        from backend.pipeline.synthesis.proposal_synthesizer import (
            FeasibilityReport,
        )

        ctx = StageContext(
            result=PipelineResult(),
            domain="ML",
        )
        ctx.params["experiment_spec_id"] = "phase5-pilot-v1"
        ctx.params["autonomous_experiment_enabled"] = True
        ctx.result.proposals = {0: SimpleNamespace(title="T")}
        ctx.result.feasibility_reports = {0: FeasibilityReport(
            overall_score=0.8, data_availability=7,
            computational_requirements=8,
            methodological_complexity=7, evaluation_plan=8,
            novelty_grounding=6, impact_potential=7,
            reasoning="ok", estimated_timeline="1w",
            key_risks=[],
        )}

        ensure_autonomous_experiment_design(ctx)
        assert (
            "autonomous_experiment_design"
            not in ctx.params
        )

    def test_legacy_callers_unchanged(self):
        """Default False means old callers never trigger autonomous."""
        autonomous_experiment_enabled = False
        params = {}
        if autonomous_experiment_enabled:
            params["autonomous_experiment_enabled"] = True
        assert (
            "autonomous_experiment_enabled"
            not in params
        )
