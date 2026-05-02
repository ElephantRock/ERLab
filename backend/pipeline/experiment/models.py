"""Experiment execution models (BATCH-49)."""

from pydantic import BaseModel


class ExperimentResult(BaseModel):
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    artifacts: dict[str, str] = {}
    metrics: dict[str, float] = {}
    execution_time_seconds: float
    error: str | None = None


class ExperimentRequest(BaseModel):
    code: str
    inputs: dict = {}
    timeout: int | None = None
    language: str = "python"
