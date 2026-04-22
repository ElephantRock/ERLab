"""Tests for LLM-driven memory consolidation."""

import pytest

from backend.pipeline.knowledge.truth import TruthValue
from backend.pipeline.memory.consolidation import (
    ConsolidationAction,
    ConsolidationDecision,
    LLMConsolidator,
)
from backend.pipeline.memory.models import MemoryEntry, MemoryType
from backend.tests.conftest import FakeLLMProvider


def _make_entry(content: str, confidence: float = 0.8, entry_id: str = "") -> MemoryEntry:
    return MemoryEntry(
        id=entry_id or f"id_{hash(content) % 9999:04d}",
        content=content,
        memory_type=MemoryType.SEMANTIC,
        namespace="research_facts",
        truth=TruthValue.from_observation(confidence),
    )


class TestConsolidationAction:
    def test_action_values(self):
        assert ConsolidationAction.ADD.value == "ADD"
        assert ConsolidationAction.UPDATE.value == "UPDATE"
        assert ConsolidationAction.DELETE.value == "DELETE"
        assert ConsolidationAction.SKIP.value == "SKIP"

    def test_action_from_string(self):
        assert ConsolidationAction("ADD") == ConsolidationAction.ADD


class TestConsolidationDecision:
    def test_default_is_skip(self):
        d = ConsolidationDecision()
        assert d.action == ConsolidationAction.SKIP
        assert d.existing_id is None
        assert d.confidence == 0.0

    def test_decision_with_all_fields(self):
        d = ConsolidationDecision(
            action=ConsolidationAction.UPDATE,
            existing_id="abc",
            new_content="updated content",
            reason="new info",
            confidence=0.9,
        )
        assert d.action == ConsolidationAction.UPDATE
        assert d.existing_id == "abc"
        assert d.new_content == "updated content"


class TestLLMConsolidator:
    @pytest.fixture
    def provider(self):
        return FakeLLMProvider(responses={
            "structured_output": {
                "action": "SKIP",
                "existing_id": None,
                "new_content": None,
                "reason": "duplicate",
                "confidence": 0.95,
            },
        })

    @pytest.fixture
    def consolidator(self, provider):
        return LLMConsolidator(provider=provider, similarity_threshold=0.5)

    @pytest.mark.anyio
    async def test_add_when_no_existing(self, consolidator):
        new = _make_entry("RAG with reranking improves retrieval by 15 percent")
        decision = await consolidator.consolidate_entry(new, [])
        assert decision.action == ConsolidationAction.ADD
        assert decision.confidence == 1.0

    @pytest.mark.anyio
    async def test_add_when_no_similar_found(self, consolidator):
        new = _make_entry("quantum computing uses qubits")
        existing = [_make_entry("RAG improves retrieval performance")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.ADD
        assert decision.confidence == 0.8

    @pytest.mark.anyio
    async def test_llm_decides_skip_on_similar(self, consolidator, provider):
        new = _make_entry("RAG with reranking improves retrieval by 15 percent")
        existing = [_make_entry("RAG with reranking improves retrieval by 15 percent on standard benchmarks")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.SKIP
        assert provider._call_log[-1]["method"] == "structured_output"

    @pytest.mark.anyio
    async def test_llm_decides_update(self, provider):
        provider._responses["structured_output"] = {
            "action": "UPDATE",
            "existing_id": "existing_1",
            "new_content": "Updated content with new info",
            "reason": "new data available",
            "confidence": 0.85,
        }
        consolidator = LLMConsolidator(provider=provider, similarity_threshold=0.5)
        new = _make_entry("RAG with reranking improves retrieval by 20 percent")
        existing = [_make_entry("RAG with reranking improves retrieval by 15 percent", entry_id="existing_1")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.UPDATE
        assert decision.existing_id == "existing_1"

    @pytest.mark.anyio
    async def test_llm_decides_delete(self, provider):
        provider._responses["structured_output"] = {
            "action": "DELETE",
            "existing_id": "old_id",
            "new_content": None,
            "reason": "superseded",
            "confidence": 0.9,
        }
        consolidator = LLMConsolidator(provider=provider, similarity_threshold=0.5)
        new = _make_entry("RAG with reranking improves retrieval by 20 percent new results")
        existing = [_make_entry("RAG with reranking improves retrieval by 15 percent old results", entry_id="old_id")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.DELETE

    @pytest.mark.anyio
    async def test_invalid_action_defaults_to_skip(self, provider):
        provider._responses["structured_output"] = {
            "action": "INVALID_ACTION",
            "reason": "bad",
            "confidence": 0.5,
        }
        consolidator = LLMConsolidator(provider=provider, similarity_threshold=0.5)
        new = _make_entry("some similar text here about RAG")
        existing = [_make_entry("some similar text here about RAG retrieval")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.SKIP

    @pytest.mark.anyio
    async def test_llm_failure_defaults_to_add(self, provider):
        provider._responses["structured_output"] = Exception("LLM error")
        consolidator = LLMConsolidator(provider=provider, similarity_threshold=0.5)
        new = _make_entry("some similar text here about RAG")
        existing = [_make_entry("some similar text here about RAG retrieval")]
        decision = await consolidator.consolidate_entry(new, existing)
        assert decision.action == ConsolidationAction.ADD
        assert decision.confidence == 0.3

    @pytest.mark.anyio
    async def test_pass1_jaccard_filters(self, consolidator):
        new_content = "the cat sat on the mat"
        entry_close = _make_entry("the cat sat on the mat and floor")
        entry_far = _make_entry("quantum entanglement is a physical phenomenon")
        candidates = consolidator._pass_1_find_similar(new_content, [entry_close, entry_far])
        assert len(candidates) == 1
        assert "cat" in candidates[0].content


class TestConsolidationSweep:
    @pytest.mark.anyio
    async def test_sweep_empty_memory(self):
        from unittest.mock import MagicMock
        provider = FakeLLMProvider()
        consolidator = LLMConsolidator(provider=provider)
        memory = MagicMock()
        memory._index = {}
        stats = await consolidator.run_consolidation_sweep(memory)
        assert stats["scanned"] == 0

    @pytest.mark.anyio
    async def test_sweep_with_entries(self):
        from unittest.mock import MagicMock
        provider = FakeLLMProvider(responses={
            "structured_output": {
                "action": "SKIP",
                "reason": "keep",
                "confidence": 0.9,
            },
        })
        consolidator = LLMConsolidator(provider=provider, similarity_threshold=0.1)
        entries = {
            "id1": _make_entry("RAG improves retrieval", entry_id="id1"),
            "id2": _make_entry("RAG improves retrieval with reranking", entry_id="id2"),
        }
        memory = MagicMock()
        memory._index = entries
        stats = await consolidator.run_consolidation_sweep(memory, batch_size=2)
        assert stats["scanned"] == 2
