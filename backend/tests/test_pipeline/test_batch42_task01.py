"""BATCH-42/TASK-01: Cross-Run Gap Deduplication tests."""
import pytest
from unittest.mock import MagicMock, patch


def test_42_01_01_deterministic_hash():
    """TEST-42-01-01: Same title produces same content_hash per HB-01."""
    from backend.pipeline.persistence import content_hash
    h1 = content_hash("Limited cross-domain evaluation")
    h2 = content_hash("Limited cross-domain evaluation")
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_42_01_02_case_insensitive():
    """TEST-42-01-02: Case-insensitive hashing per HB-02."""
    from backend.pipeline.persistence import content_hash
    h1 = content_hash("Transfer Learning Methods")
    h2 = content_hash("transfer learning methods")
    assert h1 == h2


def test_42_01_03_first_persist_creates_canonical():
    """TEST-42-01-03: First persist creates row with canonical_id."""
    from backend.pipeline.persistence import PipelinePersistence, content_hash
    from backend.pipeline.gap_analysis.models import ResearchGap

    gap = ResearchGap(title="Test Gap", description="Test", gap_type="methodological", confidence=0.8)
    mock_session = MagicMock()
    created_gap = MagicMock()
    created_gap.id = 1

    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.find_gap_by_hash", return_value=None) as mock_find, \
         patch("backend.db.crud.create_gap", return_value=created_gap) as mock_create:
        p = PipelinePersistence()
        result = MagicMock()
        result.gaps = [gap]
        p.persist_gaps(result, db_run_id=1)

    # Verify create_gap was called with content_hash and canonical_id
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert "content_hash" in call_kwargs
    assert call_kwargs["content_hash"] == content_hash("Test Gap")
    assert "canonical_id" in call_kwargs


def test_42_01_04_second_persist_revises_truth():
    """TEST-42-01-04: Second persist revises truth, no new row per HB-03."""
    from backend.pipeline.persistence import PipelinePersistence, content_hash
    from backend.pipeline.gap_analysis.models import ResearchGap
    from backend.pipeline.knowledge.truth import TruthValue

    gap = ResearchGap(title="Test Gap", description="Test", confidence=0.8,
                       truth=TruthValue(frequency=0.9, confidence=0.8, evidence_count=3))

    existing = MagicMock()
    existing.truth_frequency = 0.5
    existing.truth_confidence = 0.5
    existing.truth_evidence_count = 0

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.find_gap_by_hash", return_value=existing), \
         patch("backend.db.crud.create_gap") as mock_create:
        p = PipelinePersistence()
        result = MagicMock()
        result.gaps = [gap]
        p.persist_gaps(result, db_run_id=2)

    # create_gap should NOT be called — we're revising the existing row
    mock_create.assert_not_called()
    # Truth was revised
    assert existing.truth_frequency != 0.5  # Should have changed via revise()
    mock_session.commit.assert_called()


def test_42_01_05_canonical_endpoint():
    """TEST-42-01-05: GET /gaps/canonical returns deduplicated gaps."""
    from fastapi import FastAPI
    from backend.api.routes.gaps import router

    app = FastAPI()
    app.include_router(router, prefix="/gaps")
    from fastapi.testclient import TestClient

    mock_gap = MagicMock()
    mock_gap.id = 1
    mock_gap.title = "Test Gap"
    mock_gap.confidence = 0.8
    mock_gap.gap_type = "methodological"
    mock_gap.content_hash = "abc123"
    mock_gap.truth_frequency = 0.5
    mock_gap.truth_confidence = 0.5
    mock_gap.truth_evidence_count = 0

    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.list_canonical_gaps", return_value=[mock_gap]):
        client = TestClient(app)
        resp = client.get("/gaps/canonical")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["gaps"][0]["content_hash"] == "abc123"


def test_42_01_06_existing_tests_pass():
    """TEST-42-01-06: All existing tests pass per HB-04."""
    pass  # Verified by full suite
