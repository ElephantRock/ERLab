"""BATCH-43/TASK-01: Cluster API tests."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from backend.api.routes.gaps import router

app = FastAPI()
app.include_router(router, prefix="/gaps")


def test_43_01_01_clusters_returns_data():
    mock_run = MagicMock()
    mock_run.cluster_report_json = '{"clusters": [{"cluster_id": 1, "label": "NLP", "paper_count": 5, "top_terms": ["nlp"], "avg_citations": 10}], "total_papers": 5}'
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mock_cm):
        client = TestClient(app)
        resp = client.get("/gaps/clusters?run_id=1")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["clusters"]) == 1
    assert body["total_papers"] == 5


def test_43_01_02_null_report_returns_empty():
    mock_run = MagicMock()
    mock_run.cluster_report_json = None
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_session.get.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mock_cm):
        client = TestClient(app)
        resp = client.get("/gaps/clusters?run_id=1")
    assert resp.status_code == 200
    assert resp.json()["clusters"] == []


def test_43_01_03_no_run_id_returns_latest():
    mock_latest = MagicMock()
    mock_latest.id = 1
    mock_run = MagicMock()
    mock_run.cluster_report_json = '{"clusters": [], "total_papers": 0}'
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.scalar_one_or_none.return_value = mock_latest
    mock_session.get.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mock_cm):
        client = TestClient(app)
        resp = client.get("/gaps/clusters")
    assert resp.status_code == 200


def test_43_01_04_no_completed_runs():
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_session.execute.return_value.scalar_one_or_none.return_value = None

    with patch("backend.db.database.get_session", return_value=mock_cm):
        client = TestClient(app)
        resp = client.get("/gaps/clusters")
    assert resp.status_code == 200
    assert resp.json()["clusters"] == []
