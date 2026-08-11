"""AES-2: Regression tests for the governed batch execution extraction.

Tests that ``_execute_query_batch`` and ``_merge_candidate_corpus``
produce the same results as the pre-refactor inline code, and that the
extraction is truly behavior-neutral.

The batch-execution tests mock the search service and verify normalized
output (candidates + linkage expectations). The merge tests call the
method directly with constructed candidates and verify exact/fuzzy dedup,
discovery-route preservation, and new_unique_count semantics.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.literature.contracts import (
    AttemptOutcome,
    SearchBatchOutcome,
)
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.persistence import (
    CandidateWithDiscoveries,
    DiscoveryMetadata,
    SearchQueryData,
)
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    LiteratureSearchStage,
    StageContext,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _paper(
    title: str = "Test Paper",
    doi: str | None = None,
    source: str = "openalex",
    id: str = "p1",
) -> Paper:
    return Paper(
        id=id,
        source=source,
        title=title,
        abstract="An abstract.",
        authors=[Author(name="Author")],
        year=2024,
        doi=doi,
    )


def _candidate(
    title: str = "Test Paper",
    doi: str | None = None,
    source: str = "openalex",
    id: str = "p1",
    discoveries: list[DiscoveryMetadata] | None = None,
) -> CandidateWithDiscoveries:
    return CandidateWithDiscoveries(
        paper=_paper(title=title, doi=doi, source=source, id=id),
        discoveries=discoveries or [],
    )


def _sqd(text: str = "test query", seq: int = 0) -> SearchQueryData:
    return SearchQueryData(
        query_text=text,
        query_type="template",
        generation_origin="base",
        sequence_number=seq,
        query_key=f"key_{seq}",
    )


def _stage(search=None, persistence=None) -> LiteratureSearchStage:
    hooks = MagicMock()
    hooks.dispatch_sync_safe = AsyncMock()
    return LiteratureSearchStage(
        search=search or AsyncMock(),
        hooks=hooks,
        persistence=persistence,
    )


def _ctx(db_run_id: int | None = None) -> StageContext:
    return StageContext(
        result=PipelineResult(),
        all_papers=[],
        domain="AI/NLP",
        db_run_id=db_run_id,
    )


# ── _execute_query_batch tests ──────────────────────────────────────────────


class TestExecuteQueryBatch:
    """Verify the extracted batch method normalizes all result shapes."""

    def test_governed_batch_normalizes_search_batch_outcome(self):
        """SearchBatchOutcome produces candidates + linkage expectations."""
        cand = _candidate(title="Alpha Method", doi="10.1/a")
        exec_outcome = AttemptOutcome(
            execution_id=1,
            source="openalex",
            status="success",
            attempt_count=1,
            results=[MagicMock()],
        )
        outcome = SearchBatchOutcome(
            candidates=[cand],
            executions=[exec_outcome],
        )
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(return_value=outcome)
        stage = _stage(search=search, persistence=MagicMock())
        stage._persistence.ensure_search_queries = MagicMock(
            return_value={"key_0": 42}
        )

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=1),
            query_data=[_sqd()],
            db_engine=MagicMock(),
        ))

        assert len(batch.candidates) == 1
        assert batch.candidates[0].paper.title == "Alpha Method"
        assert len(batch.linkage_expectations) == 1
        assert batch.linkage_expectations[0].execution_id == 1
        assert batch.linkage_expectations[0].accounting_status == "reconciled"

    def test_partial_execution_preserves_linkage(self):
        """Partial status produces reconciled linkage."""
        exec_outcome = AttemptOutcome(
            execution_id=2,
            source="crossref",
            status="partial",
            attempt_count=1,
            results=[MagicMock()],
        )
        outcome = SearchBatchOutcome(
            candidates=[],
            executions=[exec_outcome],
        )
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(return_value=outcome)
        stage = _stage(search=search, persistence=MagicMock())
        stage._persistence.ensure_search_queries = MagicMock(
            return_value={"key_0": 42}
        )

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=1),
            query_data=[_sqd()],
            db_engine=MagicMock(),
        ))

        assert len(batch.linkage_expectations) == 1
        assert batch.linkage_expectations[0].accounting_status == "reconciled"

    def test_skipped_execution_preserves_incomplete(self):
        """Skipped status produces incomplete linkage with None count."""
        exec_outcome = AttemptOutcome(
            execution_id=3,
            source="semantic_scholar",
            status="skipped",
            attempt_count=0,
            results=[],
        )
        outcome = SearchBatchOutcome(
            candidates=[],
            executions=[exec_outcome],
        )
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(return_value=outcome)
        stage = _stage(search=search, persistence=MagicMock())
        stage._persistence.ensure_search_queries = MagicMock(
            return_value={"key_0": 42}
        )

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=1),
            query_data=[_sqd()],
            db_engine=MagicMock(),
        ))

        assert len(batch.linkage_expectations) == 1
        linkage = batch.linkage_expectations[0]
        assert linkage.accounting_status == "incomplete"
        assert linkage.expected_discovery_count is None

    def test_legacy_list_result_zero_linkage(self):
        """Bare list result produces candidates but no linkage."""
        cand = _candidate(title="Legacy Paper")
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(return_value=[cand])
        stage = _stage(search=search)

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=None),
            query_data=[_sqd()],
            db_engine=None,
        ))

        assert len(batch.candidates) == 1
        assert batch.linkage_expectations == []

    def test_failed_query_does_not_cancel_siblings(self):
        """One exception in gather does not prevent sibling results."""
        good_cand = _candidate(title="Good Paper", id="good")
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            side_effect=[
                RuntimeError("source down"),
                [good_cand],
            ]
        )
        stage = _stage(search=search)

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=None),
            query_data=[_sqd("q1", 0), _sqd("q2", 1)],
            db_engine=None,
        ))

        assert len(batch.candidates) == 1
        assert batch.candidates[0].paper.title == "Good Paper"

    def test_unexpected_type_contributes_nothing(self):
        """A non-standard return type does not crash the batch."""
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=42  # unexpected
        )
        stage = _stage(search=search)

        batch = asyncio.run(stage._execute_query_batch(
            ctx=_ctx(db_run_id=None),
            query_data=[_sqd()],
            db_engine=None,
        ))

        assert batch.candidates == []
        assert batch.linkage_expectations == []


# ── _merge_candidate_corpus tests ───────────────────────────────────────────


class TestMergeCandidateCorpus:
    """Verify exact/fuzzy dedup, discovery preservation, and counting."""

    def test_exact_duplicate_preserves_first_and_combines(self):
        """Same DOI: first candidate wins, discoveries merge."""
        d1 = DiscoveryMetadata(
            query_key="q1", source="openalex", source_record_id="a1",
        )
        d2 = DiscoveryMetadata(
            query_key="q2", source="crossref", source_record_id="c1",
        )
        c1 = _candidate(title="Alpha", doi="10.1/a", id="first",
                        discoveries=[d1])
        c2 = _candidate(title="Alpha", doi="10.1/a", id="second",
                        discoveries=[d2])
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[], incoming=[c1, c2],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].paper.id == "first"
        assert len(result.candidates[0].discoveries) == 2

    def test_fuzzy_duplicate_combines_discoveries(self):
        """Titles above 0.85 similarity: first-match wins, discoveries merge."""
        d1 = DiscoveryMetadata(
            query_key="q1", source="openalex", source_record_id="a1",
        )
        d2 = DiscoveryMetadata(
            query_key="q2", source="crossref", source_record_id="c1",
        )
        c1 = _candidate(
            title="Machine Learning Classification Methods",
            doi="10.1/a", id="first", discoveries=[d1],
        )
        c2 = _candidate(
            title="Machine Learning Classification Method",
            doi="10.2/b", id="second", discoveries=[d2],
        )
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[], incoming=[c1, c2],
        )

        assert len(result.candidates) == 1
        assert result.candidates[0].paper.id == "first"
        assert len(result.candidates[0].discoveries) == 2

    def test_below_threshold_remain_separate(self):
        """Dissimilar titles survive as distinct candidates."""
        c1 = _candidate(
            title="Graph Neural Networks for Physics",
            doi="10.1/a", id="gnn",
        )
        c2 = _candidate(
            title="Reinforcement Learning for Robotics",
            doi="10.2/b", id="rl",
        )
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[], incoming=[c1, c2],
        )

        assert len(result.candidates) == 2

    def test_incremental_rediscovery_zero_new_unique(self):
        """Same paper via different route: discoveries merge, count is 0."""
        d1 = DiscoveryMetadata(
            query_key="q1", source="openalex", source_record_id="a1",
        )
        d2 = DiscoveryMetadata(
            query_key="q7", source="crossref", source_record_id="c1",
        )
        existing_cand = _candidate(
            title="Alpha Method", doi="10.1/a",
            id="orig", discoveries=[d1],
        )
        incoming_cand = _candidate(
            title="Alpha Method", doi="10.1/a",
            id="adaptive", discoveries=[d2],
        )
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[existing_cand],
            incoming=[incoming_cand],
        )

        assert result.new_unique_count == 0
        assert len(result.candidates) == 1
        assert len(result.candidates[0].discoveries) == 2

    def test_incremental_new_paper_counts_one(self):
        """Genuinely new paper: count is 1."""
        existing_cand = _candidate(
            title="Alpha Method", doi="10.1/a", id="orig",
        )
        incoming_cand = _candidate(
            title="Beta Technique for Calibration",
            doi="10.3/c", id="new_paper",
        )
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[existing_cand],
            incoming=[incoming_cand],
        )

        assert result.new_unique_count == 1
        assert len(result.candidates) == 2

    def test_empty_existing_reproduces_current_ordering(self):
        """existing=[] with incoming produces same ordering as old inline code."""
        c1 = _candidate(title="First Paper", doi="10.1/a", id="p1")
        c2 = _candidate(title="Second Paper", doi="10.2/b", id="p2")
        stage = _stage()

        result = stage._merge_candidate_corpus(
            existing=[], incoming=[c1, c2],
        )

        assert len(result.candidates) == 2
        assert result.candidates[0].paper.id == "p1"
        assert result.candidates[1].paper.id == "p2"
        assert result.new_unique_count == 2
