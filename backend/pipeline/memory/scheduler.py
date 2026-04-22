"""Background consolidation scheduler — periodic sweep of memories."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.memory.consolidation import LLMConsolidator
    from backend.pipeline.memory.service import MemoryService

logger = logging.getLogger(__name__)


class ConsolidationScheduler:
    """Periodic background consolidation task."""

    def __init__(
        self,
        memory: MemoryService,
        consolidator: LLMConsolidator,
        interval_hours: int = 24,
    ) -> None:
        self._memory = memory
        self._consolidator = consolidator
        self._interval_hours = interval_hours
        self._task: asyncio.Task | None = None
        self._last_run: float | None = None
        self._sweeps_completed = 0
        self._entries_consolidated = 0

    async def start(self) -> None:
        """Begin periodic consolidation."""
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Consolidation scheduler started (interval=%dh)", self._interval_hours)

    async def stop(self) -> None:
        """Cancel background task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Consolidation scheduler stopped")

    async def _run_loop(self) -> None:
        """Main loop — sleep, then sweep."""
        interval_s = self._interval_hours * 3600
        try:
            while True:
                await asyncio.sleep(interval_s)
                await self._run_sweep()
        except asyncio.CancelledError:
            pass

    async def _run_sweep(self) -> None:
        """Execute one consolidation sweep."""
        logger.info("Starting consolidation sweep")
        stats = await self._consolidator.run_consolidation_sweep(self._memory)
        self._last_run = time.time()
        self._sweeps_completed += 1
        self._entries_consolidated += stats.get("scanned", 0)
        logger.info("Consolidation sweep complete: %s", stats)

    def status(self) -> dict:
        return {
            "running": self._task is not None and not self._task.done(),
            "last_run": self._last_run,
            "sweeps_completed": self._sweeps_completed,
            "entries_consolidated": self._entries_consolidated,
            "interval_hours": self._interval_hours,
        }
