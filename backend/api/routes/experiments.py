"""Sandboxed experiment execution API routes (BATCH-49, BATCH-66)."""

import logging

from fastapi import APIRouter
from sqlalchemy import select

from backend.api.errors import BadRequestError, ForbiddenError
from backend.config import get_settings
from backend.db.database import get_session
from backend.db.models import ExperimentResult as ExperimentResultDB
from backend.db.models import Idea
from backend.pipeline.experiment.models import ExperimentRequest, ExperimentResult
from backend.pipeline.experiment.runner import ExperimentRunner
from backend.pipeline.experiment.experiment_generator import ExperimentGenerator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/specs",
    summary="List registered experiment specifications",
    description="Return the checked-in empirical specifications available for pipeline runs.",
)
async def list_experiment_specs() -> dict:
    """Return selectable registered experiment specs and compatible strategies."""
    from backend.pipeline.experiment.specification import list_specs
    from backend.pipeline.monitoring.cost_estimator import STRATEGY_STAGES

    specs = list_specs()
    compatible_strategies = sorted(
        strategy
        for strategy, stages in STRATEGY_STAGES.items()
        if "experiment_execution" in stages
    )
    return {
        "specs": [
            {
                "spec_id": spec.spec_id,
                "description": spec.description,
                "research_question": spec.research_question,
                "dataset_name": spec.dataset_name,
                "analysis_method": spec.analysis_method,
                "primary_metric": spec.primary_metric,
            }
            for spec in specs
        ],
        "compatible_strategies": compatible_strategies,
    }


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


@router.post(
    "/ideas/{idea_id}/run-experiment",
    summary="Generate and run experiment for an idea (BATCH-66)",
)
async def run_idea_experiment(idea_id: int) -> dict:
    """Generate experiment code from an idea, validate, execute, and store results."""
    settings = get_settings()
    if not settings.experiment_enabled:
        raise ForbiddenError(
            detail="Experiment execution is disabled",
            hint="Enable by setting EROCK_EXPERIMENT_ENABLED=true",
        )

    with get_session() as session:
        idea = session.get(Idea, idea_id)
        if not idea:
            raise BadRequestError(detail=f"Idea {idea_id} not found")

    # Generate experiment code
    from backend.pipeline.generation.models import IdeaCandidate
    candidate = IdeaCandidate(
        title=idea.title,
        problem_statement=idea.problem_statement,
        proposed_method=idea.proposed_method,
        expected_contributions=idea.expected_contributions,
        evaluation_approach="",
    )
    generator = ExperimentGenerator()
    code = await generator.generate(candidate)

    # Run via existing sandbox
    runner = ExperimentRunner()
    request = ExperimentRequest(code=code, language="python", timeout=30)
    result = await runner.run(request)

    # Store result in DB
    with get_session() as session:
        db_result = ExperimentResultDB(
            idea_id=idea_id,
            code_md=code,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.exit_code,
            success=result.success,
            execution_time_seconds=result.execution_time_seconds,
            error=result.error,
        )
        session.add(db_result)
        session.commit()
        result_id = db_result.id

    return {
        "id": result_id,
        "idea_id": idea_id,
        "success": result.success,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:500],
        "exit_code": result.exit_code,
        "execution_time_seconds": result.execution_time_seconds,
        "error": result.error,
    }
