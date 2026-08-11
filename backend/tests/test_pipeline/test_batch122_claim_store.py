"""BATCH-122 Tests — Claim Storage & Query Layer.

AIV v5.3 — 12 tests across 2 tasks.
pytest.ini has `-p no:asyncio` — use asyncio.run() directly.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.db.database import Base
from backend.db.models import ResearchClaim
from backend.pipeline.claims.models import Claim, ClaimType
from backend.pipeline.claims.store import ClaimStore

# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def db_session():
    """In-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()


def _make_claim(**overrides) -> Claim:
    """Create a test Claim with defaults."""
    defaults = {
        "claim_type": ClaimType.METHOD,
        "title": "Test method",
        "description": "A test method for research",
        "source_paper_id": "paper-001",
        "method_name": "TestMethod",
        "method_category": "architecture",
    }
    defaults.update(overrides)
    return Claim(**defaults)


# ═══════════════════════════════════════════════════════════
# TASK-01: ResearchClaims Database Model + Migration
# ═══════════════════════════════════════════════════════════


class TestResearchClaimModel:
    """TEST-122-01-01 through TEST-122-01-02."""

    def test_model_has_all_fields(self, db_session):
        """TEST-122-01-01: ResearchClaim model has all required fields."""
        row = ResearchClaim(
            claim_id="test-uuid-1",
            claim_type="METHOD",
            title="Test",
            description="Desc",
            source_paper_id="P1",
            source_section="abstract",
            confidence=0.8,
            method_name="TestMethod",
            method_category="architecture",
            dataset="WikiText-103",
            metric="perplexity",
            value="24.0",
            baseline_method="LSTM",
            baseline_value="48.7",
            limitation_category="compute",
            acknowledged=True,
            feasibility="high",
            potential_impact="high",
            compared_to="LSTM",
            relationship="improves_on",
            extra_json='{"constraints": {"max_seq": 512}}',
        )
        db_session.add(row)
        db_session.commit()

        fetched = db_session.query(ResearchClaim).first()
        assert fetched.claim_id == "test-uuid-1"
        assert fetched.claim_type == "METHOD"
        assert fetched.title == "Test"
        assert fetched.description == "Desc"
        assert fetched.source_paper_id == "P1"
        assert fetched.confidence == 0.8
        assert fetched.method_name == "TestMethod"
        assert fetched.dataset == "WikiText-103"
        assert fetched.metric == "perplexity"
        assert fetched.value == "24.0"
        assert fetched.baseline_method == "LSTM"
        assert fetched.limitation_category == "compute"
        assert fetched.acknowledged is True
        assert fetched.feasibility == "high"
        assert fetched.compared_to == "LSTM"
        assert fetched.relationship == "improves_on"
        assert fetched.extra_json is not None
        # Verify no AttributeError on any field
        for attr in [
            "claim_id", "claim_type", "title", "description",
            "source_paper_id", "source_section", "confidence",
            "method_name", "method_category", "dataset", "metric",
            "value", "baseline_method", "baseline_value",
            "limitation_category", "acknowledged", "feasibility",
            "potential_impact", "compared_to", "relationship",
            "extra_json", "created_at",
        ]:
            assert hasattr(fetched, attr), f"Missing attribute: {attr}"

    def test_claim_id_is_unique(self, db_session):
        """TEST-122-01-02: claim_id has unique constraint."""
        row1 = ResearchClaim(
            claim_id="unique-id",
            claim_type="METHOD",
            title="T1",
            description="D1",
            source_paper_id="P1",
        )
        db_session.add(row1)
        db_session.commit()

        row2 = ResearchClaim(
            claim_id="unique-id",  # Same claim_id
            claim_type="RESULT",
            title="T2",
            description="D2",
            source_paper_id="P1",
        )
        db_session.add(row2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()


# ═══════════════════════════════════════════════════════════
# TASK-02: ClaimStore Service
# ═══════════════════════════════════════════════════════════


class TestClaimStore:
    """TEST-122-02-01 through TEST-122-02-10."""

    def test_store_claims_persists(self, db_session):
        """TEST-122-02-01: store_claims persists claims to DB."""
        store = ClaimStore(session=db_session)
        claims = [
            _make_claim(claim_id="c1", title="Claim 1"),
            _make_claim(claim_id="c2", title="Claim 2", claim_type=ClaimType.RESULT),
            _make_claim(claim_id="c3", title="Claim 3", claim_type=ClaimType.LIMITATION),
        ]

        count = asyncio.run(store.store_claims(claims))
        assert count == 3

        retrieved = store.get_claims_by_paper("paper-001")
        assert len(retrieved) == 3

    def test_store_claims_idempotent(self, db_session):
        """TEST-122-02-02: store_claims is idempotent (HB-01)."""
        store = ClaimStore(session=db_session)
        claims = [_make_claim(claim_id="c1")]

        count1 = asyncio.run(store.store_claims(claims))
        assert count1 == 1

        # Store same claims again (same claim_id)
        count2 = asyncio.run(store.store_claims(claims))
        assert count2 == 0  # No new claims stored

        assert store.count_claims() == 1  # HB-01

    def test_get_claims_by_type_filters(self, db_session):
        """TEST-122-02-03: get_claims_by_type filters correctly."""
        store = ClaimStore(session=db_session)
        claims = [
            _make_claim(claim_id="c1", claim_type=ClaimType.METHOD),
            _make_claim(claim_id="c2", claim_type=ClaimType.RESULT),
            _make_claim(claim_id="c3", claim_type=ClaimType.METHOD),
        ]
        asyncio.run(store.store_claims(claims))

        method_claims = store.get_claims_by_type(ClaimType.METHOD)
        assert len(method_claims) == 2
        assert all(c.claim_type == ClaimType.METHOD for c in method_claims)

    def test_find_similar_claims_empty_db(self, db_session):
        """TEST-122-02-11: find_similar_claims returns [] on empty DB (HB-02)."""
        store = ClaimStore(session=db_session)
        results = asyncio.run(store.find_similar_claims("transformer architecture"))
        assert results == []  # HB-02

    def test_delete_claims_by_paper(self, db_session):
        """TEST-122-02-05: delete_claims_by_paper removes claims."""
        store = ClaimStore(session=db_session)
        claims = [_make_claim(claim_id="c1", source_paper_id="to-delete")]
        asyncio.run(store.store_claims(claims))

        deleted = store.delete_claims_by_paper("to-delete")
        assert deleted == 1

        assert store.get_claims_by_paper("to-delete") == []

    def test_count_claims(self, db_session):
        """TEST-122-02-06: count_claims returns total."""
        store = ClaimStore(session=db_session)
        claims = [_make_claim(claim_id=f"c{i}") for i in range(5)]
        asyncio.run(store.store_claims(claims))

        assert store.count_claims() == 5

    def test_round_trip_preserves_fields(self, db_session):
        """TEST-122-02-07: Round-trip: Claim → DB → Claim preserves all fields."""
        store = ClaimStore(session=db_session)
        original = Claim(
            claim_type=ClaimType.RESULT,
            title="SOTA result",
            description="Achieves 95.2% accuracy on GLUE",
            source_paper_id="paper-rt",
            source_section="results",
            confidence=0.92,
            method_name="BERT-Large",
            method_category="architecture",
            dataset="GLUE",
            metric="accuracy",
            value="95.2%",
            baseline_method="GPT-2",
            baseline_value="89.1%",
            limitation_category="compute",
            acknowledged=True,
            feasibility="low",
            potential_impact="high",
            compared_to="GPT-2",
            relationship="improves_on",
            constraints={"max_seq_length": 512, "parameter_count": "340M"},
        )

        asyncio.run(store.store_claims([original]))
        retrieved = store.get_claims_by_paper("paper-rt")
        assert len(retrieved) == 1

        rt = retrieved[0]
        assert rt.claim_type == original.claim_type
        assert rt.title == original.title
        assert rt.description == original.description
        assert rt.source_paper_id == original.source_paper_id
        assert rt.source_section == original.source_section
        assert rt.confidence == original.confidence
        assert rt.method_name == original.method_name
        assert rt.method_category == original.method_category
        assert rt.dataset == original.dataset
        assert rt.metric == original.metric
        assert rt.value == original.value
        assert rt.baseline_method == original.baseline_method
        assert rt.baseline_value == original.baseline_value
        assert rt.limitation_category == original.limitation_category
        assert rt.acknowledged == original.acknowledged
        assert rt.feasibility == original.feasibility
        assert rt.potential_impact == original.potential_impact
        assert rt.compared_to == original.compared_to
        assert rt.relationship == original.relationship
        assert rt.constraints == original.constraints

    def test_find_similar_claims_success_path(self, db_session):
        """TEST-122-02-08: find_similar_claims returns relevant results on populated DB."""
        store = ClaimStore(session=db_session)
        claims = [
            _make_claim(claim_id="c1", description="The Transformer uses self-attention mechanism for NLP tasks"),
            _make_claim(claim_id="c2", description="ResNet introduces residual connections for image classification"),
            _make_claim(claim_id="c3", description="BERT uses masked language modeling for pre-training"),
        ]
        asyncio.run(store.store_claims(claims))

        results = asyncio.run(store.find_similar_claims("self-attention transformer NLP"))
        assert len(results) > 0
        # At least one result should have positive similarity
        assert any(sim > 0 for _, sim in results)

    def test_keyword_fallback_no_embedding_service(self, db_session):
        """TEST-122-02-09: Keyword fallback works when embedding_service=None."""
        store = ClaimStore(session=db_session, embedding_service=None)
        claims = [
            _make_claim(claim_id="c1", description="Neural machine translation with attention"),
        ]
        asyncio.run(store.store_claims(claims))

        results = asyncio.run(store.find_similar_claims("machine translation attention"))
        assert len(results) > 0
        assert results[0][1] > 0  # Non-zero similarity

    def test_invalid_claim_type_raises_on_read(self, db_session):
        """TEST-122-02-10: Invalid claim_type raises ValueError on read (A-02)."""
        # Directly insert a row with invalid claim_type
        row = ResearchClaim(
            claim_id="bad-type",
            claim_type="INVALID_TYPE",
            title="Bad",
            description="Bad type",
            source_paper_id="P1",
        )
        db_session.add(row)
        db_session.commit()

        store = ClaimStore(session=db_session)
        with pytest.raises(ValueError, match="Invalid claim_type"):
            store.get_claims_by_paper("P1")
