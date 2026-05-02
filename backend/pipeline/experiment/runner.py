"""Experiment runner — orchestrates validation and sandboxed execution (BATCH-49)."""

from __future__ import annotations

import logging
import time

from backend.config import get_settings
from backend.pipeline.experiment.models import ExperimentRequest, ExperimentResult
from backend.pipeline.experiment.validator import SecurityValidator
from backend.pipeline.sandboxing.manager import get_sandbox_manager
from backend.pipeline.sandboxing.protocol import SandboxConfig

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Runs experiment code in a sandbox after security validation."""

    def __init__(self) -> None:
        self._validator = SecurityValidator()

    async def run(self, request: ExperimentRequest) -> ExperimentResult:
        """Validate and execute experiment code.

        Args:
            request: The experiment request with code, inputs, and timeout.

        Returns:
            ExperimentResult with execution details.
        """
        settings = get_settings()

        # Security validation
        violations = self._validator.validate(request.code)
        if violations:
            return ExperimentResult(
                success=False,
                stdout="",
                stderr="Security validation failed:\n" + "\n".join(f"- {v}" for v in violations),
                exit_code=1,
                execution_time_seconds=0.0,
                error="Security validation failed",
            )

        # Build sandbox config
        timeout = request.timeout or settings.experiment_default_timeout
        config = SandboxConfig(timeout_seconds=timeout)

        # Execute in sandbox
        start = time.monotonic()
        try:
            manager = get_sandbox_manager()
            if request.language == "python":
                result = await manager.execute_python(request.code, config)
            else:
                result = await manager.execute_shell(request.code, config)

            elapsed = time.monotonic() - start
            return ExperimentResult(
                success=result.exit_code == 0 and not result.timed_out,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_code,
                execution_time_seconds=round(elapsed, 3),
                error="Execution timed out" if result.timed_out else None,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error("Experiment execution failed: %s", e)
            return ExperimentResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
                execution_time_seconds=round(elapsed, 3),
                error=str(e),
            )
