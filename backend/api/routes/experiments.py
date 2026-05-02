"""Sandboxed experiment execution API routes (BATCH-49)."""

import logging

from fastapi import APIRouter

from backend.api.errors import BadRequestError, ForbiddenError
from backend.config import get_settings
from backend.pipeline.experiment.models import ExperimentRequest, ExperimentResult
from backend.pipeline.experiment.runner import ExperimentRunner

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post(
    "/run",
    summary="Run experiment in sandbox",
    description="Execute code in a sandboxed environment after security validation.",
)
async def run_experiment(request: ExperimentRequest) -> ExperimentResult:
    """Run experiment code in sandbox.

    Args:
        request: Experiment request with code, inputs, timeout, and language.

    Returns:
        ExperimentResult with execution details.

    Raises:
        403: If experiment execution is disabled.
        413: If code exceeds max size.
        400: If security validation fails.
    """
    settings = get_settings()

    # Check if experiments are enabled
    if not settings.experiment_enabled:
        raise ForbiddenError(
            detail="Experiment execution is disabled",
            hint="Enable experiments by setting EROCK_EXPERIMENT_ENABLED=true",
        )

    # Check code size
    if len(request.code) > settings.experiment_max_code_size:
        from fastapi import status
        raise BadRequestError(
            detail=f"Code exceeds maximum size of {settings.experiment_max_code_size} characters",
            hint="Reduce code size or increase EROCK_EXPERIMENT_MAX_CODE_SIZE",
        )

    # Run experiment
    runner = ExperimentRunner()
    result = await runner.run(request)

    # Return 400 if security validation failed
    if not result.success and result.error and "Security validation" in result.error:
        raise BadRequestError(
            detail=result.stderr,
            hint="Remove dangerous patterns from your code",
        )

    return result
