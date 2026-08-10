"""Phase 1 1B focused tests: research-question threading.

Covers spec 1G backend cases 1–3:
  1. Legacy domain-only requests remain valid.
  2. A research question reaches the persisted run context.
  3. Explicit search queries remain unchanged.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas import PipelineRunRequest


def test_1g_01_legacy_domain_only_request_remains_valid():
    """Case 1: a request with only a domain (no research_question) validates
    exactly as before Phase 1."""
    req = PipelineRunRequest(domain="machine learning")
    assert req.domain == "machine learning"
    assert req.research_question is None
    assert req.search_queries is None


def test_1g_01b_bare_empty_body_still_validates_default_domain():
    """Legacy behavior: an empty body falls back to the default domain."""
    req = PipelineRunRequest()
    assert req.domain == "AI/NLP"
    assert req.research_question is None


def test_1g_02_research_question_accepted_and_stored():
    """Case 2: a research question is accepted on the request model."""
    rq = "How can graph-based reasoning and neuro-symbolical methods improve verifiability?"
    req = PipelineRunRequest(domain="AI/NLP", research_question=rq)
    assert req.research_question == rq


def test_1g_03_explicit_search_queries_remain_unchanged():
    """Case 3: explicit search_queries are preserved verbatim alongside a
    research question (both can coexist)."""
    req = PipelineRunRequest(
        domain="AI/NLP",
        research_question="some question",
        search_queries=["query one", "query two"],
    )
    assert req.search_queries == ["query one", "query two"]


def test_1g_03b_research_question_length_limit_enforced():
    """The max_length guard prevents absurdly long questions."""
    with pytest.raises(ValidationError):
        PipelineRunRequest(research_question="x" * 2001)


# ── StageContext carries the question (unit, no DB) ──────────────


def test_1g_02b_stage_context_carries_research_question():
    """Case 2 (runtime): StageContext propagates research_question to stages."""
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext

    ctx = StageContext(result=PipelineResult(), domain="AI/NLP", research_question="the question")
    assert ctx.research_question == "the question"


def test_1g_02c_stage_context_defaults_to_none():
    """Legacy: StageContext without research_question stays None (not a string)."""
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext

    ctx = StageContext(result=PipelineResult(), domain="AI/NLP")
    assert ctx.research_question is None
