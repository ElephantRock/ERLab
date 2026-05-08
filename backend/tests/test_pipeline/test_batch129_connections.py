"""BATCH-129 Tests — Cross-Paper Connection Agent."""

import pytest
from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.connection_agent import ConnectionAgent, PaperConnection


class TestConnectionAgent:
    def _comparison(self, paper_id, compared_to, relationship="improves_on"):
        return Claim(
            claim_type=ClaimType.COMPARISON, title=f"vs {compared_to}",
            description=f"Comparison with {compared_to}", source_paper_id=paper_id,
            compared_to=compared_to, relationship=relationship, confidence=0.85,
        )

    def _method(self, name, paper_id):
        return Claim(claim_type=ClaimType.METHOD, title=name, description=f"{name} method",
                     source_paper_id=paper_id, method_name=name)

    def test_connection_creates(self):
        """TEST-129-01: PaperConnection creates."""
        conn = PaperConnection(paper_a="P1", paper_b="P2", connection_type="builds_on",
                               confidence=0.8, evidence="test")
        assert conn.connection_type == "builds_on"

    def test_finds_comparison_connections(self):
        """TEST-129-02: Finds connections from COMPARISON claims."""
        agent = ConnectionAgent()
        claims = [self._comparison("P1", "P2", "improves_on")]
        conns = agent.find_connections(claims)
        assert len(conns) >= 1
        assert any(c.connection_type == "builds_on" for c in conns)

    def test_finds_shared_method_connections(self):
        """TEST-129-03: Finds connections from shared methods."""
        agent = ConnectionAgent()
        claims = [
            self._method("BERT", "P1"),
            self._method("BERT", "P2"),  # Same method, different paper
        ]
        conns = agent.find_connections(claims)
        assert any(c.connection_type == "complements" for c in conns)

    def test_contradiction_detected(self):
        """TEST-129-04: Contradiction relationship detected."""
        agent = ConnectionAgent()
        claims = [self._comparison("P1", "P2", "contradicts")]
        conns = agent.find_connections(claims)
        assert any(c.connection_type == "contradicts" for c in conns)

    def test_deduplicates(self):
        """TEST-129-05: Duplicate connections removed."""
        agent = ConnectionAgent()
        claims = [
            self._comparison("P1", "P2", "improves_on"),
            self._method("BERT", "P1"),
            self._method("BERT", "P2"),
        ]
        conns = agent.find_connections(claims)
        # Check no duplicate (P1, P2) pairs with same type
        pairs = set()
        for c in conns:
            pair = tuple(sorted([c.paper_a, c.paper_b]))
            key = (pair, c.connection_type)
            assert key not in pairs, f"Duplicate connection: {key}"
            pairs.add(key)

    def test_empty_claims(self):
        """TEST-129-06: Returns [] on empty claims."""
        agent = ConnectionAgent()
        assert agent.find_connections([]) == []
