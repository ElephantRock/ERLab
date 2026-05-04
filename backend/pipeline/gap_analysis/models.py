"""Data models for gap analysis."""

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class ClusterInfo(BaseModel):
    cluster_id: int
    label: str = ""
    paper_count: int = 0
    top_terms: list[str] = Field(default_factory=list)
    avg_citations: float | None = None


class ClusterReport(BaseModel):
    clusters: list[ClusterInfo] = Field(default_factory=list)
    total_papers: int = 0
    silhouette_score: float | None = None
    davies_bouldin_index: float | None = None


class ResearchGap(BaseModel):
    title: str
    description: str
    gap_type: str = ""  # methodological, empirical, theoretical, cross-domain
    related_clusters: list[int] = Field(default_factory=list)
    potential_impact: str = ""
    confidence: float = 0.5
    truth: TruthValue = Field(default_factory=TruthValue.initial)
