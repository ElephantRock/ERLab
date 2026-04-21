"""Tests for skill lifecycle models and registry."""

import tempfile

from backend.pipeline.skills.models import FeedbackEntry, Skill, SkillStatus


class TestSkillModels:
    def test_create_skill(self):
        skill = Skill(
            id="s1",
            name="gap_analyzer",
            description="Analyzes research gaps",
            domain="gap_analysis",
        )
        assert skill.current_version == 0
        assert skill.status == SkillStatus.DRAFT
        assert skill.get_current() is None

    def test_add_version(self):
        skill = Skill(id="s1", name="test", description="Test skill", domain="test")
        v1 = skill.add_version("Initial skill content", score=0.5)
        assert skill.current_version == 1
        assert v1.version == 1
        assert v1.score == 0.5

        v2 = skill.add_version("Improved content", score=0.8)
        assert skill.current_version == 2
        assert v2.parent_version == 1

        current = skill.get_current()
        assert current is not None
        assert current.version == 2
        assert current.content == "Improved content"

    def test_feedback_tracking(self):
        skill = Skill(id="s1", name="test", description="Test skill", domain="test")
        skill.add_version("v1 content")

        skill.add_feedback(
            FeedbackEntry(
                iteration=1,
                success=False,
                score=0.3,
                observation="Generated generic ideas",
                diagnosis="Prompt too broad",
                suggestion="Add domain-specific constraints",
            )
        )
        assert len(skill.feedback_history) == 1
        assert skill.feedback_history[0].success is False

    def test_version_lineage(self):
        skill = Skill(id="s1", name="test", description="Test skill", domain="test")
        v1 = skill.add_version("v1")
        v2 = skill.add_version("v2")
        v3 = skill.add_version("v3")

        assert v1.parent_version is None
        assert v2.parent_version == 1
        assert v3.parent_version == 2


class TestSkillRegistry:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        from backend.pipeline.skills.registry import SkillRegistry

        self.registry = SkillRegistry(persist_dir=self._tmpdir)

    def test_register_and_get(self):
        skill = Skill(
            id="skill_1", name="ideator", description="Generates ideas", domain="generation"
        )
        self.registry.register(skill)

        retrieved = self.registry.get("skill_1")
        assert retrieved is not None
        assert retrieved.name == "ideator"

    def test_discover_by_domain(self):
        self.registry.register(Skill(id="s1", name="ideator", description="", domain="generation"))
        self.registry.register(
            Skill(id="s2", name="gap_finder", description="", domain="gap_analysis")
        )
        self.registry.register(Skill(id="s3", name="critic", description="", domain="generation"))

        # Activate skills
        for sid in ["s1", "s2", "s3"]:
            self.registry.activate(sid)

        results = self.registry.discover(domain="generation")
        assert len(results) == 2

    def test_add_version(self):
        self.registry.register(Skill(id="s1", name="test", description="", domain="test"))
        version = self.registry.add_version("s1", "New version content", score=0.7)
        assert version is not None
        assert version.version == 1

        skill = self.registry.get("s1")
        assert skill.current_version == 1

    def test_record_feedback(self):
        self.registry.register(Skill(id="s1", name="test", description="", domain="test"))
        self.registry.record_feedback(
            "s1",
            FeedbackEntry(
                iteration=1,
                success=True,
                score=0.8,
                observation="Worked well",
            ),
        )
        skill = self.registry.get("s1")
        assert len(skill.feedback_history) == 1

    def test_deactivate(self):
        self.registry.register(Skill(id="s1", name="test", description="", domain="test"))
        self.registry.activate("s1")
        assert self.registry.get("s1").status == SkillStatus.ACTIVE

        self.registry.deactivate("s1")
        assert self.registry.get("s1").status == SkillStatus.DEPRECATED

        # Deprecated skills not returned by discover
        results = self.registry.discover(domain="test")
        assert len(results) == 0

    def test_persistence(self):
        skill = Skill(id="s1", name="persistent", description="Persists", domain="test")
        skill.add_version("v1 content")
        self.registry.register(skill)

        # Load fresh registry from same dir
        from backend.pipeline.skills.registry import SkillRegistry

        registry2 = SkillRegistry(persist_dir=self._tmpdir)
        retrieved = registry2.get("s1")
        assert retrieved is not None
        assert retrieved.name == "persistent"
        assert retrieved.current_version == 1
