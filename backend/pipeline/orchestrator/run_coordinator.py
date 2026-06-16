"""Run Coordinator — owns the stage loop and sequencing decisions.

Extracted from PipelineOrchestrator.run() to isolate:
- Strategy-based stage skipping
- Doom loop detection
- Resume support (skip completed stages)
- Model routing cascade (ModelManager → TaskRouter → user-config)
- Operation executor delegation (model lifecycle)
- Policy gate evaluation
- Stage execution with heartbeat
- Post-stage processing delegation
- Checkpoint save between stages
- Stop/cancel checks

The coordinator does NOT own:
- Model lifecycle (OperationExecutor does)
- Stage execution mechanics (StageExecutor does)
- Post-stage result processing (StageLifecycle does)
- Persistence mechanics (PipelinePersistence does)

The orchestrator delegates to the coordinator. The coordinator
receives all dependencies via constructor injection.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import PipelineStage, StageContext
    from backend.pipeline.execution.run_state import RunCheckpoint
    from backend.api.run_service import RunService

logger = logging.getLogger(__name__)


class RunCoordinator:
    """Coordinates the pipeline stage loop.

    Receives a reference to the orchestrator (which holds all wired
    dependencies) and runs the stage loop against it. This is an
    extraction, not a redesign — behavior is identical to the inline
    loop that was in ``PipelineOrchestrator.run()``.
    """

    def __init__(self, orchestrator: "PipelineOrchestrator") -> None:
        self._orch = orchestrator

    async def execute_stage_loop(
        self,
        stages: list["PipelineStage"],
        ctx: "StageContext",
        result: "PipelineResult",
        checkpoint: "RunCheckpoint",
        run_id: str,
        domain: str,
        db_run_id: int | None,
        skip_stages: set[str] | None = None,
        run_svc: "RunService | None" = None,
    ) -> bool:
        """Execute the pipeline stage loop.

        Returns True if all stages completed, False if the pipeline
        stopped early (cancellation, abort, doom loop).
        """
        from backend.pipeline.result import StageReport
        from backend.pipeline.stages import ExportStage

        should_continue = True

        for stage in stages:
            # ── 1. Strategy skip ──────────────────────────────
            strategy_stage = self._orch._strategy_config.stages.get(stage.name)
            if strategy_stage is None or not strategy_stage.enabled:
                logger.info("Strategy '%s' skips stage: %s", self._orch._strategy_name, stage.name)
                result.stage_report.append(StageReport(
                    name=stage.name,
                    status="skipped_by_strategy",
                    skip_reason=f"Strategy {self._orch._strategy_name}",
                ))
                continue

            # ── 2. Doom loop skip ─────────────────────────────
            if self._orch._lifecycle.doom_detected and stage.name not in ("export",):
                result.stage_report.append(StageReport(
                    name=stage.name,
                    status="skipped_by_doom",
                    skip_reason="Doom loop detected — skipping optional stage",
                ))
                continue

            # ── 3. Resume skip ────────────────────────────────
            if skip_stages and stage.name in skip_stages:
                logger.info("Skipping completed stage (resume): %s", stage.name)
                continue

            logger.info("=== %s ===", stage.name.replace("_", " ").title())

            # ── 4. DB stage tracking ──────────────────────────
            if db_run_id:
                self._orch._persistence.advance_stage(db_run_id, stage.name)

            # ── 5. Model routing cascade ──────────────────────
            await self._route_model_for_stage(stage, ctx, run_id)

            # ── 6. Operation executor (model lifecycle) ───────
            await self._ensure_model_loaded(stage, ctx)

            # ── 7. Policy gate ────────────────────────────────
            gate_result = await self._evaluate_policy_gate(stage)
            if gate_result == "deny":
                result.stage_report.append(StageReport(
                    name=stage.name, status="skipped_by_policy",
                    skip_reason="Governance policy denied",
                ))
                continue
            elif gate_result == "gate_rejected":
                result.stage_report.append(StageReport(
                    name=stage.name, status="skipped_by_policy",
                    skip_reason="Approval denied",
                ))
                continue

            # ── 8. Stage execution ────────────────────────────
            t0 = time.time()

            # Cross-stage context: load prior outputs
            if self._orch._services.cross_stage_ctx:
                prior = await self._orch._services.cross_stage_ctx.load_prior_context(run_id, stage.name)
                if prior:
                    ctx.params["prior_context"] = prior

            from backend.pipeline.tracing import create_span, SpanKind
            with create_span(SpanKind.STAGE, stage.name, run_id=run_id) as span:
                prepared_ctx = await self._orch._compaction.prepare_context(ctx, stage.name)

                # Heartbeat
                heartbeat = None
                if getattr(self._orch._settings, "heartbeat_enabled", True):
                    from backend.pipeline.execution.heartbeat import StageHeartbeat
                    heartbeat = StageHeartbeat(
                        checkpoint, self._orch._persistence,
                        interval_seconds=getattr(self._orch._settings, "heartbeat_interval_seconds", 30.0),
                    )
                    await heartbeat.start(stage.name)

                try:
                    # Update provider stage context
                    if hasattr(self._orch._provider, '_stage'):
                        self._orch._provider._stage = stage.name
                    if hasattr(self._orch._provider, '_run_id'):
                        self._orch._provider._run_id = run_id

                    # Set async context var for stage routing
                    from backend.providers.stage_context import set_stage, reset_stage
                    _stage_token = set_stage(stage.name)
                    try:
                        should_continue = await self._orch._execute_stage_with_retry(
                            stage, prepared_ctx, checkpoint
                        )
                    finally:
                        reset_stage(_stage_token)

                    elapsed = time.time() - t0
                    result.stage_report.append(StageReport(
                        name=stage.name,
                        status="executed",
                        elapsed_s=round(elapsed, 3),
                        retries_used=getattr(self._orch, '_last_stage_retries', 0),
                    ))
                except Exception as e:
                    elapsed = time.time() - t0
                    import traceback as _tb
                    logger.error(
                        "Stage '%s' failed (continuing pipeline): %s\n%s",
                        stage.name, e, _tb.format_exc(),
                    )
                    result.stage_report.append(StageReport(
                        name=stage.name,
                        status="skipped_by_error",
                        elapsed_s=round(elapsed, 3),
                        error=str(e)[:500],
                        retries_used=0,
                    ))
                    if heartbeat:
                        await heartbeat.stop()
                    self._orch._record_stage(stage.name, t0)
                    continue
                finally:
                    if heartbeat:
                        await heartbeat.stop()

            elapsed = time.time() - t0
            self._orch._record_stage(stage.name, t0)

            # ── 9. Post-stage processing (delegated) ──────────
            await self._orch._lifecycle.post_stage_common(
                stage, result, ctx, elapsed, run_id, domain,
                strategy=self._orch._strategy_name,
            )

            stage_result = await self._orch._lifecycle.post_stage_specific(
                stage, result, ctx, run_id, db_run_id, domain,
                strategy=self._orch._strategy_name,
                should_continue=should_continue,
            )
            if stage_result == "abort":
                reported_names = {r.name for r in result.stage_report}
                for remaining in stages:
                    if remaining.name not in reported_names and not isinstance(remaining, ExportStage):
                        result.stage_report.append(StageReport(
                            name=remaining.name, status="not_reached",
                        ))
                self._orch._persist_stage_report(result, db_run_id)
                return False

            # Cross-stage context: persist stage outputs
            if self._orch._services.cross_stage_ctx:
                await self._orch._persist_stage_context(run_id, stage.name, ctx, result)

            # ── 10. Checkpoint save ───────────────────────────
            checkpoint.mark_stage_completed(stage.name)
            next_idx = self._orch._STAGE_ORDER.index(stage.name) + 1 if stage.name in self._orch._STAGE_ORDER else -1
            if next_idx < len(stages):
                checkpoint.mark_stage_running(stages[next_idx].name)
            self._orch._persistence.save_checkpoint(checkpoint)

            # ── 11. Doom loop check ───────────────────────────
            if self._orch._lifecycle.doom_detected and not isinstance(stage, ExportStage):
                logger.info("Doom detected — skipping remaining optional stages")
                reported_names = {r.name for r in result.stage_report}
                for remaining_stage in stages:
                    if (
                        remaining_stage.name not in reported_names
                        and not isinstance(remaining_stage, ExportStage)
                    ):
                        result.stage_report.append(StageReport(
                            name=remaining_stage.name,
                            status="skipped_by_doom",
                            skip_reason="Doom loop detected",
                        ))
                continue

            # ── 12. Stop / cancel check ───────────────────────
            # Check durable cancellation via RunService, then fall back to _should_stop
            cancelled = False
            if run_svc:
                try:
                    cancelled = run_svc.is_cancelled(run_id)
                except (RuntimeError, ValueError, OSError):
                    pass  # RunService unavailable — fall through to legacy check
            if not should_continue or self._orch._should_stop() or cancelled:
                reported_names = {r.name for r in result.stage_report}
                for stage_name in self._orch._STAGE_ORDER:
                    if stage_name not in reported_names:
                        result.stage_report.append(StageReport(
                            name=stage_name, status="not_reached",
                        ))
                self._orch._persist_stage_report(result, db_run_id)
                return False

        return True

    # ── Private helpers (extracted from inline code) ─────────

    async def _route_model_for_stage(
        self,
        stage: "PipelineStage",
        ctx: "StageContext",
        run_id: str,
    ) -> None:
        """Execute the model routing cascade for a stage.

        Order: ModelManager → TaskRouter → user-config.
        Sets ctx.provider_override to the resolved provider, or None.
        """
        # Universal Model Manager takes priority
        if self._orch._model_manager:
            try:
                mm_stage = self._orch._mm_stage_aliases.get(stage.name, stage.name)
                ctx.provider_override = self._orch._model_manager.get_provider(mm_stage)
                model_info = self._orch._model_manager.get_stage_model(mm_stage)
                if model_info:
                    logger.debug(
                        "ModelManager: stage '%s' -> '%s' (from %s)",
                        stage.name, model_info.model_id, model_info.endpoint_url,
                    )
            except Exception as e:
                logger.warning("ModelManager failed for stage '%s': %s", stage.name, e)
                ctx.provider_override = None

        # Legacy: TaskRouter
        if self._orch._task_router and not ctx.provider_override:
            ctx.provider_override = self._orch._task_router.get_provider(stage.name, run_id)

        # Legacy: User-configured per-stage model override
        if not ctx.provider_override:
            from backend.api.routes.model_config import get_stage_model
            user_model = get_stage_model(stage.name)
            if user_model and user_model != "auto":
                try:
                    ctx.provider_override = self._orch._resolve_user_model(user_model)
                except Exception as e:
                    logger.warning(
                        "User model '%s' for stage '%s' failed, using default: %s",
                        user_model, stage.name, e,
                    )

    async def _ensure_model_loaded(
        self,
        stage: "PipelineStage",
        ctx: "StageContext",
    ) -> None:
        """Delegate model lifecycle to OperationExecutor.

        The executor is the ONLY component that loads/unloads/swaps models.
        """
        _executor = getattr(self._orch, '_operation_executor', None)
        if _executor and ctx.provider_override:
            _resolved_model = (
                getattr(ctx.provider_override, '_model', None)
                or getattr(ctx.provider_override, 'default_model', None)
            )
            if _resolved_model:
                try:
                    from backend.config import get_settings as _gs
                    _ctx_len = _gs().lmstudio_context_length
                    await _executor.ensure_model_loaded(
                        _resolved_model, context_length=_ctx_len,
                    )
                except (RuntimeError, OSError, ConnectionError) as _op_err:
                    logger.warning(
                        "Operation executor failed for stage '%s' "
                        "(model '%s'): %s — continuing",
                        stage.name, _resolved_model, _op_err,
                    )

    async def _evaluate_policy_gate(
        self,
        stage: "PipelineStage",
    ) -> str:
        """Evaluate governance policy before stage execution.

        Returns:
            "allow" — stage may proceed
            "deny" — stage denied by policy
            "gate_rejected" — gate requested but approval was denied
        """
        if not self._orch._services.governance_policy:
            return "allow"

        from backend.pipeline.governance.policy import PolicyAction

        decision = self._orch._services.governance_policy.evaluate(
            scope=stage.name,
            capability="execute",
        )

        if decision.action == PolicyAction.DENY:
            logger.warning(
                "Governance policy DENIED stage '%s': %s",
                stage.name, decision.reason,
            )
            if self._orch._services.governance_audit:
                from backend.pipeline.governance.events import GovernanceEvent
                self._orch._services.governance_audit.record(GovernanceEvent(
                    event_type="policy.deny",
                    stage=stage.name,
                    content_hash="",
                    checks_summary=f"Rule: {decision.rule_name}, Reason: {decision.reason}",
                ))
            return "deny"

        if decision.action == PolicyAction.GATE:
            logger.info(
                "Governance policy GATE on stage '%s': %s — awaiting approval",
                stage.name, decision.reason,
            )
            if self._orch._services.governance_audit:
                from backend.pipeline.governance.events import GovernanceEvent
                self._orch._services.governance_audit.record(GovernanceEvent(
                    event_type="policy.gate",
                    stage=stage.name,
                    content_hash="",
                    checks_summary=f"Rule: {decision.rule_name}, Awaiting approval",
                ))

            if hasattr(self._orch, "_approval_manager"):
                approval = await self._orch._services.approval_manager.request_approval(
                    stage=stage.name,
                    reason=decision.reason,
                    rule_name=decision.rule_name,
                )
                if approval.status.value != "approved":
                    logger.warning(
                        "Stage '%s' %s: %s",
                        stage.name, approval.status.value,
                        approval.amendment or decision.reason,
                    )
                    return "gate_rejected"

        return "allow"
