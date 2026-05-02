"""BATCH-45: Gap-to-Paper Navigation & Related Gaps tests."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from backend.api.routes.gaps import router

app = FastAPI()
app.include_router(router, prefix="/gaps")


def _mock_gap():
    g = MagicMock()
    g.id = 1
    g.title = "Test Gap"
    g.pipeline_run_id = 1
    g.related_clusters = "[1, 3]"
    return g


def test_45_01_01_papers_endpoint():
    gap = _mock_gap()
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    paper = MagicMock()
    paper.id = 1; paper.title = "Paper A"; paper.abstract = "Abstract"; paper.year = 2024; paper.venue = "NeurIPS"; paper.citation_count = 50
    ms.execute.return_value.scalar_one_or_none.return_value = None  # for latest run lookup
    ms.execute.return_value.scalars.return_value.all.return_value = [paper]

    from backend.db.crud import get_gap
    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.get_gap", return_value=gap):
        client = TestClient(app)
        resp = client.get("/gaps/1/papers")
    assert resp.status_code == 200
    body = resp.json()
    assert "papers" in body


def test_45_01_02_related_endpoint():
    gap = _mock_gap()
    other = MagicMock()
    other.id = 2; other.title = "Related Gap"; other.confidence = 0.7; other.gap_type = "empirical"; other.related_clusters = "[1, 5]"
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    ms.execute.return_value.scalars.return_value.all.return_value = [other]

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.get_gap", return_value=gap):
        client = TestClient(app)
        resp = client.get("/gaps/1/related")
    assert resp.status_code == 200
    body = resp.json()
    assert "gaps" in body
    assert len(body["gaps"]) == 1
    assert body["gaps"][0]["shared_clusters"] == [1]


def test_45_01_03_no_clusters():
    gap = _mock_gap()
    gap.related_clusters = None
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.get_gap", return_value=gap):
        client = TestClient(app)
        resp = client.get("/gaps/1/related")
    assert resp.status_code == 200
    assert resp.json()["gaps"] == []


def test_45_01_04_not_found():
    """Gap not found returns NotFoundError."""
    from backend.api.errors import NotFoundError
    import pytest
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.get_gap", return_value=None), \
         pytest.raises(NotFoundError):
        client = TestClient(app)
        client.get("/gaps/999/papers")
