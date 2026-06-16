"""Stage executor — handles stage execution, retry logic, and recording.

Extracted from PipelineOrchestrator to isolate execution mechanics
from the orchestration flow.
"""

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

from backend.pipeline.result import StageReport
from backend.providers.retry import retry_llm_call

if TYPE_CHECKING:
    from backend.pipeline.stages import PipelineStage, StageContext
    from backend.pipeline.execution.run_state import RunCheckpoint

logger = logging.getLogger(__name__)


class StageExecutor:
    """Executes pipeline stages with retry, timeout, and checkpoint support."""

    def __init__(self, settings, persistence, stage_callback=None,
                 cost_tracker=None, token_counter=None, budget=None,
                 strategy_name: str = "deep_research") -> None:
        self._settings = settings
        self._persistence = persistence
        self._stage_callback = stage_callback
        self._cost_tracker = cost_tracker
        self._token_counter = token_counter
        self._budget = budget
        self._strategy_name = strategy_name
        self._last_stage_retries = 0
        self._current_run_id: str | None = None
        self._stage_logger = None

    def set_run_id(self, run_id: str) -> None:
        """Set the current run ID for structured logging."""
        self._current_run_id = run_id
        self._stage_logger = None  # Reset for new run

    async def execute_with_retry(
        self,
        stage: "PipelineStage",
        ctx: "StageContext",
        checkpoint: "RunCheckpoint",
    ) -> bool:
        """Execute a stage with retry, exponential backoff, checkpointing, and timeout."""
        max_retries = getattr(self._settings, "stage_max_retries", 3)
        base_delay = getattr(self._settings, "stage_retry_base_delay", 2.0)
        max_delay = getattr(self._settings, "stage_retry_max_delay", 120.0)
        jitter_frac = getattr(self._settings, "stage_retry_jitter", 0.1)

        # LLM-level rate limit retry
        max_llm_retries = getattr(self._settings, "llm_rate_limit_retries", 3)

        # Per-stage timeout
        stage_timeouts = getattr(self._settings, "stage_timeouts", {})
        default_timeout = getattr(self._settings, "stage_default_timeout", 1800)
        stage_timeout = stage_timeouts.get(stage.name, default_timeout)

        for attempt in range(max_retries + 1):
            try:
                async def _run():
                    result, retries = await retry_llm_call(
                        lambda: stage.execute(ctx),
                        max_retries=max_llm_retries,
                    )
                    self._last_stage_retries = retries
                    return result

                result = await asyncio.wait_for(_run(), timeout=stage_timeout)
                return result
            except asyncio.TimeoutError:
                self._last_stage_retries = 0
                logger.error(
                    "Stage %s TIMED OUT after %ds (attempt %d/%d)",
                    stage.name, stage_timeout, attempt + 1, max_retries + 1,
                )
                if attempt >= max_retries:
                    raise RuntimeError(
                        f"Stage {stage.name} timed out after {stage_timeout}s "
                        f"across {max_retries + 1} attempts"
                    )
                delay = min(base_delay * (2 ** attempt), max_delay)
                await asyncio.sleep(delay)
            except Exception as exc:
                self._last_stage_retries = 0
                checkpoint.mark_stage_failed(stage.name, str(exc))
                self._persistence.save_checkpoint(checkpoint)
                if attempt >= max_retries:
                    logger.error(
                        "Stage %s exhausted %d retries: %s", stage.name, max_retries, exc
                    )
                    raise
                delay = min(base_delay * (2 ** attempt), max_delay)
                jitter = delay * jitter_frac
                delay += random.uniform(-jitter, jitter)
                logger.warning(
                    "Stage %s failed (attempt %d/%d), retrying in %.1fs: %s",
                    stage.name, attempt + 1, max_retries + 1, delay, exc,
                )
                await asyncio.sleep(delay)
        return False  # unreachable but satisfies type checker

    def record_stage(self, stage_name: str, start_time: float, stage_order: list[str]) -> None:
        """Record stage completion: callback, budget tracking, structured logging."""
        elapsed = time.time() - start_time

        # Callback for SSE/UI progress
        if self._stage_callback:
            idx = (
                stage_order.index(stage_name) + 1 if stage_name in stage_order else "?"
            )
            self._stage_callback(stage_name, idx, len(stage_order), elapsed)

        # Budget tracking
        if self._budget and self._token_counter:
            tokens = self._token_counter.snapshot().total_tokens
            cost_usd = 0.0
            if self._cost_tracker:
                stage_costs = self._cost_tracker.by_stage()
                cost_usd = stage_costs.get(stage_name, {}).get("total_cost_usd", 0.0)
            self._budget.record(stage_name, tokens=tokens, cost_usd=cost_usd, elapsed=elapsed)

        # Structured JSON logging (BATCH-184)
        try:
            from backend.pipeline.dag.stage_log import StageLogger
            if self._stage_logger is None:
                run_id = self._current_run_id or "unknown"
                self._stage_logger = StageLogger(run_id=run_id)
            self._stage_logger.log(
                stage=stage_name,
                event="complete",
                config={"strategy": self._strategy_name},
                inputs={},
                outputs={},
                elapsed_s=elapsed,
            )
        except Exception as e:
            logger.debug("StageLogger failed for %s: %s", stage_name, e)

        # Reset token counter per stage
        if self._token_counter:
            self._token_counter.reset()

    @property
    def last_stage_retries(self) -> int:
        return self._last_stage_retries

    async def execute_with_result(
        self,
        stage: "PipelineStage",
        ctx: "StageContext",
        checkpoint: "RunCheckpoint",
    ) -> "StageExecutionResult":
        """Execute a stage and return a typed StageExecutionResult.

        This is the compatibility bridge: old stages return ``bool``,
        which we wrap into a ``StageExecutionResult`` with
        ``is_compatibility_mode = True``.

        Until all stages are migrated to operation-scoped provider calls,
        results from this method have no model receipts and must be
        marked as compatibility mode.
        """
        from backend.pipeline.operations.types import StageExecutionResult, StageStatus

        try:
            success = await self.execute_with_retry(stage, ctx, checkpoint)
            return StageExecutionResult(
                status=StageStatus.COMPLETED if success else StageStatus.FAILED,
                # Compatibility mode: no receipts, no resource epoch.
                # Stages still call providers internally.
                model_receipts=[],
                resource_epoch=None,
                error=None if success else "Stage returned False",
            )
        except Exception as exc:
            return StageExecutionResult(
                status=StageStatus.FAILED,
                failure_class="unknown",
                error=str(exc)[:500],
                retryable=False,
            )
