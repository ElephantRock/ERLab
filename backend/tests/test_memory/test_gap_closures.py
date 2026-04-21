"""Tests for WP-3 memory gap closures: prior gaps recall, quality gate,
semantic recall, auto-promotion, deletion, and decay trigger."""

import asyncio
import sys
import tempfile
from datetime import datetime, timedelta
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# Stub out chromadb before any backend imports that need it
_chromadb = ModuleType("chromadb")
_chromadb.PersistentClient = MagicMock
_chromadb.HttpClient = MagicMock
sys.modules.setdefault("chromadb", _chromadb)

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.models import MemoryEntry, MemoryQuery, MemoryType
from backend.pipeline.memory.service import MemoryService


def _make_entry(
    content="test memory content for recall",
    memory_type=MemoryType.SEMANTIC,
    namespace="research_facts",
    access_count=0,
    confidence=0.9,
):
    return MemoryEntry(
        id="placeholder",
        content=content,
        memory_type=memory_type,
        namespace=namespace,
        truth=TruthValue(confidence=confidence, frequency=1.0),
        created_at=datetime.now(),
        access_count=access_count,
    )


async def _store(svc, **kwargs):
    """Store an entry and return the actual ID assigned by the service."""
    entry = _make_entry(**kwargs)
    return await svc.store(entry)


class TestRecallPriorGaps:
    """Gap 3a: _recall_prior_gaps should return actual results, not None."""

    def test_returns_results_when_memory_has_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            asyncio.run(_store(svc, content="NLP research gaps in evaluation metrics"))

            results = asyncio.run(
                svc.recall(
                    MemoryQuery(
                        query="NLP research gaps",
                        memory_type=MemoryType.SEMANTIC,
                        namespace="research_facts",
                        top_k=20,
                    )
                )
            )
            assert len(results) > 0
            assert "NLP" in results[0].content

    def test_returns_none_when_no_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            results = asyncio.run(
                svc.recall(
                    MemoryQuery(
                        query="nonexistent topic",
                        memory_type=MemoryType.SEMANTIC,
                        namespace="research_facts",
                        top_k=20,
                    )
                )
            )
            assert results == []


class TestQualityGateFailClosed:
    """Gap 3b: Quality gate should reject on exception (fail-closed)."""

    def test_quality_gate_rejects_on_exception(self):
        from backend.pipeline.memory.extraction import _quality_gate

        failing_provider = MagicMock()
        failing_provider.structured_output = AsyncMock(side_effect=RuntimeError("API down"))

        result = asyncio.run(_quality_gate("some fact content", failing_provider))
        assert result is False

    def test_quality_gate_passes_valid_fact(self):
        from backend.pipeline.memory.extraction import _quality_gate

        provider = MagicMock()
        provider.structured_output = AsyncMock(return_value={"is_valid": True, "reason": "good"})

        result = asyncio.run(_quality_gate("well-formed fact", provider))
        assert result is True

    def test_quality_gate_rejects_invalid_fact(self):
        from backend.pipeline.memory.extraction import _quality_gate

        provider = MagicMock()
        provider.structured_output = AsyncMock(return_value={"is_valid": False, "reason": "vague"})

        result = asyncio.run(_quality_gate("vague claim", provider))
        assert result is False


class TestAutoPromotion:
    """Gap 3d: Frequently accessed archival entries auto-promote to working tier."""

    def test_auto_promotion_on_high_access_count(self):
        from backend.pipeline.memory.tiers import TieredMemoryService

        with tempfile.TemporaryDirectory() as tmp:
            tiers = TieredMemoryService(
                working_capacity=50,
                archival_path=tmp,
                retriever=None,
            )

            # Store to archival via tiers
            entry = _make_entry(content="frequently accessed entry about transformers")
            entry_id = asyncio.run(tiers.store(entry, tier=tiers._archival))

            # Bump access count in archival index
            tiers._archival._index[entry_id].access_count = 3

            results = asyncio.run(
                tiers.recall(
                    MemoryQuery(query="transformers", top_k=10)
                )
            )
            assert len(results) > 0
            # The entry should have been promoted to working tier
            assert entry_id in tiers._working


class TestMemoryDeletion:
    """Gap 3e: MemoryService.delete() removes entries."""

    def test_delete_existing_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            entry_id = asyncio.run(_store(svc, content="entry to be deleted"))

            assert entry_id in svc._index
            deleted = asyncio.run(svc.delete(entry_id))
            assert deleted is True
            assert entry_id not in svc._index

    def test_delete_nonexistent_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            deleted = asyncio.run(svc.delete("nonexistent_id"))
            assert deleted is False

    def test_delete_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            entry_id = asyncio.run(_store(svc, content="entry to delete and verify"))

            # Delete
            asyncio.run(svc.delete(entry_id))

            # Reload from disk — entry should be gone
            svc2 = MemoryService(persist_path=tmp)
            assert entry_id not in svc2._index


class TestDecayTrigger:
    """Gap 3f: maybe_decay only fires after min_interval_hours."""

    def test_decay_skipped_within_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            asyncio.run(_store(svc, content="decay test entry", confidence=0.9))

            # _last_decay is set to datetime.now() in constructor, so decay should be skipped
            count = asyncio.run(svc.maybe_decay(min_interval_hours=24))
            assert count == 0

    def test_decay_fires_after_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            entry_id = asyncio.run(_store(svc, content="decay test entry", confidence=0.9))

            # Backdate _last_decay to trigger decay
            svc._last_decay = datetime.now() - timedelta(hours=48)
            count = asyncio.run(svc.maybe_decay(decay_rate=0.9, min_interval_hours=24))
            assert count > 0
            # Confidence should have decreased
            assert svc._index[entry_id].truth.confidence < 0.9

    def test_recall_triggers_decay_when_interval_elapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = MemoryService(persist_path=tmp)
            entry_id = asyncio.run(_store(svc, content="recall decay trigger", confidence=0.95))

            # Backdate so recall triggers decay
            svc._last_decay = datetime.now() - timedelta(hours=30)

            asyncio.run(
                svc.recall(MemoryQuery(query="recall decay", top_k=10))
            )
            # Decay should have been applied via maybe_decay in recall
            assert svc._last_decay > datetime.now() - timedelta(seconds=5)
