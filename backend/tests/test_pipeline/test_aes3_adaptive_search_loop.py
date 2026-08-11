"""AES-3: Adaptive search loop integration tests.

Tests that the adaptive loop in ``LiteratureSearchStage.execute()``
activates correctly, produces governed adaptive queries, converges
deterministically, and preserves the initial corpus on failure.

Important: when a gateway is present, the stage's initial LLM query
expansion calls the gateway once BEFORE the adaptive loop. So gateway
call counts must account for that initial call.
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.literature.contracts import SearchBatchOutcome
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.persistence import CandidateWithDiscoveries
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import LiteratureSearchStage, StageContext

ADAPTIVE_CFG = {
    "enabled": True,
    "enabled_strategies": ["deep_research", "academic_proposal"],
    "max_rounds": 2,
    "queries_per_round": 3,
    "limit_per_source": 10,
    "digest_max_papers": 20,
    "digest_abstract_chars": 600,
    "dedup_similarity_threshold": 0.85,
}


def _paper(title="Test Paper", doi=None, id="p1", source="openalex"):
    return Paper(
        id=id, source=source, title=title,
        abstract="An abstract about ML methods.",
        authors=[Author(name="A")], year=2024, doi=doi,
    )


def _cand(paper):
    return CandidateWithDiscoveries(paper=paper)


def _ctx(**kw):
    defaults = dict(
        result=PipelineResult(), all_papers=[], domain="AI/NLP",
        search_queries=["test query"],
    )
    defaults.update(kw)
    return StageContext(**defaults)


def _gw_resp(content):
    r = MagicMock()
    r.content = content
    r.degraded = False
    r.warnings = []
    return r


def _stage(
    search=None, gateway=None, adaptive_config=None,
    strategy_name="deep_research",
):
    hooks = MagicMock()
    hooks.dispatch_sync_safe = AsyncMock()
    return LiteratureSearchStage(
        search=search or AsyncMock(), hooks=hooks,
        gateway=gateway, persistence=None,
        adaptive_config=adaptive_config,
        strategy_name=strategy_name,
    )


def _run(stage, ctx):
    with patch(
        "backend.pipeline.knowledge.integration.KnowledgeIntegrationService"
    ) as mock_ki:
        mock_ki.return_value.query_existing_knowledge.return_value = {
            "has_knowledge": False
        }
        with patch("backend.config.get_settings") as mock_s:
            mock_s.return_value = MagicMock(embedding_base_url=None)
            return asyncio.run(stage.execute(ctx))


# ── Activation tests ───────────────────────────────────────────────────────


class TestAdaptiveActivation:
    def test_disabled_config_skips_planner(self):
        """Empty adaptive_config: gateway called once (initial expansion)."""
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha Method", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(return_value=_gw_resp('[]'))
        stage = _stage(search=search, gateway=gw, adaptive_config={})
        _run(stage, _ctx())
        assert gw.call.call_count == 1  # initial expansion only

    def test_wrong_strategy_skips_planner(self):
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha Method", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(return_value=_gw_resp('[]'))
        stage = _stage(
            search=search, gateway=gw,
            adaptive_config=ADAPTIVE_CFG, strategy_name="fast_scan",
        )
        _run(stage, _ctx())
        assert gw.call.call_count == 1  # initial expansion only

    def test_no_gateway_adaptive_disabled(self):
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha Method", id="a"))],
                executions=[],
            )
        )
        stage = _stage(
            search=search, gateway=None, adaptive_config=ADAPTIVE_CFG,
        )
        ok = _run(stage, _ctx())
        assert ok is True


# ── Loop behavior tests ────────────────────────────────────────────────────


class TestAdaptiveLoop:
    def test_planner_empty_no_adaptive_batch(self):
        """Planner returns [] → no second governed search round."""
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),  # initial expansion
                _gw_resp('[]'),  # adaptive planner round 1 → empty
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        _run(stage, _ctx())
        assert gw.call.call_count == 2  # expansion + planner

    def test_one_adaptive_query_finds_new_paper(self):
        """Planner proposes one query → new paper C discovered."""
        pa = _paper(title="Alpha Method for Classification", id="a")
        pc = _paper(title="Calibration Under Distribution Shift", id="c")

        call_n = [0]

        async def mock_search(*a, **kw):
            call_n[0] += 1
            if call_n[0] <= 1:  # initial batch (1 query)
                return SearchBatchOutcome(
                    candidates=[_cand(pa)], executions=[],
                )
            return SearchBatchOutcome(
                candidates=[_cand(pc)], executions=[],
            )

        search = AsyncMock()
        search.search_all_with_provenance = mock_search

        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),  # initial expansion
                _gw_resp(json.dumps(["calibration for distribution shift"])),
                _gw_resp('[]'),  # planner converges
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        ctx = _ctx()
        _run(stage, ctx)
        titles = [p.title for p in ctx.all_papers]
        assert "Calibration Under Distribution Shift" in titles

    def test_adaptive_query_identity(self):
        """Adaptive SearchQueryData has correct origin/type/sequence."""
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),  # initial expansion
                _gw_resp(json.dumps(["calibration techniques"])),
                _gw_resp('[]'),  # converge
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        ctx = _ctx()
        _run(stage, ctx)
        adaptive = [
            q for q in ctx.search_query_data
            if q.generation_origin == "adaptive"
        ]
        assert len(adaptive) >= 1
        assert adaptive[0].query_type == "llm_generated"
        initial = sum(
            1 for q in ctx.search_query_data
            if q.generation_origin != "adaptive"
        )
        assert adaptive[0].sequence_number >= initial

    def test_adaptive_query_in_final_data(self):
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),
                _gw_resp(json.dumps(["calibration for deep learning"])),
                _gw_resp('[]'),
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        ctx = _ctx()
        _run(stage, ctx)
        texts = [
            q.query_text for q in ctx.search_query_data
            if q.generation_origin == "adaptive"
        ]
        assert "calibration for deep learning" in texts

    def test_rediscovery_stops_loop(self):
        """A round that only rediscovers existing papers stops."""
        pa = _paper(title="Alpha Method for Classification", doi="10.1/a", id="a")

        async def mock_search(*a, **kw):
            return SearchBatchOutcome(
                candidates=[_cand(pa)], executions=[],
            )

        search = AsyncMock()
        search.search_all_with_provenance = mock_search

        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),  # initial expansion
                _gw_resp(json.dumps(["new aspect of the method"])),
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        _run(stage, _ctx())
        # Gateway: 1 initial + 1 planner = 2. No third call because
        # rediscovery stopped the loop.
        assert gw.call.call_count == 2

    def test_max_rounds_hard_enforced(self):
        """max_rounds=2 is a hard ceiling."""
        pa = _paper(title="Alpha", id="a")
        pb = _paper(title="Beta Technique", id="b")
        pc = _paper(title="Gamma Approach", id="c")

        call_n = [0]
        cycle = [pa, pb, pc, pa, pa]

        async def mock_search(*a, **kw):
            idx = min(call_n[0], len(cycle) - 1)
            call_n[0] += 1
            return SearchBatchOutcome(
                candidates=[_cand(cycle[idx])], executions=[],
            )

        search = AsyncMock()
        search.search_all_with_provenance = mock_search

        gw = MagicMock()
        gw.call = AsyncMock(
            return_value=_gw_resp(
                json.dumps(["always new query topic"])
            )
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        _run(stage, _ctx())
        # 1 initial expansion + at most 2 adaptive planner calls = 3.
        assert gw.call.call_count <= 3

    def test_planner_exception_preserves_initial(self):
        """Gateway exception → initial corpus survives."""
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[
                    _cand(_paper(title="Alpha for Classification", id="a"))
                ],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),  # initial expansion succeeds
                RuntimeError("gateway down"),  # planner fails
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        ctx = _ctx()
        ok = _run(stage, ctx)
        assert ok is True
        titles = [p.title for p in ctx.all_papers]
        assert "Alpha for Classification" in titles

    def test_post_adaptive_seen_prevents_duplicates(self):
        """Adaptive paper must not be re-added by enrichment."""
        pa = _paper(
            title="Alpha Method for Classification",
            doi="10.1/a", id="a",
        )
        pc = _paper(
            title="Calibration Under Distribution Shift",
            doi="10.3/c", id="c",
        )

        call_n = [0]

        async def mock_search(*a, **kw):
            call_n[0] += 1
            if call_n[0] <= 1:  # initial batch (1 query)
                return SearchBatchOutcome(
                    candidates=[_cand(pa)], executions=[],
                )
            return SearchBatchOutcome(
                candidates=[_cand(pc)], executions=[],
            )

        search = AsyncMock()
        search.search_all_with_provenance = mock_search

        gw = MagicMock()
        gw.call = AsyncMock(
            side_effect=[
                _gw_resp('[]'),
                _gw_resp(json.dumps(["calibration for distribution shift"])),
                _gw_resp('[]'),
            ]
        )
        stage = _stage(
            search=search, gateway=gw, adaptive_config=ADAPTIVE_CFG,
        )
        ctx = _ctx()
        _run(stage, ctx)
        c_matches = [
            p for p in ctx.all_papers
            if p.title.lower().strip() == pc.title.lower().strip()
        ]
        assert len(c_matches) == 1


# ── Configuration tests ────────────────────────────────────────────────────


class TestAdaptiveConfig:
    def test_valid_config_loads(self):
        from backend.pipeline.dag.config import ConfigLoader
        config = ConfigLoader().load()
        adaptive = config["search"]["adaptive_search"]
        assert adaptive["enabled"] is True
        assert "deep_research" in adaptive["enabled_strategies"]
        assert adaptive["max_rounds"] == 2

    def test_invalid_threshold_fails(self):
        from backend.pipeline.dag.config import ConfigLoader
        with pytest.raises(ValueError, match="dedup_similarity"):
            ConfigLoader._validate_adaptive_search(
                {"dedup_similarity_threshold": 1.5}
            )

    def test_negative_rounds_fail(self):
        from backend.pipeline.dag.config import ConfigLoader
        with pytest.raises(ValueError, match="max_rounds"):
            ConfigLoader._validate_adaptive_search({"max_rounds": -1})

    def test_absent_block_is_valid(self):
        from backend.pipeline.dag.config import ConfigLoader
        ConfigLoader._validate_search({
            "sources": ["openalex"],
            "queries_per_source": 5,
            "citation_explore": True,
        })

    def test_fast_scan_no_planner(self):
        search = AsyncMock()
        search.search_all_with_provenance = AsyncMock(
            return_value=SearchBatchOutcome(
                candidates=[_cand(_paper(title="Alpha", id="a"))],
                executions=[],
            )
        )
        gw = MagicMock()
        gw.call = AsyncMock(return_value=_gw_resp('[]'))
        stage = _stage(
            search=search, gateway=gw,
            adaptive_config=ADAPTIVE_CFG, strategy_name="fast_scan",
        )
        _run(stage, _ctx())
        assert gw.call.call_count == 1  # initial expansion only
