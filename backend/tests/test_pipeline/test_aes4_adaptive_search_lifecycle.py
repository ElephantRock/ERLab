"""AES-4: Controlled causal/provenance lifecycle proof.

Exercises real LiteratureSearchStage, real LLMQueryGenerator adaptive
method, real SearchService, real ExecutionRecorder, real
PipelinePersistence, and real reconcile_run_search against a temporary
SQL database. Only external nondeterminism (LLM gateway responses and
academic source network) is mocked.

Primary test: initial Q0 finds A,B → planner sees A,B → generates Q1
→ Q1 finds C → planner sees A,B,C → converges → corpus persisted →
reconciliation = reconciled → durable lineage proven.

Convergence test: Q1 only rediscovers A,B → new_unique_count == 0 →
loop stops → no Q2.
"""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    PaperDiscovery,
    PipelineRun,
    RunPaper,
    SearchQuery,
    SearchQueryExecution,
)
from backend.pipeline.dag.config import ConfigLoader
from backend.pipeline.gateway.gateway import LLMRequest
from backend.pipeline.literature.contracts import (
    SourceQueryPlan,
    SourceResultAccounting,
    SourceSearchOutcome,
    canonical_plan_json,
)
from backend.pipeline.literature.models import Author, Paper, SearchResult
from backend.pipeline.literature.result_accounting import (
    reconcile_source_results,
)
from backend.pipeline.literature.run_reconciliation import (
    reconcile_run_search,
)
from backend.pipeline.literature.search_service import SearchService
from backend.pipeline.persistence import PipelinePersistence
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import LiteratureSearchStage, StageContext

# ── Config ──────────────────────────────────────────────────────────────────

ADAPTIVE_CFG = {
    "enabled": True,
    "enabled_strategies": ["deep_research"],
    "max_rounds": 2,
    "queries_per_round": 3,
    "limit_per_source": 10,
    "digest_max_papers": 20,
    "digest_abstract_chars": 600,
    "dedup_similarity_threshold": 0.85,
}

SOURCE_NAME = "openalex"


# ── Test papers ─────────────────────────────────────────────────────────────

PAPER_A = Paper(
    id="ctrl:a", source=SOURCE_NAME,
    title="Robust Method X for Classification Tasks",
    abstract="We study calibration properties of Method X under distribution shift.",
    authors=[Author(name="Author A")], year=2024,
    doi="10.1/a",
)
PAPER_B = Paper(
    id="ctrl:b", source=SOURCE_NAME,
    title="Distribution Shift Analysis in Deep Learning",
    abstract="Distribution shift remains an open problem for deep learning systems.",
    authors=[Author(name="Author B")], year=2023,
    doi="10.2/b",
)
PAPER_C = Paper(
    id="ctrl:c", source=SOURCE_NAME,
    title="Calibration Evaluation Under Covariate Shift",
    abstract="We evaluate calibration metrics when covariate shift is present.",
    authors=[Author(name="Author C")], year=2024,
    doi="10.3/c",
)


# ── DB helpers ──────────────────────────────────────────────────────────────


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def _seed_run(engine) -> int:
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_aes4",
        domain="machine learning",
        status="running",
        config_json="{}",
        stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    run_id = run.id
    session.close()
    return run_id


@contextmanager
def _patched_session(engine):
    """Monkeypatch get_session to bind to the test engine."""
    import backend.pipeline.persistence as persist_mod
    import backend.db.database as db_mod

    test_session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched_get_session():
        session = test_session_factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    original = db_mod.get_session
    db_mod.get_session = patched_get_session
    persist_mod.get_session = patched_get_session
    try:
        yield
    finally:
        db_mod.get_session = original
        persist_mod.get_session = original


# ── Deterministic source adapter ────────────────────────────────────────────


class ControlledSourceAdapter:
    """Returns deterministic papers based on the query text."""

    source_name = SOURCE_NAME

    def __init__(self, query_map: dict[str, list[Paper]]):
        self._map = query_map
        self.call_count = 0

    def build_query_plan(
        self, query: str, limit: int = 20,
        year_from: int | None = None, year_to: int | None = None,
    ) -> SourceQueryPlan:
        return SourceQueryPlan(
            source=SOURCE_NAME,
            schema_version="source_query_v1",
            translated_query=canonical_plan_json(
                SOURCE_NAME, {"query": query}
            ),
            request_parameters={"query": query},
        )

    async def execute_query_plan(
        self, plan: SourceQueryPlan, *,
        attempt_observer=None,
    ) -> SourceSearchOutcome:
        self.call_count += 1
        if attempt_observer:
            await attempt_observer.attempt_started()

        query = plan.request_parameters.get("query", "")
        papers = self._lookup(query)

        results = [
            SearchResult(paper=p, source=SOURCE_NAME)
            for p in papers
        ]
        unique, acct = reconcile_source_results(
            raw_result_count=len(results),
            normalized_results=results,
            rejected_result_count=0,
        )
        return SourceSearchOutcome(
            results=unique,
            status="success",
            attempt_count=1,
            accounting=acct,
        )

    async def get_paper(self, paper_id: str) -> Paper | None:
        return None

    async def get_citations(self, paper_id: str, limit: int = 50) -> list[Paper]:
        return []

    async def get_references(self, paper_id: str, limit: int = 50) -> list[Paper]:
        return []

    def _lookup(self, query: str) -> list[Paper]:
        normalized = query.strip().lower()
        for key, papers in self._map.items():
            if key.strip().lower() in normalized or normalized in key.strip().lower():
                return papers
        return []


