"""StageLogger — writes one JSON entry per stage execution.

BATCH-180 / HB-03: Every stage execution MUST produce exactly one JSON log
entry with: run_id, stage, timestamp, event, elapsed_s, config, inputs,
outputs, error.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Fields required in every log entry (HB-03)
REQUIRED_FIELDS = (
    "run_id",
    "stage",
    "timestamp",
    "event",
    "elapsed_s",
    "config",
    "inputs",
    "outputs",
    "error",
)


class StageLogger:
    """Append-only JSON-lines logger for pipeline stage execution.

    Each call to :meth:`log` or :meth:`log_error` appends one JSON object
    (one line) to the log file.  The file is never truncated.
    """

    def __init__(self, run_id: str, log_dir: str | Path = "logs/pipeline") -> None:
        self._run_id = run_id
        self._log_dir = Path(log_dir)
        self._log_file = self._log_dir / f"{run_id}.jsonl"

    # ── public API ────────────────────────────────────────────

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def log_file(self) -> Path:
        return self._log_file

    def log(
        self,
        *,
        stage: str,
        event: str,
        elapsed_s: float,
        config: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write a *success* log entry and return it."""
        entry = self._build_entry(
            stage=stage,
            event=event,
            elapsed_s=elapsed_s,
            config=config or {},
            inputs=self._normalize_counts(inputs or {}),
            outputs=self._normalize_counts(outputs or {}),
            error=None,
        )
        self._append(entry)
        return entry

    def log_error(
        self,
        *,
        stage: str,
        event: str,
        elapsed_s: float,
        error: str,
        config: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Write an *error* log entry and return it."""
        entry = self._build_entry(
            stage=stage,
            event=event,
            elapsed_s=elapsed_s,
            config=config or {},
            inputs=self._normalize_counts(inputs or {}),
            outputs=self._normalize_counts(outputs or {}),
            error=error,
        )
        self._append(entry)
        return entry

    def read_entries(self) -> list[dict[str, Any]]:
        """Read all log entries from the log file."""
        if not self._log_file.exists():
            return []
        entries: list[dict[str, Any]] = []
        with open(self._log_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    # ── internal ──────────────────────────────────────────────

    @staticmethod
    def _build_entry(
        *,
        stage: str,
        event: str,
        elapsed_s: float,
        config: dict[str, Any],
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        error: str | None,
    ) -> dict[str, Any]:
        return {
            "run_id": "",  # filled by _append
            "stage": stage,
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "elapsed_s": round(elapsed_s, 4),
            "config": config,
            "inputs": inputs,
            "outputs": outputs,
            "error": error,
        }

    @staticmethod
    def _normalize_counts(data: dict[str, Any]) -> dict[str, Any]:
        """Ensure numeric count fields are integers."""
        result: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, (int, float)):
                result[key] = int(value)
            else:
                result[key] = value
        return result

    def _append(self, entry: dict[str, Any]) -> None:
        """Append one JSON entry to the log file (create dir if needed)."""
        entry["run_id"] = self._run_id
        self._log_dir.mkdir(parents=True, exist_ok=True)
        with open(self._log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")


def measure_stage(stage_name: str, logger: StageLogger, **kwargs: Any) -> _StageTimer:
    """Context-manager helper to measure stage elapsed time."""
    return _StageTimer(stage_name, logger, **kwargs)


class _StageTimer:
    """Context manager that logs start + complete/error around a stage."""

    def __init__(
        self,
        stage: str,
        logger: StageLogger,
        *,
        config: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        self._stage = stage
        self._logger = logger
        self._config = config or {}
        self._inputs = inputs or {}
        self._start: float = 0.0

    def __enter__(self) -> _StageTimer:
        self._start = time.time()
        self._logger.log(
            stage=self._stage,
            event="start",
            elapsed_s=0.0,
            config=self._config,
            inputs=self._inputs,
        )
        return self

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: Any) -> bool:
        elapsed = time.time() - self._start
        if exc_type is not None:
            self._logger.log_error(
                stage=self._stage,
                event="error",
                elapsed_s=elapsed,
                error=str(exc_val),
                config=self._config,
                inputs=self._inputs,
            )
        else:
            self._logger.log(
                stage=self._stage,
                event="complete",
                elapsed_s=elapsed,
                config=self._config,
                inputs=self._inputs,
            )
        return False  # don't suppress exceptions
