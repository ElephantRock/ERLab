"""Regression: autonomous_experiment_design persists even when
paper synthesis times out or fails."""
from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    PaperSynthesisStage,
    StageContext,
)


class TestMetadataPersistsThroughFailure:
    def test_design_in_metadata_before_synthesis_call(self):
        """Pre-synthesis persistence writes autonomous design
        to proposal metadata BEFORE synthesize_paper is called."""
        design_state = {
            "status": "designed",
            "capability_id": (
                "tabular_calibration_selective_v1"
            ),
            "selected_proposal_idx": 0,
            "research_question": "test",
            "specs": [
                {"experiment_spec_id": "auto-iris"},
                {"experiment_spec_id": "auto-wine"},
            ],
            "diagnostics": [],
        }

        proposal = SimpleNamespace(
            title="Test",
            to_markdown=lambda: "test",
            metadata={},
        )

        ctx = StageContext(
            result=PipelineResult(),
            domain="ML",
        )
        ctx.params["autonomous_experiment_design"] = (
            design_state
        )

        captured_metadata = {}

        async def _mock_synthesize(**kwargs):
            raw = getattr(proposal, "metadata", None)
            if isinstance(raw, str):
                with contextlib.suppress(
                    json.JSONDecodeError, TypeError,
                ):
                    captured_metadata.update(json.loads(raw))
            elif isinstance(raw, dict):
                captured_metadata.update(raw)
            return SimpleNamespace(
                success=False,
                paper_markdown="",
                word_count=0,
                sections_generated=0,
                sections_total=0,
                synthesis_strategy="failed",
                workflow_state="timeout",
                source_map=[],
                section_checkpoints={},
                error="timed out",
            )

        stage = PaperSynthesisStage()

        with patch(
            "backend.pipeline.synthesis."
            "synthesis_service.synthesize_paper",
            new=_mock_synthesize,
        ), contextlib.suppress(Exception):
            asyncio.run(
                stage._synthesize_paper_for_proposal(
                    0,
                    proposal,
                    ctx,
                    None,
                    [],
                    [],
                    8192,
                )
            )

        assert (
            "autonomous_experiment_design"
            in captured_metadata
        ), (
            "autonomous_experiment_design must be persisted"
            " BEFORE the synthesis call"
        )
        assert captured_metadata[
            "autonomous_experiment_design"
        ]["status"] == "designed"
        assert len(
            captured_metadata[
                "autonomous_experiment_design"
            ]["specs"]
        ) == 2

    def test_no_autonomous_design_no_persistence(self):
        """When autonomous design is absent, nothing is
        written to metadata."""
        proposal = SimpleNamespace(
            title="Test",
            to_markdown=lambda: "test",
            metadata={},
        )
        assert (
            "autonomous_experiment_design"
            not in proposal.metadata
        )
