"""BATCH-135 Tests — LLM-Grounded Connection Agent."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.connection_agent import ConnectionAgent, PaperConnection


def _comparison(pid, compared_to, rel="improves_on"):
    return Claim(claim_type=ClaimType.COMPARISON, title=f"vs {compared_to}",
                 description=f"Comparison", source_paper_id=pid,
                 compared_to=compared_to, relationship=rel, confidence=0.85)

def _method(name, pid):
    return Claim(claim_type=ClaimType.METHOD, title=name, description=name,
                 source_paper_id=pid, method_name=name)

def _result(dataset, pid, method_name=None):
    return Claim(claim_type=ClaimType.RESULT, title=f"Result on {dataset}",
                 description=f"Result", source_paper_id=pid,
                 dataset=dataset, metric="acc", value="90%", method_name=method_name)


class TestLLMConnectionAgent:
    def test_llm_infers_complements(self):
        """TEST-135-01: LLM infers complements for papers sharing datasets."""
        provider = MagicMock()
        provider.complete = AsyncMock(return_value=
            '{"connection_type": "complements", "confidence": 0.75, "evidence": "BERT uses bidirectional context while GPT uses autoregressive — complementary approaches to language modeling"}')
        agent = ConnectionAgent(provider=provider)
        claims = [
            _method("BERT", "P1"),
            _method("GPT-3", "P2"),
            _result("SQuAD", "P1"),
            _result("SQuAD", "P2"),
        ]
        conns = agent.find_connections(claims)
        assert any(c.connection_type == "complements" for c in conns)

    def test_comparison_claims_still_work(self):
        """TEST-135-02: COMPARISON claims still detected."""
        agent = ConnectionAgent(provider=None)
        claims = [_comparison("P1", "P2", "improves_on")]
        conns = agent.find_connections(claims)
        assert any(c.connection_type == "builds_on" for c in conns)

    def test_shared_methods_still_work(self):
        """TEST-135-03: Shared method detection still works."""
        agent = ConnectionAgent(provider=None)
        claims = [_method("BERT", "P1"), _method("BERT", "P2")]
        conns = agent.find_connections(claims)
        assert any(c.connection_type == "complements" for c in conns)

    def test_llm_failure_falls_back(self):
        """TEST-135-04: Falls back gracefully on LLM failure."""
        provider = MagicMock()
        provider.complete = AsyncMock(side_effect=RuntimeError("API down"))
        agent = ConnectionAgent(provider=provider)
        claims = [
            _method("BERT", "P1"),
            _result("SQuAD", "P2"),
        ]
        conns = agent.find_connections(claims)
        # Should not crash, may return empty (no shared methods/datasets)
        assert isinstance(conns, list)

    def test_deduplication(self):
        """TEST-135-05: Deduplication works."""
        agent = ConnectionAgent(provider=None)
        claims = [
            _comparison("P1", "P2", "improves_on"),
            _method("BERT", "P1"),
            _method("BERT", "P2"),
        ]
        conns = agent.find_connections(claims)
        pairs = set()
        for c in conns:
            pair = tuple(sorted([c.paper_a, c.paper_b]))
            key = (pair, c.connection_type)
            assert key not in pairs
            pairs.add(key)

    def test_prompt_exists(self):
        """TEST-135-06: Connection inference prompt exists."""
        from pathlib import Path
        assert Path("backend/pipeline/claims/prompts/connection_inference.md").exists()