# ── Gateway dispatcher ──────────────────────────────────────────────────────


class GatewayDispatcher:
    """Dispatches gateway responses based on request content.

    Initial expansion → []
    Adaptive prompt containing A+B (not C) → Q1
    Adaptive prompt containing A+B+C → []
    """

    def __init__(self):
        self.calls: list[LLMRequest] = []

    async def __call__(self, request: LLMRequest):
        self.calls.append(request)
        user_content = request.messages[-1]["content"]

        # Initial expansion (no "CURRENTLY DISCOVERED LITERATURE").
        if "CURRENTLY DISCOVERED LITERATURE" not in user_content:
            resp = MagicMock()
            resp.content = "[]"
            resp.degraded = False
            resp.warnings = []
            return resp

        # Adaptive planner.
        has_c = "Calibration Evaluation" in user_content
        if not has_c:
            # Round 1: sees A+B, proposes Q1.
            resp = MagicMock()
            resp.content = json.dumps([
                "method X calibration under distribution shift",
            ])
            resp.degraded = False
            resp.warnings = []
            return resp

        # Round 2: sees A+B+C, converges.
        resp = MagicMock()
        resp.content = "[]"
        resp.degraded = False
        resp.warnings = []
        return resp


# ── Stage helpers ───────────────────────────────────────────────────────────


def _build_stage(
    engine, gateway, query_map,
) -> LiteratureSearchStage:
    adapter = ControlledSourceAdapter(query_map)
    search = SearchService(sources=[adapter])
    persistence = PipelinePersistence()
    hooks = MagicMock()
    hooks.dispatch_sync_safe = AsyncMock()

    return LiteratureSearchStage(
        search=search,
        hooks=hooks,
        gateway=gateway,
        persistence=persistence,
        adaptive_config=ADAPTIVE_CFG,
        strategy_name="deep_research",
    )


def _ctx(db_run_id: int) -> StageContext:
    return StageContext(
        result=PipelineResult(),
        all_papers=[],
        domain="machine learning",
        research_question="How does Method X behave under distribution shift?",
        search_queries=["method X distribution shift"],
        db_run_id=db_run_id,
        run_id="run_aes4",
    )


def _run_stage(stage, ctx, engine):
    """Run the stage with all infrastructure bound to the test engine."""
    with _patched_session(engine), patch(
        "backend.pipeline.knowledge.integration.KnowledgeIntegrationService"
    ) as mock_ki:
        mock_ki.return_value.query_existing_knowledge.return_value = {
            "has_knowledge": False
        }
        with patch("backend.config.get_settings") as mock_s:
            mock_s.return_value = MagicMock(embedding_base_url=None)
            with patch(
                "backend.db.database._get_engine", return_value=engine
            ):
                asyncio.run(stage.execute(ctx))


# ── Primary lifecycle test ──────────────────────────────────────────────────


