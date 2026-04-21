"""API request/response schemas with validation constraints."""

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    domain: str = Field(default="AI/NLP", max_length=200)
    max_gaps: int = Field(default=5, ge=1, le=20)
    generation_rounds: int | None = Field(default=None, ge=1, le=10)
    ideas_per_round: int | None = Field(default=None, ge=1, le=20)
    search_queries: list[str] | None = Field(default=None)
    run_novelty: bool = Field(default=True)
    run_feasibility: bool = Field(default=True)
    run_synthesis: bool = Field(default=True)
    export_format: str = Field(default="markdown")


class SearchRequest(BaseModel):
    query: str = Field(max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)


class IdeaFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class AutonomousCycleRequest(BaseModel):
    domain: str = Field(default="AI/NLP", max_length=200)
    max_runs: int = Field(default=3, ge=1, le=20)
