"""AES-1: Evidence-aware adaptive query planner tests.

Tests the planner method (``generate_adaptive_queries``) and the query
hygiene functions (``adaptive_search.py``). Nothing in production calls
the planner yet — these tests prove capability in isolation.

Gateway mock inspects the actual ``LLMRequest`` to verify the planner
goes through the governed LLM path, not an ungoverned direct call.
"""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator
from backend.pipeline.literature.adaptive_search import (
    filter_adaptive_queries,
    is_terminal_planner_text,
    normalize_query,
    query_similarity,
)
from backend.pipeline.literature.models import Author, Paper


# ── Helpers ──────────────────────────────────────────────────────────────────


def _paper(
    title: str = "Test Paper",
    abstract: str = "An abstract about machine learning methods.",
    source: str = "openalex",
    year: int = 2024,
    venue: str = "NeurIPS",
) -> Paper:
    return Paper(
        id="test1",
        source=source,
        title=title,
        abstract=abstract,
        authors=[Author(name="Author A")],
        year=year,
        venue=venue,
    )


def _gateway_returning(content: str, degraded: bool = False):
    """Build a mock gateway whose .call returns the given content."""
    gw = MagicMock()
    response = MagicMock()
    response.content = content
    response.degraded = degraded
    response.warnings = []
    gw.call = AsyncMock(return_value=response)
    return gw


def _run_planner(
    gateway,
    *,
    research_question: str = "How does method X behave under distribution shift?",
    attempted_queries: list[str] | None = None,
    papers: list[Paper] | None = None,
    n_queries: int = 3,
    run_id: str = "run_test",
    max_papers: int = 20,
    abstract_chars: int = 600,
) -> list[str]:
    gen = LLMQueryGenerator(gateway)
    return asyncio.run(gen.generate_adaptive_queries(
        research_question=research_question,
        attempted_queries=attempted_queries or ["method X distribution shift"],
        papers=papers or [_paper()],
        n_queries=n_queries,
        run_id=run_id,
        max_papers=max_papers,
        abstract_chars=abstract_chars,
    ))


# ── 1. Evidence digest contains retrieved literature ───────────────────────


def test_digest_contains_retrieved_literature():
    """Paper title, abstract, year, venue, and source appear in the request."""
    paper = _paper(
        title="Calibration Methods for Neural Networks",
        abstract="We study calibration under distribution shift.",
        source="openalex",
        year=2023,
        venue="ICML",
    )
    gw = _gateway_returning('[]')
    _run_planner(gw, papers=[paper])

    request = gw.call.call_args[0][0]
    user_msg = request.messages[1]["content"]

    assert "Calibration Methods for Neural Networks" in user_msg
    assert "We study calibration under distribution shift" in user_msg
    assert "2023" in user_msg
    assert "ICML" in user_msg
    assert "openalex" in user_msg


# ── 2. Digest bounds are enforced ───────────────────────────────────────────


def test_digest_bounds_enforced():
    """max_papers=2 and abstract_chars=50 cannot leak paper 3 or long abstract."""
    papers = [
        _paper(title=f"Paper {i}", abstract="A" * 200, source="openalex")
        for i in range(5)
    ]
    gw = _gateway_returning('[]')
    _run_planner(gw, papers=papers, max_papers=2, abstract_chars=50)

    request = gw.call.call_args[0][0]
    user_msg = request.messages[1]["content"]

    assert "Paper 0" in user_msg
    assert "Paper 1" in user_msg
    assert "Paper 2" not in user_msg
    # Each abstract entry should be at most 50 chars
    # (the "A" * 200 should be truncated)
    assert user_msg.count("A" * 51) == 0


# ── 3. Attempted queries are present ────────────────────────────────────────


def test_attempted_queries_present():
    gw = _gateway_returning('[]')
    _run_planner(gw, attempted_queries=["alpha query", "beta query"])

    request = gw.call.call_args[0][0]
    user_msg = request.messages[1]["content"]

    assert "alpha query" in user_msg
    assert "beta query" in user_msg


