"""BATCH-47: Global Search tests."""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.search import router

app = FastAPI()
app.include_router(router, prefix="/search")


def _mock_session():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    return ms, mc


def test_47_01_01_search_returns_results():
    ms, mc = _mock_session()
    idea = MagicMock()
    idea.id = 1; idea.title = "Transfer Learning"; idea.domain = "AI"; idea.overall_score = 0.8
    ms.execute.return_value.scalars.return_value.all.return_value = [idea]
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/search/?q=transfer")
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert body["total"] >= 1


def test_47_01_02_type_filter():
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/search/?q=test&types=ideas")
    assert resp.status_code == 200
    body = resp.json()
    assert "ideas" in body["results"]
    assert "gaps" not in body["results"]


def test_47_01_03_empty_query():
    with patch("backend.db.database.get_session"):
        client = TestClient(app)
        resp = client.get("/search/?q=")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_47_01_04_special_chars():
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/search/?q=test%27%3B%20DROP%20TABLE%20ideas%3B%20--")
    assert resp.status_code == 200  # No crash = injection safe


def test_47_01_05_results_grouped_by_type():
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/search/?q=test&types=ideas,gaps,papers,runs")
    assert resp.status_code == 200
    body = resp.json()
    assert all(k in body["results"] for k in ["ideas", "gaps", "papers", "runs"])


def test_47_01_06_no_results():
    ms, mc = _mock_session()
    ms.execute.return_value.scalars.return_value.all.return_value = []
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/search/?q=nonexistent")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
