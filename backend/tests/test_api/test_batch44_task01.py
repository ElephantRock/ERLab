"""BATCH-44: Gap Analytics Dashboard tests."""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.gaps import router

app = FastAPI()
app.include_router(router, prefix="/gaps")


def _result(all_val=None, scalar_val=None):
    """Create a mock execute result."""
    m = MagicMock()
    m.all.return_value = all_val or []
    m.scalar.return_value = scalar_val
    return m


def test_44_01_01_type_distribution():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    ms.execute.side_effect = [
        _result(all_val=[("methodological", 5), ("empirical", 3)]),
        _result(scalar_val=0.7),
        _result(scalar_val=8),
        _result(all_val=[]),
        _result(all_val=[]),
    ]
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/gaps/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "type_distribution" in body


def test_44_01_02_top_gaps_sorted():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    ms.execute.side_effect = [
        _result(all_val=[]),
        _result(scalar_val=0.7),
        _result(scalar_val=8),
        _result(all_val=[("Gap A", 5, 0.9), ("Gap B", 3, 0.7)]),
        _result(all_val=[]),
    ]
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/gaps/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert "top_gaps" in body


def test_44_01_03_confidence_trend():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    ms.execute.side_effect = [
        _result(all_val=[]),
        _result(scalar_val=0.7),
        _result(scalar_val=8),
        _result(all_val=[]),
        _result(all_val=[(1, 0.65, 5), (2, 0.72, 8)]),
    ]
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/gaps/stats")
    assert resp.status_code == 200
    assert "confidence_trend" in resp.json()


def test_44_01_04_empty_db_returns_zeros():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    ms.execute.side_effect = [
        _result(all_val=[]),
        _result(scalar_val=None),
        _result(scalar_val=None),
        _result(all_val=[]),
        _result(all_val=[]),
    ]
    with patch("backend.db.database.get_session", return_value=mc):
        client = TestClient(app)
        resp = client.get("/gaps/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_gaps"] == 0
    assert body["avg_confidence"] == 0.0
