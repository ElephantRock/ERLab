"""Data models for idea generation."""

from pydantic import BaseModel, Field


class IdeaCandidate(BaseModel):
    """A raw research idea from the IdeatorAgent."""
    title: str
    problem_statement: str
    proposed_method: str
    expected_contributions: str = ""
    novelty_rationale: str = ""
    evaluation_approach: str = ""


class Critique(BaseModel):
    """Feedback from the CriticAgent on an idea."""
    idea_title: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    prior_art_concerns: list[str] = Field(default_factory=list)
    feasibility_concerns: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    overall_assessment: str = ""


class ResearchIdea(BaseModel):
    """A refined research idea ready for novelty/feasibility evaluation."""
    title: str
    problem_statement: str
    proposed_method: str
    expected_contributions: str
    novelty_rationale: str
    evaluation_approach: str
    domain: str = "AI/NLP"
    round_generated: int = 1
    score: float = 0.0
    supporting_papers: list[str] = Field(default_factory=list)  # paper IDs
