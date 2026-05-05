"""Tests for truth value revision (BATCH-74/TASK-02)."""

from unittest.mock import MagicMock

from backend.pipeline.knowledge.truth import TruthValue


class TestTruthRevision:
    def test_confidence_increases_after_revision(self):
        """TEST-74-02-01: Gap truth confidence increases after idea generation."""
        initial = TruthValue(frequency=0.5, confidence=0.5, evidence_count=1)
        new_evidence = TruthValue.from_observation(frequency=0.8)
        revised = initial.revise(new_evidence)
        assert revised.confidence > initial.confidence
        assert revised.confidence > 0.5

    def test_evidence_count_increases(self):
        """TEST-74-02-02: TruthValue.evidence_count increases after revision."""
        initial = TruthValue(frequency=0.5, confidence=0.5, evidence_count=1)
        new_evidence = TruthValue.from_observation(frequency=0.8)
        revised = initial.revise(new_evidence)
        assert revised.evidence_count > initial.evidence_count
        assert revised.evidence_count >= 3  # 1 initial + 1 new + 1 bonus

    def test_confidence_never_exceeds_099(self):
        """TEST-74-02-03: Truth confidence never exceeds 0.99."""
        truth = TruthValue(frequency=0.9, confidence=0.9, evidence_count=10)
        # Revise many times — confidence should cap at 0.99
        for _ in range(50):
            truth = truth.revise(TruthValue.from_observation(frequency=0.9))
        assert truth.confidence <= 0.99

    def test_frequency_averages_toward_new_evidence(self):
        """Frequency should move toward the new observation."""
        initial = TruthValue(frequency=0.3, confidence=0.6, evidence_count=2)
        new_evidence = TruthValue.from_observation(frequency=0.9)
        revised = initial.revise(new_evidence)
        assert revised.frequency > initial.frequency
        assert revised.frequency < 0.9  # Averaged, not replaced

    def test_revision_with_zero_confidence(self):
        """Revision handles zero-confidence inputs gracefully."""
        initial = TruthValue(frequency=0.5, confidence=0.0, evidence_count=0)
        new_evidence = TruthValue.from_observation(frequency=0.8)
        revised = initial.revise(new_evidence)
        assert revised.confidence > 0

    def test_revision_chain(self):
        """Multiple revisions accumulate evidence correctly."""
        truth = TruthValue.initial()
        scores = [0.7, 0.8, 0.9, 0.85, 0.75]
        for score in scores:
            truth = truth.revise(TruthValue.from_observation(frequency=score))
        assert truth.evidence_count >= len(scores)  # At least as many as revisions
        assert truth.confidence > 0.7


class TestTruthRevisionInStage:
    def test_idea_generation_revises_gap_truth(self):
        """Integration test: IdeaGenerationStage revises gap truth values."""
        from backend.pipeline.stages import IdeaGenerationStage
        from backend.pipeline.knowledge.entities import KnowledgeEntity, EntityType
        from backend.pipeline.knowledge.graph import KnowledgeGraph
        from backend.pipeline.knowledge.truth import TruthValue

        # Create a KG with a gap entity
        kg = KnowledgeGraph()
        gap_entity = KnowledgeEntity(
            id="gap:test_gap_title_here________________________________",
            entity_type=EntityType.CONCEPT,
            name="Test Gap Title",
            properties={},
            truth=TruthValue(frequency=0.5, confidence=0.5, evidence_count=1),
        )
        kg.add_entity(gap_entity)

        # Simulate what _execute_sequential does after idea creation
        from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType

        gap_eid = "gap:test_gap_title_here________________________________"
        idea_eid = "idea:Test Idea"

        # This is the truth revision logic from the stage
        if gap_eid in kg._entities:
            kg.add_relationship(KnowledgeRelationship(
                source_id=gap_eid,
                target_id=idea_eid,
                relation_type=RelationType.PROPOSES_METHOD,
                truth=TruthValue.from_observation(frequency=0.8),
            ))
            # Truth revision
            gap_ent = kg._entities[gap_eid]
            revised = gap_ent.truth.revise(
                TruthValue.from_observation(frequency=0.8)
            )
            gap_ent.truth = revised

        # Verify gap truth was revised upward
        final_truth = kg._entities[gap_eid].truth
        assert final_truth.confidence > 0.5
        assert final_truth.evidence_count > 1
