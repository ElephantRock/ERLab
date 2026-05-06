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
    session_id: str | None = None
    strategy: str = Field(default="deep_research", pattern="^(fast_scan|deep_research|academic_proposal|literature_review)$")


class SearchRequest(BaseModel):
    query: str = Field(max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)


class IdeaFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)


class AutonomousCycleRequest(BaseModel):
    domain: str = Field(default="AI/NLP", max_length=200)
    max_runs: int = Field(default=3, ge=1, le=20)


class SessionCreateRequest(BaseModel):
    name: str = Field(default="", max_length=200)
    max_runs: int = Field(default=10, ge=1, le=1000)
    max_cost_usd: float = Field(default=50.0, ge=0.0)
    max_tokens: int = Field(default=5_000_000, ge=0)
    max_duration_hours: float = Field(default=24.0, ge=0.1)
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class ExportPdfRequest(BaseModel):
    """Request to export a single idea as PDF."""
    idea_id: int = Field(ge=1)


class BulkExportRequest(BaseModel):
    """Request to bulk export ideas as ZIP."""
    idea_ids: list[int] = Field(min_length=1, max_length=500)
    format: str = Field(default="markdown", pattern="^(pdf|markdown)$")


class PluginInstallRequest(BaseModel):
    """Request to install/register a plugin."""
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(default="0.1.0", max_length=20)
    description: str = Field(default="", max_length=500)