class TestAdaptiveLifecycle:
    """Proves the full causal + durable provenance lifecycle."""

    def test_causal_loop_and_durable_lineage(self):
        """Q0→A,B → planner sees A,B → Q1 → C → planner sees A,B,C → [].

        Then persist → reconcile → durable lineage proven.
        """
        engine = _make_engine()
        run_id = _seed_run(engine)

        query_map = {
            "method X distribution shift": [PAPER_A, PAPER_B],
            "calibration": [PAPER_C],
        }

        dispatcher = GatewayDispatcher()
        gateway = MagicMock()
        gateway.call = dispatcher

        stage = _build_stage(engine, gateway, query_map)
        ctx = _ctx(run_id)

        with _patched_session(engine):
            _run_stage(stage, ctx, engine)

        # ── Causal proof: planner received evidence ─────────────────
        adaptive_calls = [
            r for r in dispatcher.calls
            if "CURRENTLY DISCOVERED LITERATURE" in r.messages[-1]["content"]
        ]
        assert len(adaptive_calls) == 2, (
            f"Expected 2 adaptive planner calls, got {len(adaptive_calls)}"
        )

        round1_content = adaptive_calls[0].messages[-1]["content"]
        assert "Robust Method X" in round1_content  # Paper A
        assert "Distribution Shift Analysis" in round1_content  # Paper B
        assert "Calibration Evaluation" not in round1_content  # NOT Paper C

        round2_content = adaptive_calls[1].messages[-1]["content"]
        assert "Robust Method X" in round2_content
        assert "Distribution Shift Analysis" in round2_content
        assert "Calibration Evaluation" in round2_content  # Paper C now present

        # ── Adaptive query has governed identity ────────────────────
        adaptive_queries = [
            q for q in ctx.search_query_data
            if q.generation_origin == "adaptive"
        ]
        assert len(adaptive_queries) == 1
        assert adaptive_queries[0].query_type == "llm_generated"

        # ── Paper C in final corpus ─────────────────────────────────
        titles = [p.title for p in ctx.all_papers]
        assert "Calibration Evaluation Under Covariate Shift" in titles
        assert "Robust Method X for Classification Tasks" in titles
        assert "Distribution Shift Analysis in Deep Learning" in titles

        # ── Persist and reconcile ───────────────────────────────────
        with _patched_session(engine):
            persistence = PipelinePersistence()
            persistence.persist_search_results(
                candidates=ctx.candidate_papers,
                search_queries=ctx.search_query_data,
                db_run_id=run_id,
                execution_linkage_expectations=(
                    ctx.execution_linkage_expectations
                ),
            )

        status = reconcile_run_search(engine, run_id)
        assert status == "reconciled", (
            f"Expected reconciled, got {status}"
        )

        # ── Durable lineage proof ───────────────────────────────────
        Session = sessionmaker(bind=engine)
        session = Session()

        # Q1 exists with correct identity.
        all_queries = session.execute(
            select(SearchQuery).where(SearchQuery.run_id == run_id)
        ).scalars().all()
        adaptive_q = [
            q for q in all_queries
            if q.generation_origin == "adaptive"
        ]
        assert len(adaptive_q) == 1
        assert adaptive_q[0].query_type == "llm_generated"
        assert adaptive_q[0].sequence_number > min(
            q.sequence_number for q in all_queries
            if q.generation_origin != "adaptive"
        )

        # Execution exists for Q1.
        execs = session.execute(
            select(SearchQueryExecution).where(
                SearchQueryExecution.search_query_id == adaptive_q[0].id
            )
        ).scalars().all()
        assert len(execs) >= 1
        assert execs[0].source == SOURCE_NAME
        assert execs[0].status == "success"

        # Paper C has discovery linked to Q1's execution.
        c_discoveries = session.execute(
            select(PaperDiscovery).where(
                PaperDiscovery.run_id == run_id,
                PaperDiscovery.source == SOURCE_NAME,
            ).order_by(PaperDiscovery.search_query_id)
        ).scalars().all()

        c_linked = [
            d for d in c_discoveries
            if d.search_query_id == adaptive_q[0].id
        ]
        assert len(c_linked) >= 1, (
            "Paper C should have a discovery linked to the adaptive query"
        )

        # All 3 papers are run members.
        run_papers = session.execute(
            select(RunPaper).where(RunPaper.run_id == run_id)
        ).scalars().all()
        assert len(run_papers) == 3

        session.close()


# ── Convergence test ────────────────────────────────────────────────────────


class TestAdaptiveConvergence:
    """Proves new_unique_count == 0 stops the loop with routes preserved."""

    def test_rediscovery_only_stops_loop(self):
        """Q1 only rediscovers A → new_unique_count == 0 → no Q2."""
        engine = _make_engine()
        run_id = _seed_run(engine)

        # Q1 returns Paper A again (rediscovery).
        query_map = {
            "method X distribution shift": [PAPER_A, PAPER_B],
            "calibration": [PAPER_A],  # Rediscovery of A only
        }

        dispatcher = GatewayDispatcher()
        gateway = MagicMock()
        gateway.call = dispatcher

        stage = _build_stage(engine, gateway, query_map)
        ctx = _ctx(run_id)

        with _patched_session(engine):
            _run_stage(stage, ctx, engine)

        # Only 2 gateway calls: 1 initial expansion + 1 adaptive planner.
        # The loop stopped because rediscovery → new_unique_count == 0.
        assert len(dispatcher.calls) == 2

        # Adaptive query exists.
        adaptive_queries = [
            q for q in ctx.search_query_data
            if q.generation_origin == "adaptive"
        ]
        assert len(adaptive_queries) == 1

        # Paper A has 2 discovery routes (Q0 + Q1).
        a_candidates = [
            c for c in ctx.candidate_papers
            if c.paper.title == PAPER_A.title
        ]
        assert len(a_candidates) == 1
        assert len(a_candidates[0].discoveries) >= 2

        # No third planner call (no Q2).
        adaptive_calls = [
            r for r in dispatcher.calls
            if "CURRENTLY DISCOVERED LITERATURE" in r.messages[-1]["content"]
        ]
        assert len(adaptive_calls) == 1


# ── Config validation ───────────────────────────────────────────────────────


class TestAdaptiveConfigValidation:
    def test_yaml_config_loads_with_adaptive(self):
        config = ConfigLoader().load()
        adaptive = config["search"]["adaptive_search"]
        assert adaptive["enabled"] is True
        assert adaptive["max_rounds"] >= 1

    def test_invalid_threshold_rejected(self):
        from backend.pipeline.dag.config import ConfigLoader
        with pytest.raises(ValueError, match="threshold"):
            ConfigLoader._validate_adaptive_search(
                {"dedup_similarity_threshold": 2.0}
            )

    def test_absent_block_means_disabled(self):
        from backend.pipeline.dag.config import ConfigLoader
        ConfigLoader._validate_search({
            "sources": ["openalex"],
            "queries_per_source": 5,
            "citation_explore": True,
        })
