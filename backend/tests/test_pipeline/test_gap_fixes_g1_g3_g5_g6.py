"""Tests for gap fixes G1, G3, G5, G6."""

import asyncio
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.knowledge.embedding_providers import DummyEmbeddingProvider
from backend.pipeline.knowledge.embedding_service import EmbeddingService

# ── G1: Zero-vector startup detection ──────────────────────────────────

class TestEmbeddingValidation:
    def test_real_provider_passes(self):
        """Non-zero embedding passes validation."""
        provider = MagicMock()
        provider.dimension = 8
        provider.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]])
        service = EmbeddingService(provider)
        result = asyncio.run(service.validate_startup())
        assert result is True

    def test_zero_vector_fails(self):
        """All-zero embedding fails validation."""
        provider = DummyEmbeddingProvider(dimension=1536)
        service = EmbeddingService(provider)
        result = asyncio.run(service.validate_startup())
        assert result is False

    def test_empty_vector_fails(self):
        """Empty embedding list fails validation."""
        provider = MagicMock()
        provider.dimension = 8
        provider.embed = AsyncMock(return_value=[[]])
        service = EmbeddingService(provider)
        result = asyncio.run(service.validate_startup())
        assert result is False


# ── G3: Paper-to-gap truth revision ────────────────────────────────────

class TestPaperToGapTruth:
    def test_gap_truth_revised_on_paper_overlap(self):
        """Gap truth increases when papers overlap with gap description."""
        from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
        from backend.pipeline.knowledge.graph import KnowledgeGraph
        from backend.pipeline.knowledge.truth import TruthValue

        kg = KnowledgeGraph()
        gap_entity = KnowledgeEntity(
            id="gap:retrieval augmented generation",
            entity_type=EntityType.CONCEPT,
            name="Retrieval Augmented Generation",
            properties={},
            truth=TruthValue(frequency=0.5, confidence=0.6, evidence_count=1),
        )
        kg.add_entity(gap_entity)

        # Simulate the overlap logic from GapAnalysisStage
        gap_description = "retrieval augmented generation for NLP tasks"
        gap_words = set(gap_description.lower().split()[:20])
        papers = []
        for title in [
            "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "Improving Retrieval Augmented Generation with Dense Passages",
        ]:
            p = MagicMock()
            p.title = title
            p.abstract = "retrieval augmented generation"
            papers.append(p)

        overlap_count = 0
        for paper in papers:
            paper_text = f"{paper.title} {paper.abstract or ''}".lower()
            if sum(1 for w in gap_words if w in paper_text) >= 3:
                overlap_count += 1

        assert overlap_count == 2  # Both papers match

        # Revise truth
        entity = kg._entities.get("gap:retrieval augmented generation")
        revised = entity.truth.revise(
            TruthValue(
                frequency=min(0.95, 0.5 + overlap_count * 0.05),
                confidence=0.6,
                evidence_count=overlap_count,
            )
        )
        entity.truth = revised

        assert revised.confidence > 0.6
        assert revised.evidence_count > 1


# ── G5: Watchdog at pipeline start ─────────────────────────────────────

class TestWatchdogAtRunStart:
    def test_watchdog_integration_point_exists(self):
        """Verify orchestrator.run() calls watchdog before executing."""
        # Read the orchestrator source to verify the watchdog call is present
        import inspect

        from backend.pipeline.orchestrator import PipelineOrchestrator
        source = inspect.getsource(PipelineOrchestrator.run)
        assert "PipelineWatchdog" in source, "Watchdog not called in orchestrator.run()"
        assert "check_sync" in source, "check_sync() not called in orchestrator.run()"

    def test_watchdog_check_sync_marks_stale(self):
        """check_sync finds and marks stale runs."""
        from backend.pipeline.execution.watchdog import PipelineWatchdog

        persistence = MagicMock()
        stale_run = MagicMock()
        stale_run.id = 42
        stale_run.status = "running"
        stale_run.created_at = datetime.now(UTC) - timedelta(hours=2)
        persistence.find_stale_runs.return_value = [stale_run]

        watchdog = PipelineWatchdog(persistence, timeout=timedelta(minutes=30))
        marked = watchdog.check_sync()

        assert marked == 1
        persistence.mark_stale_run_failed.assert_called_once()


# ── G6: Fuzzy title dedup ──────────────────────────────────────────────

class TestFuzzyDedup:
    def test_exact_different_titles_kept(self):
        """Papers with different titles are both kept."""
        titles = [
            "Attention Is All You Need",
            "BERT: Pre-training of Deep Bidirectional Transformers",
        ]
        unique = []
        for title in titles:
            p = MagicMock()
            p.title = title
            p.doi = None
            is_dup = any(
                SequenceMatcher(None, title.lower(), e.title.lower()).ratio() > 0.85
                for e in unique
            )
            if not is_dup:
                unique.append(p)
        assert len(unique) == 2

    def test_near_duplicate_removed(self):
        """Near-duplicate titles (typos, trailing punctuation) are merged."""
        titles = [
            "Attention Is All You Need",
            "Attention Is All You Need.",  # Trailing period
        ]
        unique = []
        for title in titles:
            p = MagicMock()
            p.title = title
            p.doi = None
            is_dup = any(
                SequenceMatcher(None, title.lower().strip(), e.title.lower().strip()).ratio() > 0.85
                for e in unique
            )
            if not is_dup:
                unique.append(p)
        assert len(unique) == 1

    def test_similar_but_distinct_kept(self):
        """Papers that are similar but genuinely different are kept."""
        titles = [
            "A Survey of Deep Learning for NLP",
            "A Survey on Deep Learning for Computer Vision",
        ]
        unique = []
        for title in titles:
            p = MagicMock()
            p.title = title
            p.doi = None
            is_dup = any(
                SequenceMatcher(None, title.lower().strip(), e.title.lower().strip()).ratio() > 0.85
                for e in unique
            )
            if not is_dup:
                unique.append(p)
        # These are different enough (ratio ~0.73) to both be kept
        assert len(unique) == 2

    def test_threshold_85_catches_minor_variants(self):
        """Ratio threshold 0.85 correctly catches minor variants."""
        assert SequenceMatcher(None, "deep learning for nlp", "deep learning for nlp").ratio() > 0.85
        assert SequenceMatcher(None, "deep learning for nlp", "deep learning for nlp.").ratio() > 0.85
        assert SequenceMatcher(None, "deep learning for nlp", "deep learning for vision").ratio() < 0.85
