"""Knowledge graph relationships with Hebbian-like edge consolidation."""

from enum import Enum

from pydantic import BaseModel, Field

from backend.pipeline.knowledge.truth import TruthValue


class RelationType(str, Enum):
    CITES = "cites"
    USES_METHOD = "uses_method"
    EXTENDS = "extends"
    CONTRADICTS = "contradicts"
    BUILDS_ON = "builds_on"
    APPLIED_TO = "applied_to"
    IDENTIFIES_GAP = "identifies_gap"
    PROPOSES_METHOD = "proposes_method"


class KnowledgeRelationship(BaseModel):
    source_id: str
    target_id: str
    relation_type: RelationType
    weight: float = 1.0  # Hebbian-like reinforcement/weakening [0, 2]
    evidence: list[str] = []  # Paper IDs supporting this relationship
    truth: TruthValue = Field(default_factory=TruthValue.initial)
