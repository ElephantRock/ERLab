"""Tests for BATCH-23/TASK-01: Literature search and ingest API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.pipeline.literature.models import Author, Paper


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sample_papers():
    return [
        Paper(
            id="ss-abc123",
            source="semantic_scholar",
            title="Attention Is All You Need",
            abstract="We propose a new network architecture, the Transformer.",
            authors=[Author(name="Ashish Vaswani"), Author(name="Noam Shazeer")],
            year=2017,
            citation_count=50000,
            url="https://arxiv.org/abs/1706.03762",
            doi="10.5555/3295222.3295349",
        ),
        Paper(
            id="arxiv-1801.03891",
            source="arxiv",
            title="BERT: Pre-training of Deep Bidirectional Transformers",
            abstract="We introduce BERT, designed to pre-train deep bidirectional representations.",
            authors=[Author(name="Jacob Devlin"), Author(name="Ming-Wei Chang")],
            year=2018,
            url="https://arxiv.org/abs/1810.04805",
        ),
    ]


# ── TEST-23-01-01: GET /literature/search?q=test returns papers ──
class TestSearchEndpoint:
    def test_search_returns_papers(self, client, sample_papers):
        """GET /literature/search?q=test returns papers list."""
        mock_service = AsyncMock()
        mock_service.search_all = AsyncMock(return_value=sample_papers)

        with patch(
            "backend.api.routes.literature._get_service", return_value=mock_service
        ):
            response = client.get("/api/v1/literature/search?q=test")

            assert response.status_code == 200
            data = response.json()
            assert "papers" in data
            assert len(data["papers"]) == 2
            assert data["papers"][0]["title"] == "Attention Is All You Need"
            assert data["papers"][1]["source"] == "arxiv"

    # ── TEST-23-01-02: GET /literature/search without q returns 422 ──
    def test_search_without_query_returns_422(self, client):
        """GET /literature/search without q parameter returns 422."""
        response = client.get("/api/v1/literature/search")

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"

    # ── TEST-23-01-05: Search handles source errors gracefully ──
    def test_search_handles_source_errors(self, client, sample_papers):
        """Search endpoint handles source errors gracefully, returning partial results."""
        mock_service = AsyncMock()
        # SearchService.search_all already handles exceptions internally
        # and returns partial results — simulate that behavior
        mock_service.search_all = AsyncMock(return_value=[sample_papers[0]])

        with patch(
            "backend.api.routes.literature._get_service", return_value=mock_service
        ):
            response = client.get("/api/v1/literature/search?q=transformer&max_results=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data["papers"]) == 1

    def test_search_respects_max_results(self, client, sample_papers):
        """Search endpoint caps results to max_results parameter."""
        mock_service = AsyncMock()
        mock_service.search_all = AsyncMock(return_value=sample_papers)

        with patch(
            "backend.api.routes.literature._get_service", return_value=mock_service
        ):
            response = client.get("/api/v1/literature/search?q=test&max_results=1")

            assert response.status_code == 200
            data = response.json()
            assert len(data["papers"]) == 1


# ── TEST-23-01-03: POST /literature/ingest stores paper ──
class TestIngestEndpoint:
    def test_ingest_stores_paper(self, client):
        """POST /literature/ingest stores a valid paper."""
        paper_payload = {
            "id": "p-test-001",
            "source": "semantic_scholar",
            "title": "Test Paper on Transformers",
            "abstract": "A test paper abstract.",
            "authors": [{"name": "Jane Doe"}, {"name": "John Smith"}],
            "year": 2024,
            "doi": "10.1234/test",
        }

        with patch(
            "backend.api.routes.literature._do_ingest",
            new_callable=AsyncMock,
            return_value={"status": "ingested", "id": "p-test-001"},
        ):
            response = client.post("/api/v1/literature/ingest", json=paper_payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ingested"
            assert data["id"] == "p-test-001"

    # ── TEST-23-01-04: Ingestion confirmation required (paper must have title) ──
    def test_ingest_requires_title(self, client):
        """POST /literature/ingest with empty title returns 400 (HB-01 confirmation)."""
        paper_payload = {
            "id": "p-no-title",
            "source": "arxiv",
            "title": "",
            "abstract": "A paper without a title.",
        }

        response = client.post("/api/v1/literature/ingest", json=paper_payload)

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "BAD_REQUEST"
        assert "title" in data["error"]["message"].lower()
