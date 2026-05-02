"""Heartbeat-based stage execution monitoring.

A background task sends periodic heartbeat signals while a stage executes.
If heartbeats stop (process crash, hang), the stage checkpoint will show
a stale last_heartbeat timestamp, enabling external watchdogs to detect
and recover hung stages.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.execution.run_state import RunCheckpoint
    from backend.pipeline.persistence import PipelinePersistence

logger = logging.getLogger(__name__)


class StageHeartbeat:
    """Tracks stage execution health via periodic heartbeats.

    Usage:
        hb = StageHeartbeat(checkpoint, persistence, interval_seconds=30)
        await hb.start("gap_analysis")
        try:
            await stage.execute(ctx)
        finally:
            await hb.stop()
    """

    def __init__(
        self,
        checkpoint: RunCheckpoint,
        persistence: PipelinePersistence,
        interval_seconds: float = 30.0,
        timeout_seconds: float = 300.0,
    ) -> None:
        self._checkpoint = checkpoint
        self._persistence = persistence
        self._interval = interval_seconds
        self._timeout = timeout_seconds
        self._task: asyncio.Task | None = None
        self._stage_name: str = ""
        self._stop_event = asyncio.Event()

    async def start(self, stage_name: str) -> None:
        """Begin sending heartbeats for a stage."""
        self._stage_name = stage_name
        self._stop_event.clear()
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.debug("Heartbeat started for stage %s", stage_name)

    async def stop(self) -> None:
        """Stop sending heartbeats."""
        self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.debug("Heartbeat stopped for stage %s", self._stage_name)

    async def _heartbeat_loop(self) -> None:
        """Background loop that updates checkpoint heartbeats."""
        while not self._stop_event.is_set():
            try:
                # Update the checkpoint with current heartbeat timestamp
                for sc in self._checkpoint.stages:
                    if sc.stage_name == self._stage_name:
                        sc._last_heartbeat = time.monotonic()
                        break
                self._persistence.save_checkpoint(self._checkpoint)
            except Exception as exc:
                logger.warning("Heartbeat update failed for %s: %s", self._stage_name, exc)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._interval
                )
            except asyncio.TimeoutError:
                pass  # Normal: interval elapsed, loop continues
