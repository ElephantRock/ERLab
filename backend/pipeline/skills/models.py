"""Skill lifecycle models — skills as first-class evolvable artifacts.

Skills are discrete, discoverable capabilities that can be created, versioned,
and improved over time. Stored as directory-per-skill with metadata.

Reference: EvoSkill four-agent pipeline with .claude/skills/ directory model.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SkillStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    FAILED = "failed"


class SkillVersion(BaseModel):
    """A specific version of a skill."""

    version: int
    content: str  # The skill instructions/prompt
    created_at: datetime = Field(default_factory=datetime.now)
    score: float = 0.0  # Quality score from evaluation
    parent_version: int | None = None  # Lineage tracking
    feedback_summary: str | None = None


class FeedbackEntry(BaseModel):
    """Single feedback item for a skill version."""

    iteration: int
    success: bool
    score: float
    observation: str  # What happened
    diagnosis: str | None = None  # Why it happened (from proposer)
    suggestion: str | None = None  # How to fix (from generator)
    created_at: datetime = Field(default_factory=datetime.now)


class Skill(BaseModel):
    """A discoverable, versioned skill artifact."""

    id: str
    name: str
    description: str
    domain: str  # "generation", "critique", "retrieval", etc.
    status: SkillStatus = SkillStatus.DRAFT
    current_version: int = 0
    versions: list[SkillVersion] = Field(default_factory=list)
    feedback_history: list[FeedbackEntry] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_current(self) -> SkillVersion | None:
        """Return the current active version."""
        for v in reversed(self.versions):
            if v.version == self.current_version:
                return v
        return None

    def add_version(self, content: str, score: float = 0.0) -> SkillVersion:
        """Add a new version, incrementing the version counter."""
        self.current_version += 1
        version = SkillVersion(
            version=self.current_version,
            content=content,
            score=score,
            parent_version=self.current_version - 1 if self.current_version > 1 else None,
        )
        self.versions.append(version)
        self.updated_at = datetime.now()
        return version

    def add_feedback(self, entry: FeedbackEntry) -> None:
        """Record feedback for the current version."""
        self.feedback_history.append(entry)
        self.updated_at = datetime.now()


class SkillMarkdown:
    """Parse and generate SKILL.md format.

    Sections: description, trigger, steps, examples, constraints.
    """

    @staticmethod
    def from_markdown(text: str, skill_id: str = "", name: str = "") -> Skill:
        """Parse a SKILL.md string into a Skill object."""
        sections: dict[str, str] = {}
        current_section = ""
        current_lines: list[str] = []

        for line in text.split("\n"):
            if line.startswith("## ") and not line.startswith("### "):
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip().lower()
                current_lines = []
            else:
                current_lines.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_lines).strip()

        description = sections.get("description", "")
        if not name:
            name = sections.get("name", skill_id or "unnamed")

        import uuid
        return Skill(
            id=skill_id or uuid.uuid4().hex[:8],
            name=name,
            description=description,
            domain="",
            tags=[],
            versions=[SkillVersion(
                version=1,
                content=text,
                score=0.0,
            )],
            feedback_history=[],
        )

    @staticmethod
    def to_markdown(skill: Skill) -> str:
        """Convert a Skill object to SKILL.md format."""
        current = skill.get_current()
        content = current.content if current else ""

        # If content is already markdown, return it
        if content.startswith("# "):
            return content

        parts = [f"# {skill.name}", ""]
        parts.append("## Description")
        parts.append(skill.description)
        parts.append("")

        if current:
            parts.append("## Content")
            parts.append(f"Version {current.version} (score: {current.score:.2f})")
            parts.append(current.content)
            parts.append("")

        if skill.feedback_history:
            parts.append("## Feedback History")
            for fb in skill.feedback_history[-5:]:
                parts.append(f"- Iteration {fb.iteration}: score={fb.score:.2f} success={fb.success}")
                if fb.observation:
                    parts.append(f"  Observation: {fb.observation}")
            parts.append("")

        return "\n".join(parts)
