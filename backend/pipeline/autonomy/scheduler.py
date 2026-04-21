"""Autonomous scheduler — periodic pipeline execution on a timer.

Wraps the orchestrator's autonomous_cycle() in a long-running asyncio.Task
that wakes up on a configurable interval, runs research cycles, and
handles errors gracefully without crashing the scheduler.

Reference: Hermes cron/ system for scheduled tasks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.orchestrator import PipelineOrchestrator

logger = logging.getLogger(__name__)


class AutonomousScheduler:
    """Periodic scheduler for autonomous pipeline execution."""

    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        interval_seconds: int = 3600,
        max_cycles_per_wake: int = 3,
    ):
        self._orchestrator = orchestrator
        self._interval = interval_seconds
        self._max_cycles = max_cycles_per_wake
        self._task: asyncio.Task | None = None
        self._running = False
        self._cycle_count = 0
        self._last_cycle_time: float | None = None
        self._last_error: str | None = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def last_cycle_time(self) -> float | None:
        return self._last_cycle_time

    @property
    def last_error(self) -> str | None:
        return self._last_error

    def status(self) -> dict:
        """Return current scheduler status."""
        return {
            "running": self._running,
            "interval_seconds": self._interval,
            "max_cycles_per_wake": self._max_cycles,
            "cycle_count": self._cycle_count,
            "last_cycle_time": self._last_cycle_time,
            "last_error": self._last_error,
        }

    async def start(self) -> None:
        """Start the scheduler as a background task."""
        if self._running:
            logger.warning("Scheduler already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler started (interval=%ds, max_cycles=%d)", self._interval, self._max_cycles)

    async def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running:
            return
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Scheduler stopped after %d cycles", self._cycle_count)

    async def _run_loop(self) -> None:
        """Main scheduler loop: sleep -> run cycles -> repeat."""
        while self._running:
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break

            if not self._running:
                break

            try:
                logger.info("Scheduler wake: starting autonomous cycle")
                t0 = time.time()
                results = await self._orchestrator.autonomous_cycle(
                    max_autonomous_runs=self._max_cycles,
                )
                elapsed = time.time() - t0
                self._cycle_count += 1
                self._last_cycle_time = time.time()
                self._last_error = None
                logger.info(
                    "Scheduler cycle %d complete: %d results in %.1fs",
                    self._cycle_count, len(results), elapsed,
                )
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = str(e)
                logger.error("Scheduler cycle failed: %s", e, exc_info=True)
                # Continue running — don't crash the scheduler on individual cycle failures
