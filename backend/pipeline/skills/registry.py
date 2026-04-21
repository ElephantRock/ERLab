"""Skill registry — directory-based skill discovery and lifecycle management.

Skills are stored as files under `data/skills/{skill_id}/` with:
  - metadata.json (Skill model)
  - v{N}.md (version content)
  - feedback_history.md (human-readable feedback log)

Reference: EvoSkill .claude/skills/ directory model.
"""

import logging
from pathlib import Path

from backend.pipeline.skills.models import FeedbackEntry, Skill, SkillStatus, SkillVersion

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Directory-based skill registry with discovery and lifecycle management."""

    def __init__(self, persist_dir: str = "./data/skills"):
        self._dir = Path(persist_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Skill] = {}
        self._load_all()

    def register(self, skill: Skill) -> str:
        """Register a new skill. Returns skill ID."""
        skill_dir = self._dir / skill.id
        skill_dir.mkdir(parents=True, exist_ok=True)
        self._save(skill)
        self._cache[skill.id] = skill
        logger.info("Registered skill '%s' (v%d)", skill.name, skill.current_version)
        return skill.id

    def get(self, skill_id: str) -> Skill | None:
        """Retrieve a skill by ID."""
        return self._cache.get(skill_id)

    def discover(self, domain: str | None = None, tag: str | None = None) -> list[Skill]:
        """Discover skills, optionally filtered by domain or tag."""
        results = list(self._cache.values())
        if domain:
            results = [s for s in results if s.domain == domain]
        if tag:
            results = [s for s in results if tag in s.tags]
        return [s for s in results if s.status == SkillStatus.ACTIVE]

    def add_version(self, skill_id: str, content: str, score: float = 0.0) -> SkillVersion | None:
        """Add a new version to an existing skill."""
        skill = self._cache.get(skill_id)
        if not skill:
            return None
        version = skill.add_version(content, score)
        self._save_version(skill_id, version)
        self._save(skill)
        return version

    def record_feedback(self, skill_id: str, entry: FeedbackEntry) -> None:
        """Record feedback for a skill."""
        skill = self._cache.get(skill_id)
        if not skill:
            return
        skill.add_feedback(entry)
        self._append_feedback(skill_id, entry)
        self._save(skill)

    def deactivate(self, skill_id: str) -> bool:
        """Mark a skill as deprecated."""
        skill = self._cache.get(skill_id)
        if not skill:
            return False
        skill.status = SkillStatus.DEPRECATED
        skill.updated_at = __import__("datetime").datetime.now()
        self._save(skill)
        return True

    def activate(self, skill_id: str) -> bool:
        """Mark a skill as active."""
        skill = self._cache.get(skill_id)
        if not skill:
            return False
        skill.status = SkillStatus.ACTIVE
        skill.updated_at = __import__("datetime").datetime.now()
        self._save(skill)
        return True

    @property
    def count(self) -> int:
        return len(self._cache)

    # ── Auto-discovery from pipeline behavior ──────────────────────

    def discover_from_behavior(
        self,
        pipeline_result: object,
        patterns: list[str] | None = None,
    ) -> list[Skill]:
        """Identify repeated patterns in pipeline execution that could become skills.

        Analyzes pipeline results for repeated successful patterns (e.g., a specific
        critique strategy that consistently produces high scores) and creates skill
        artifacts from them.
        """
        import uuid
        from datetime import datetime

        discovered: list[Skill] = []
        patterns = patterns or []

        # Extract patterns from pipeline result attributes
        if hasattr(pipeline_result, "ideas") and pipeline_result.ideas:
            top_ideas = sorted(pipeline_result.ideas, key=lambda i: i.score, reverse=True)[:5]
            if len(top_ideas) >= 2:
                common_domains = set()
                for idea in top_ideas:
                    if hasattr(idea, "domain") and idea.domain:
                        common_domains.add(idea.domain)

                for domain in common_domains:
                    skill_id = f"auto_{uuid.uuid4().hex[:8]}"
                    skill = Skill(
                        id=skill_id,
                        name=f"Auto-discovered: {domain} ideation",
                        description=f"Pattern observed across high-scoring ideas in {domain}",
                        domain=domain,
                        tags=["auto-discovered", domain],
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    content_parts = [f"# {skill.name}", ""]
                    content_parts.append("## Description")
                    content_parts.append(f"Auto-discovered skill from pipeline behavior in {domain}.")
                    content_parts.append("")
                    content_parts.append("## Trigger")
                    content_parts.append(f"Research domain matches: {domain}")
                    content_parts.append("")
                    content_parts.append("## Steps")
                    for i, idea in enumerate(top_ideas[:3], 1):
                        content_parts.append(f"{i}. Consider approaches like: {getattr(idea, 'proposed_method', 'N/A')[:200]}")
                    content_parts.append("")
                    skill.add_version("\n".join(content_parts))
                    discovered.append(skill)

        return discovered

    def auto_register(self, skills: list[Skill]) -> list[str]:
        """Register a list of discovered skills. Returns list of skill IDs."""
        registered_ids = []
        for skill in skills:
            # Don't register duplicates by name+domain
            existing = any(
                s.name == skill.name and s.domain == skill.domain
                for s in self._cache.values()
            )
            if not existing:
                self.register(skill)
                registered_ids.append(skill.id)
                logger.info("Auto-registered skill: %s (%s)", skill.name, skill.id)
        return registered_ids

    # ── Persistence ─────────────────────────────────────────────

    def _save(self, skill: Skill) -> None:
        skill_dir = self._dir / skill.id
        skill_dir.mkdir(parents=True, exist_ok=True)
        with open(skill_dir / "metadata.json", "w", encoding="utf-8") as f:
            f.write(skill.model_dump_json(indent=2))

    def _save_version(self, skill_id: str, version: SkillVersion) -> None:
        skill_dir = self._dir / skill_id
        with open(skill_dir / f"v{version.version}.md", "w", encoding="utf-8") as f:
            f.write(f"# Skill Version {version.version}\n\n")
            f.write(f"Score: {version.score}\n")
            f.write(f"Parent: {version.parent_version}\n\n")
            f.write(version.content)

    def _append_feedback(self, skill_id: str, entry: FeedbackEntry) -> None:
        skill_dir = self._dir / skill_id
        path = skill_dir / "feedback_history.md"
        with open(path, "a", encoding="utf-8") as f:
            status = "SUCCESS" if entry.success else "FAILED"
            f.write(f"\n## Iteration {entry.iteration} [{status}] Score: {entry.score}\n")
            f.write(f"**Observation:** {entry.observation}\n")
            if entry.diagnosis:
                f.write(f"**Diagnosis:** {entry.diagnosis}\n")
            if entry.suggestion:
                f.write(f"**Suggestion:** {entry.suggestion}\n")

    def _load_all(self) -> None:
        """Load all skills from disk."""
        if not self._dir.exists():
            return
        for skill_dir in self._dir.iterdir():
            if not skill_dir.is_dir():
                continue
            meta_path = skill_dir / "metadata.json"
            if not meta_path.exists():
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    skill = Skill.model_validate_json(f.read())
                self._cache[skill.id] = skill
            except Exception as e:
                logger.warning("Failed to load skill from %s: %s", skill_dir, e)
        logger.info("Loaded %d skills from %s", len(self._cache), self._dir)
