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
from typing import TYPE_CHECKING

from backend.pipeline.operations.types import OperationError

if TYPE_CHECKING:
    from backend.api.run_service import RunService
    from backend.pipeline.execution.run_state import RunCheckpoint
    from backend.pipeline.orchestrator._orchestrator import PipelineOrchestrator
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import PipelineStage, StageContext

logger = logging.getLogger(__name__)


class RunCoordinator:
    """Coordinates the pipeline stage loop.

    Receives a reference to the orchestrator (which holds all wired
    dependencies) and runs the stage loop against it. This is an
    extraction, not a redesign — behavior is identical to the inline
    loop that was in ``PipelineOrchestrator.run()``.
    """

    def __init__(self, orchestrator: PipelineOrchestrator) -> None:
        self._orch = orchestrator

    async def execute_stage_loop(
        self,
        stages: list[PipelineStage],
        ctx: StageContext,
        result: PipelineResult,
        checkpoint: RunCheckpoint,
        run_id: str,
        domain: str,
        db_run_id: int | None,
        skip_stages: set[str] | None = None,
        run_svc: RunService | None = None,
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

            from backend.pipeline.tracing import SpanKind, create_span
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
                    # Update provider stage context. Prefer set_context() (which
                    # delegates through StageAwareProvider to GatewayProvider)
                    # so the inner provider receives the stage/run_id. Fall back
                    # to direct attribute assignment only for providers without
                    # set_context().
                    if hasattr(self._orch._provider, 'set_context'):
                        self._orch._provider.set_context(stage.name, run_id)
                    else:
                        if hasattr(self._orch._provider, '_stage'):
                            self._orch._provider._stage = stage.name
                        if hasattr(self._orch._provider, '_run_id'):
                            self._orch._provider._run_id = run_id

                    # Set async context var for stage routing
                    from backend.providers.stage_context import reset_stage, set_stage
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
                    # Q2 review P1: a stage that exhausted its retries on
                    # a gateway transport failure must terminalize the
                    # run's typed outcome — otherwise a non-autonomous
                    # run with earlier-produced gaps/ideas finalizes as
                    # SUCCEEDED despite the dead provider.
                    from backend.pipeline.gateway.transport import (
                        GatewayTransportError,
                    )
                    if isinstance(e, GatewayTransportError):
                        from backend.pipeline.result import (
                            PipelineOutcome,
                        )

                        result.outcome = PipelineOutcome.FAILED_EXECUTION
                        result.terminal_stage = stage.name
                        result.terminal_reason = (
                            f"gateway transport failure exhausted"
                            f" stage retries: {e}"
                        )
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
                self._orch._processor.persist_stage_report(result, db_run_id)
                return False

            # Cross-stage context: persist stage outputs
            if self._orch._services.cross_stage_ctx:
                await self._orch._processor.persist_stage_context(run_id, stage.name, ctx, result)

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
                self._orch._processor.persist_stage_report(result, db_run_id)
                return False

        return True

    # ── Private helpers (extracted from inline code) ─────────

    async def _route_model_for_stage(
        self,
        stage: PipelineStage,
        ctx: StageContext,
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
        stage: PipelineStage,
        ctx: StageContext,
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
                except (RuntimeError, OSError, ConnectionError, OperationError) as _op_err:
                    logger.warning(
                        "Operation executor failed for stage '%s' "
                        "(model '%s'): %s — continuing",
                        stage.name, _resolved_model, _op_err,
                    )

    async def _evaluate_policy_gate(
        self,
        stage: PipelineStage,
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

    async def resume_from_checkpoint(
        self,
        run_id: str,
        domain: str = "AI/NLP",
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        export_format: str | None = "markdown",
        max_stage_retries: int = 2,
    ) -> PipelineResult | None:
        """Resume a previously failed/interrupted pipeline run from checkpoint.

        Loads the checkpoint, skips completed stages, and continues from the
        next unfinished stage. Returns None if no checkpoint found.
        """
        from backend.pipeline.execution.run_state import StageStatus
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import StageContext
        from backend.pipeline.tracing import SpanKind, create_span

        orch = self._orch
        checkpoint = orch._persistence.load_checkpoint(run_id)
        if not checkpoint:
            logger.warning("No checkpoint found for run %s", run_id)
            return None

        completed_names = {s.stage_name for s in checkpoint.stages if s.status == StageStatus.COMPLETED}
        logger.info(
            "Resuming run %s: %d/%d stages already completed",
            run_id, len(completed_names), len(checkpoint.stages),
        )

        result = PipelineResult()
        result.run_id = run_id
        params: dict = {}
        db_run_id = None

        # State reconstruction: load prior outputs from database
        db_run = orch._persistence.get_run_by_uuid(run_id)
        if db_run:
            db_run_id = db_run.id
            try:
                loaded_gaps = orch._persistence.load_gaps(db_run_id)
                if loaded_gaps:
                    result.gaps = loaded_gaps
                    logger.info("Reconstructed %d gaps from database", len(loaded_gaps))
            except Exception as exc:
                logger.warning("Failed to reconstruct gaps: %s", exc)
            try:
                loaded_ideas = orch._persistence.load_ideas(db_run_id)
                if loaded_ideas:
                    result.ideas = loaded_ideas
                    logger.info("Reconstructed %d ideas from database", len(loaded_ideas))
            except Exception as exc:
                logger.warning("Failed to reconstruct ideas: %s", exc)

        # Cross-stage context: load additional persisted outputs
        if orch._services.cross_stage_ctx:
            try:
                prior = await orch._services.cross_stage_ctx.load_prior_context(run_id, "export")
                if prior:
                    params.update({"reconstructed_context": prior})
                    logger.info("Loaded cross-stage context with %d stages", len(prior))
            except Exception as exc:
                logger.warning("Failed to load cross-stage context: %s", exc)

        ctx = StageContext(
            result=result,
            domain=domain,
            run_id=run_id,
            db_run_id=db_run_id,
            params=params,
            search_queries=search_queries,
            max_gaps=max_gaps,
            rounds=orch._settings.generation_rounds,
            ideas_per=orch._settings.ideas_per_round,
            export_format=export_format,
        )

        for stage in orch._stages:
            if stage.name in completed_names:
                logger.info("Skipping completed stage: %s", stage.name)
                continue

            logger.info("=== [RESUME] %s ===", stage.name.replace("_", " ").title())

            for attempt in range(max_stage_retries + 1):
                try:
                    checkpoint.mark_stage_running(stage.name)
                    orch._persistence.save_checkpoint(checkpoint)

                    with create_span(SpanKind.STAGE, f"{stage.name} (resume)", run_id=run_id):
                        prepared_ctx = await orch._compaction.prepare_context(ctx, stage.name)
                        should_continue = await stage.execute(prepared_ctx)

                    elapsed = time.time() - time.time()
                    orch._executor.record_stage(stage.name, elapsed, orch._STAGE_ORDER)
                    await orch._services.hooks.dispatch_sync_safe(
                        "pipeline.stage.complete",
                        {"stage": stage.name, "elapsed": elapsed, "run_id": run_id},
                    )

                    checkpoint.mark_stage_completed(stage.name)
                    orch._persistence.save_checkpoint(checkpoint)
                    break
                except Exception as e:
                    logger.error(
                        "Stage %s failed (attempt %d/%d): %s",
                        stage.name, attempt + 1, max_stage_retries + 1, e,
                    )
                    if attempt == max_stage_retries:
                        checkpoint.mark_stage_failed(stage.name, str(e))
                        orch._persistence.save_checkpoint(checkpoint)
                        logger.error("Stage %s exhausted retries. Checkpoint saved.", stage.name)
                        # Q2 review P1: an exhausted gateway transport
                        # failure during resume terminalizes the typed
                        # outcome — the API must not surface a dead
                        # provider as a running/completed run.
                        from backend.pipeline.gateway.transport import (
                            GatewayTransportError,
                        )
                        if isinstance(e, GatewayTransportError):
                            from backend.pipeline.result import (
                                PipelineOutcome,
                            )
                            result.outcome = (
                                PipelineOutcome.FAILED_EXECUTION
                            )
                            result.terminal_stage = stage.name
                            result.terminal_reason = (
                                f"gateway transport failure"
                                f" exhausted stage retries (resume): {e}"
                            )
                        return result
                    import asyncio as _aio
                    await _aio.sleep(2 ** attempt)

            # Persistence (same as normal run) — P0.1: governed path
            if stage.name == "literature_search":
                if ctx.candidate_papers and db_run_id:
                    orch._persistence.persist_search_results(
                        ctx.candidate_papers, ctx.search_query_data, db_run_id,
                        execution_linkage_expectations=getattr(
                            ctx, "execution_linkage_expectations", None
                        ),
                    )
                    # P0.2.6: Reconcile on resume path too.
                    try:
                        from backend.db.database import _get_engine
                        from backend.pipeline.literature.run_reconciliation import (
                            reconcile_run_search,
                        )
                        reconcile_run_search(_get_engine(), db_run_id)
                    except Exception as e:
                        logger.warning("Resume run search reconciliation failed: %s", e)
                else:
                    orch._persistence.persist_papers(ctx.all_papers, db_run_id)
            elif stage.name == "gap_analysis":
                orch._persistence.persist_gaps(result, db_run_id)
            elif stage.name == "feasibility_scoring":
                orch._persistence.persist_ideas(result, db_run_id)
            elif stage.name == "proposal_synthesis":
                orch._persistence.persist_proposals(result, db_run_id)

            orch._processor.collect_warnings(result)
            if not should_continue:
                return result

        logger.info("=== Resumed Pipeline Complete ===")
        orch._persistence.mark_run_completed(db_run_id)
        return result
