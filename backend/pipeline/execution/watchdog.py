"""Watchdog that detects and marks stuck pipeline runs.

Pattern from Airflow's _find_task_instances_without_heartbeats:
detects runs that have been in 'running' status beyond a configurable timeout
and marks them as 'failed' with a descriptive message.

The watchdog is designed to be called:
  - Periodically as a background task
  - On-demand via API endpoint POST /pipeline/watchdog
  - At startup to clean up orphaned runs from previous crashes
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.persistence import PipelinePersistence

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = timedelta(minutes=30)
DEFAULT_POLL_INTERVAL = 60.0


class PipelineWatchdog:
    """Detects and marks stuck pipeline runs.

    Usage:
        watchdog = PipelineWatchdog(persistence)
        cleaned = await watchdog.check_and_mark_stale_runs()
        print(f"Marked {cleaned} stale runs as failed")
    """

    def __init__(
        self,
        persistence: PipelinePersistence,
        timeout: timedelta = DEFAULT_TIMEOUT,
    ) -> None:
        self._persistence = persistence
        self._timeout = timeout

    async def check_and_mark_stale_runs(self) -> int:
        """Find and mark stale runs. Returns count of runs marked as failed.

        Only affects runs with status='running' (HB-02).
        """
        stale_runs = self._persistence.find_stale_runs(max_age=self._timeout)

        if not stale_runs:
            logger.debug("No stale pipeline runs found")
            return 0

        marked = 0
        for run in stale_runs:
            try:
                age_description = f"{self._timeout}"
                message = (
                    f"Watchdog: run has been in 'running' status longer than "
                    f"{age_description}. Marking as failed."
                )
                self._persistence.mark_stale_run_failed(run.id, message)
                marked += 1
                logger.warning(
                    "Marked stale run %s (id=%d) as failed: no activity for %s",
                    getattr(run, 'session_id', 'unknown'),
                    run.id,
                    self._timeout,
                )
            except Exception as e:
                logger.error("Failed to mark stale run %d as failed: %s", run.id, e)

        logger.info("Watchdog: marked %d/%d stale runs as failed", marked, len(stale_runs))
        return marked

    def check_sync(self) -> int:
        """Synchronous version of check_and_mark_stale_runs."""
        stale_runs = self._persistence.find_stale_runs(max_age=self._timeout)

        if not stale_runs:
            return 0

        marked = 0
        for run in stale_runs:
            try:
                message = (
                    f"Watchdog: run has been in 'running' status longer than "
                    f"{self._timeout}. Marking as failed."
                )
                self._persistence.mark_stale_run_failed(run.id, message)
                marked += 1
            except Exception as e:
                logger.error("Failed to mark stale run %d as failed: %s", run.id, e)

        return marked
