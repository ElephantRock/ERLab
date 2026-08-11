"""Granular progress reporter for pipeline stages.

Emits human-readable progress messages during pipeline execution,
replacing coarse "Stage N/7 complete" with specific step descriptions.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProgressEvent:
    """A granular progress event emitted during pipeline execution."""

    event_type: str = "progress"
    stage: str = ""
    step: str = ""
    message: str = ""
    progress_pct: float = 0.0
    timestamp: float = field(default_factory=time.time)
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        # Clamp progress_pct to [0.0, 1.0]
        self.progress_pct = max(0.0, min(1.0, self.progress_pct))


class ProgressReporter:
    """Emit granular progress events from within pipeline stages.

    The reporter calls a callback for each event. The StreamingManager
    broadcasts these events to SSE subscribers.

    Usage in a stage:
        reporter.stage_start("ingestion", total_steps=5)
        reporter.stage_step("arxiv_search", f"Searching arXiv for '{query}'...")
        reporter.stage_step("arxiv_results", f"Found {len(results)} papers from arXiv")
        reporter.stage_complete("ingestion")
    """

    def __init__(
        self,
        callback: Callable[[ProgressEvent], None] | None = None,
        stage_name: str = "",
    ) -> None:
        self._callback = callback
        self._stage_name = stage_name
        self._total_steps = 0
        self._current_step = 0

    def set_callback(self, callback: Callable[[ProgressEvent], None]) -> None:
        """Set or update the callback."""
        self._callback = callback

    def emit(self, stage: str, step: str, message: str, progress_pct: float = 0.0) -> None:
        """Emit a progress event. Non-blocking (HB-03)."""
        event = ProgressEvent(
            event_type="progress",
            stage=stage or self._stage_name,
            step=step,
            message=message,
            progress_pct=progress_pct,
        )
        if self._callback:
            try:
                self._callback(event)
            except Exception as e:
                logger.debug("Progress callback error (non-fatal): %s", e)

    def stage_start(self, stage: str, total_steps: int = 0) -> None:
        """Emit a stage start event with total step count."""
        self._stage_name = stage
        self._total_steps = total_steps
        self._current_step = 0
        self.emit(
            stage=stage,
            step="start",
            message=f"Starting {stage.replace('_', ' ')}...",
            progress_pct=0.0,
            # details={"total_steps": total_steps},  # Not in dataclass
        )

    def stage_step(self, step: str, message: str) -> None:
        """Emit a step progress event within the current stage."""
        self._current_step += 1
        pct = 0.0
        if self._total_steps > 0:
            pct = self._current_step / self._total_steps
        self.emit(
            stage=self._stage_name,
            step=step,
            message=message,
            progress_pct=pct,
        )

    def stage_complete(self, stage: str) -> None:
        """Emit a stage completion event."""
        self.emit(
            stage=stage,
            step="complete",
            message=f"Completed {stage.replace('_', ' ')}",
            progress_pct=1.0,
        )