# ── 4. Valid new queries survive ────────────────────────────────────────────


def test_valid_new_queries_survive():
    gw = _gateway_returning(
        json.dumps(["calibration methods for neural networks"])
    )
    result = _run_planner(gw)
    assert "calibration methods for neural networks" in result
    assert len(result) == 1


# ── 5. Exact attempted-query duplicate is rejected ──────────────────────────


def test_exact_duplicate_rejected():
    attempted = ["method X distribution shift"]
    gw = _gateway_returning(
        json.dumps(["method X distribution shift"])
    )
    result = _run_planner(gw, attempted_queries=attempted)
    assert result == []


# ── 6. Near-duplicate above 0.85 is rejected ────────────────────────────────


def test_near_duplicate_rejected():
    attempted = ["machine learning classification methods"]
    # Nearly identical — high similarity
    gw = _gateway_returning(
        json.dumps(["machine learning classification method"])
    )
    result = _run_planner(gw, attempted_queries=attempted)
    assert result == []


# ── 7. Duplicates within one planner response collapse ──────────────────────


def test_intra_response_duplicates_collapse():
    gw = _gateway_returning(
        json.dumps([
            "calibration methods for deep learning",
            "calibration methods for deep learning",
        ])
    )
    result = _run_planner(gw, n_queries=3)
    assert len(result) == 1


# ── 8. Terminal prose is rejected ───────────────────────────────────────────


def test_terminal_prose_rejected():
    gw = _gateway_returning(
        json.dumps(["No further queries needed"])
    )
    result = _run_planner(gw)
    assert result == []


# ── 9. Empty array remains empty ────────────────────────────────────────────


def test_empty_array_remains_empty():
    gw = _gateway_returning('[]')
    result = _run_planner(gw)
    assert result == []


# ── 10. Malformed/non-array response returns [] ─────────────────────────────


def test_malformed_response_returns_empty():
    gw = _gateway_returning('This is not JSON at all.')
    result = _run_planner(gw)
    assert result == []


def test_non_array_json_returns_empty():
    gw = _gateway_returning('{"key": "value"}')
    result = _run_planner(gw)
    assert result == []


# ── 11. Degraded gateway response returns [] ────────────────────────────────


def test_degraded_gateway_returns_empty():
    gw = _gateway_returning("", degraded=True)
    result = _run_planner(gw)
    assert result == []


# ── 12. Result never exceeds n_queries ───────────────────────────────────────


def test_result_never_exceeds_n_queries():
    gw = _gateway_returning(
        json.dumps([
            "query about calibration methods",
            "query about robustness evaluation",
            "query about uncertainty quantification",
            "query about domain adaptation theory",
            "query about transfer learning bounds",
        ])
    )
    result = _run_planner(gw, n_queries=2)
    assert len(result) <= 2


# ── 13. Gateway request uses governed path ──────────────────────────────────


def test_gateway_request_is_governed():
    """The planner must go through the gateway with stage=query_generation."""
    gw = _gateway_returning('[]')
    _run_planner(gw, run_id="run_abc")

    request = gw.call.call_args[0][0]
    assert request.stage == "query_generation"
    assert request.run_id == "run_abc"


# ── Query hygiene unit tests ────────────────────────────────────────────────


def test_normalize_query_collapses_whitespace():
    assert normalize_query("  Hello   World  ") == "hello world"


def test_query_similarity_identical():
    assert query_similarity("test query", "test query") == 1.0


def test_query_similarity_different():
    assert query_similarity("alpha", "beta") < 0.5


def test_is_terminal_planner_text_matches():
    assert is_terminal_planner_text("No further queries needed")
    assert is_terminal_planner_text("sufficient coverage achieved")
    assert not is_terminal_planner_text("calibration methods for ML")
