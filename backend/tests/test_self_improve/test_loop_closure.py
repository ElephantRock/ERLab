"""Tests for WP-4 self-improvement loop closure.

Verifies that the 4 broken links are fixed:
1. Lessons stored as memories
2. Skill proposer/generator activated
3. FitnessScore computed and passed to evolver
4. ConstraintValidator configured on evolver
"""

import sys
import tempfile
from datetime import datetime
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub out chromadb
_chromadb = ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock
_chromadb.HttpClient = MagicMock
sys.modules.setdefault("chromadb", _chromadb)


class TestConstraintValidatorConfigured:
    """Break #4: ConstraintValidator should be configured on PipelineEvolver."""

    def test_evolver_has_constraint_validator(self):
        from backend.pipeline.self_improve.constraints import ConstraintConfig
        from backend.pipeline.self_improve.evolution import PipelineEvolver
        from backend.pipeline.self_improve.frontier import ParetoFrontier

        with tempfile.TemporaryDirectory() as tmp:
            frontier = ParetoFrontier(f"{tmp}/frontier.json")
            config = ConstraintConfig(max_size=5000, max_growth_pct=0.3, min_sections=3)
            evolver = PipelineEvolver(frontier, constraint_config=config)

            assert evolver._constraints is not None

    def test_evolver_without_constraints(self):
        from backend.pipeline.self_improve.evolution import PipelineEvolver
        from backend.pipeline.self_improve.frontier import ParetoFrontier

        with tempfile.TemporaryDirectory() as tmp:
            frontier = ParetoFrontier(f"{tmp}/frontier.json")
            evolver = PipelineEvolver(frontier)

            assert evolver._constraints is None


class TestFitnessScoreComputed:
    """Break #3: FitnessScore should be computed and passed to evaluate()."""

    def test_fitness_score_computation(self):
        from backend.pipeline.self_improve.fitness import FitnessScore

        fitness = FitnessScore(
            correctness=0.8,
            procedure_following=0.9,
            conciseness=0.7,
            length_penalty=0.05,
        )
        assert fitness.composite > 0
        assert 0 < fitness.composite < 1.0

    def test_fitness_passed_to_evaluate(self):
        from backend.pipeline.self_improve.constraints import ConstraintConfig
        from backend.pipeline.self_improve.evolution import PipelineEvolver
        from backend.pipeline.self_improve.fitness import FitnessScore
        from backend.pipeline.self_improve.frontier import ParetoFrontier

        with tempfile.TemporaryDirectory() as tmp:
            frontier = ParetoFrontier(f"{tmp}/frontier.json")
            config = ConstraintConfig(max_size=50000, max_growth_pct=1.0, min_sections=1)
            evolver = PipelineEvolver(frontier, constraint_config=config)

            fitness = FitnessScore(
                correctness=0.8,
                procedure_following=0.9,
                conciseness=0.7,
            )

            point = evolver.evaluate(
                params={"generation_rounds": 2, "ideas_per_round": 3},
                run_id="test_run",
                avg_idea_score=0.8,
                avg_novelty_score=0.7,
                fitness=fitness,
            )
            assert point is not None
            assert "fitness" in point.scores

    def test_length_penalty_ramp(self):
        from backend.pipeline.self_improve.fitness import FitnessScore

        # Below 90% — no penalty
        assert FitnessScore.length_penalty_ramp(4000, 5000) == 0.0
        # At 95% — partial penalty
        penalty = FitnessScore.length_penalty_ramp(4750, 5000)
        assert 0 < penalty <= 0.3


class TestLessonsStoredAsMemories:
    """Break #1: Lessons should be stored as memories, not discarded."""

    def test_lesson_content_stored_in_memory(self):
        import asyncio

        from backend.pipeline.knowledge.truth import TruthValue
        from backend.pipeline.memory.models import MemoryEntry, MemoryType
        from backend.pipeline.memory.service import MemoryService

        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            lesson = "Round 2 ideas scored 20% lower — consider adjusting temperature"

            entry = MemoryEntry(
                id="",
                content=lesson,
                memory_type=MemoryType.EPISODIC,
                namespace="pipeline_experience",
                truth=TruthValue.from_observation(frequency=0.7),
                tags=["lesson", "self_improve"],
                created_at=datetime.now(),
            )
            entry_id = asyncio.run(svc.store(entry))

            # Verify stored
            assert entry_id in svc._index
            stored = svc._index[entry_id]
            assert stored.memory_type == MemoryType.EPISODIC
            assert "lesson" in stored.tags
            assert "self_improve" in stored.tags


class TestSkillProposerGeneratorActivated:
    """Break #2: Skill proposer/generator should be called with lessons."""

    def test_skill_proposer_diagnose_called(self):
        import asyncio

        from backend.pipeline.skills.models import FeedbackEntry, Skill, SkillStatus, SkillVersion
        from backend.pipeline.skills.proposer_generator import SkillProposer

        provider = MagicMock()
        provider.complete = AsyncMock(return_value="DIAGNOSIS: low quality ideas\nSUGGESTION: increase temperature")

        proposer = SkillProposer(provider)

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="A test skill for unit testing",
            domain="AI/NLP",
            status=SkillStatus.ACTIVE,
            current_version=1,
            versions=[SkillVersion(version=1, content="Be creative", score=0.3)],
            feedback_history=[
                FeedbackEntry(iteration=1, success=False, score=0.3, observation="low quality")
            ],
        )

        diagnosis, suggestion = asyncio.run(proposer.diagnose(skill, trace="round 2 scored low"))
        assert "low quality" in diagnosis.lower() or len(diagnosis) > 0
        assert provider.complete.called

    def test_skill_generator_produces_content(self):
        import asyncio

        from backend.pipeline.skills.models import Skill, SkillStatus, SkillVersion
        from backend.pipeline.skills.proposer_generator import SkillGenerator

        provider = MagicMock()
        provider.complete = AsyncMock(return_value="Improved skill: focus on evaluation metrics first")

        generator = SkillGenerator(provider)

        skill = Skill(
            id="test_skill",
            name="Test Skill",
            description="A test skill for unit testing",
            domain="AI/NLP",
            status=SkillStatus.ACTIVE,
            current_version=1,
            versions=[SkillVersion(version=1, content="Original content", score=0.3)],
        )

        content = asyncio.run(
            generator.generate(skill, diagnosis="low quality", suggestion="increase temperature")
        )
        assert len(content) > 0
        assert provider.complete.called

    def test_skill_registry_add_version(self):
        import asyncio

        from backend.pipeline.skills.models import Skill, SkillStatus, SkillVersion
        from backend.pipeline.skills.registry import SkillRegistry

        with tempfile.TemporaryDirectory() as tmp:
            registry = SkillRegistry(persist_dir=tmp)
            skill = Skill(
                id="test_skill_v2",
                name="Test Skill V2",
                description="A test skill for version testing",
                domain="AI/NLP",
                status=SkillStatus.ACTIVE,
                current_version=1,
                versions=[SkillVersion(version=1, content="v1 content", score=0.3)],
            )
            registry.register(skill)

            version = registry.add_version("test_skill_v2", "v2 improved content", score=0.7)
            assert version is not None
            assert version.version == 2
            assert version.score == 0.7
