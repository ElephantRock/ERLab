"""Case-4 R1 regression: false SUCCEEDED on initial persistence failure.

Adjudicated GENERIC_PRODUCT_DEFECT (2026-08-18): when the required
initial create_run_record() failed — returning None with a recorded
persistence warning — the orchestrator discarded its persistence
authority, executed every research stage for an hour, and still
finalized SUCCEEDED (invalid-attempt specimen: evidence/case4_r1_run.log
on the Case-4 evidence branch). The correction fails the run closed
BEFORE research execution, reusing the existing FAILED_EXECUTION
outcome with a persistence-initialization terminal stage/reason.

The scaffold here is intentionally minimal and drift-resistant: it
provides only what PipelineOrchestrator.run() touches between entry and
the persistence seam (the full-mock harness in
test_batch175_e2e_integration.py has drifted and no longer reaches
run()).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator
from backend.pipeline.result import PipelineOutcome


def _make_orch(create_run_record_returns) -> PipelineOrchestrator:
    """Real run() on a minimally-wired orchestrator (no real services)."""
    orch = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orch._settings = SimpleNamespace(
        generation_rounds=1,
        ideas_per_round=1,
        lmstudio_base_url="",
        notification_webhook_url=None,
        thinking_model_max_tokens=8192,
    )
    orch._strategy_name = "deep_research"
    orch._persistence = MagicMock()
    orch._persistence.create_run_record = MagicMock(
        return_value=create_run_record_returns
    )
    orch._persistence.get_warnings = MagicMock(
        return_value=["create_run_record: no such table: pipeline_runs"]
    )
    orch._lifecycle = MagicMock()
    orch._lifecycle.post_pipeline_finalize = AsyncMock()
    orch._processor = MagicMock()
    orch._services = SimpleNamespace(
        embedding_valid=True,
        evolver=None,
        agent=None,
        novelty=None,
        synthesizer=None,
        cross_stage_ctx=None,
        budget=None,
        plan_verifier=None,
        mcp_manager=None,
        session_manager=None,
        memory=None,
        hooks=SimpleNamespace(dispatch_sync_safe=AsyncMock()),
    )
    orch._stages = [SimpleNamespace(name="literature_search")]
    orch._enforce_required_provider_readiness = lambda: None
    return orch


class TestInitialPersistenceFailureFailsClosed:
    """Injected run-record creation failure must abort before stages."""

    def test_none_run_record_aborts_before_research_stages(self):
        orch = _make_orch(None)

        result = asyncio.run(orch.run(domain="AI/NLP"))

        assert result.outcome == PipelineOutcome.FAILED_EXECUTION
        assert result.terminal_stage == "persistence_initialization"
        assert "create_run_record" in (result.terminal_reason or "")
        assert any(
            "create_run_record" in w for w in result.persistence_warnings
        )
        # No research execution of any kind: no pipeline.start hook, no
        # checkpoint, no stage reports.
        orch._services.hooks.dispatch_sync_safe.assert_not_awaited()
        orch._persistence.save_checkpoint.assert_not_called()
        assert result.stage_report == []

    def test_none_run_record_cannot_return_succeeded(self):
        orch = _make_orch(None)

        result = asyncio.run(orch.run(domain="AI/NLP"))

        assert result.outcome != PipelineOutcome.SUCCEEDED
        assert result.outcome.is_failure

    def test_successful_run_record_path_unchanged(self):
        """With a working run record the run must proceed past the seam
        exactly as before: the stage coordinator receives the created
        db_run_id, and no persistence-initialization failure exists."""
        orch = _make_orch(1)

        with patch(
            "backend.pipeline.orchestrator.run_coordinator.RunCoordinator"
        ) as coordinator_cls:
            coordinator_cls.return_value.execute_stage_loop = AsyncMock(
                return_value=True
            )
            result = asyncio.run(orch.run(domain="AI/NLP"))

        orch._persistence.create_run_record.assert_called_once()
        assert result.terminal_stage != "persistence_initialization"
        assert result.outcome == PipelineOutcome.RUNNING  # loop stubbed
        kwargs = (
            coordinator_cls.return_value.execute_stage_loop.call_args.kwargs
        )
        assert kwargs.get("db_run_id") == 1
