"""BATCH-46: Gap & Idea Export tests."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from backend.api.routes.gaps import router

app = FastAPI()
app.include_router(router, prefix="/gaps")


def _mock_gap():
    g = MagicMock()
    g.id = 1; g.title = "Test Gap"; g.description = "Desc"; g.gap_type = "methodological"; g.confidence = 0.8; g.potential_impact = "high"
    return g


def test_46_01_01_csv_export():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    mock_run = MagicMock(); mock_run.id = 1
    ms.execute.return_value.scalar_one_or_none.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.search_gaps", return_value=[_mock_gap()]):
        client = TestClient(app)
        resp = client.get("/gaps/export?format=csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Test Gap" in resp.text


def test_46_01_02_json_export():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    mock_run = MagicMock(); mock_run.id = 1
    ms.execute.return_value.scalar_one_or_none.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.search_gaps", return_value=[_mock_gap()]):
        client = TestClient(app)
        resp = client.get("/gaps/export?format=json")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["gaps"]) == 1


def test_46_01_03_export_respects_filters():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    mock_run = MagicMock(); mock_run.id = 1
    ms.execute.return_value.scalar_one_or_none.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.search_gaps", return_value=[]) as mock_search:
        client = TestClient(app)
        resp = client.get("/gaps/export?format=json&search=test&gap_type=methodological&min_confidence=0.7")
    assert resp.status_code == 200
    # Verify filters were passed
    call_kwargs = mock_search.call_args[1]
    assert call_kwargs["search"] == "test"
    assert call_kwargs["gap_type"] == "methodological"
    assert call_kwargs["min_confidence"] == 0.7


def test_46_01_04_csv_has_bom():
    ms = MagicMock()
    mc = MagicMock()
    mc.__enter__ = MagicMock(return_value=ms)
    mc.__exit__ = MagicMock(return_value=False)
    mock_run = MagicMock(); mock_run.id = 1
    ms.execute.return_value.scalar_one_or_none.return_value = mock_run

    with patch("backend.db.database.get_session", return_value=mc), \
         patch("backend.db.crud.search_gaps", return_value=[_mock_gap()]):
        client = TestClient(app)
        resp = client.get("/gaps/export?format=csv")
    # UTF-8 BOM
    assert resp.content[:3] == b'\xef\xbb\xbf'
