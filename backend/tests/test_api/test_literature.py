"""Tests for BATCH-23/TASK-01: Literature search and ingest API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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


# ── F1.5c: GET /literature/ingested returns persisted paper IDs ──
class TestIngestedEndpoint:
    """F1.5c: GET /literature/ingested exposes the authoritative set of
    persisted paper IDs from the vector store. The frontend literature UI
    derives its 'Ingested' badge from this response (not from ephemeral
    client state), so the badge survives reload/remount.
    """

    def _make_store(self, metadatas):
        """Build a fake VectorStore whose _collection.get returns metadatas."""
        mock_collection = MagicMock()
        mock_collection.get.return_value = {"metadatas": metadatas}
        mock_store = MagicMock()
        mock_store._collection = mock_collection
        return mock_store

    def test_ingested_returns_ids_from_vector_store(self, client):
        """GET /literature/ingested returns unique paper_ids from metadata."""
        store = self._make_store([
            {"paper_id": "ss-1", "source": "semantic_scholar"},
            {"paper_id": "ss-1", "source": "semantic_scholar"},  # dup
            {"paper_id": "arxiv-2", "source": "arxiv"},
        ])

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=store,
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ):
            response = client.get("/api/v1/literature/ingested")

        assert response.status_code == 200
        data = response.json()
        assert "ids" in data
        # Duplicates are collapsed
        assert data["ids"] == ["ss-1", "arxiv-2"]

    def test_ingested_returns_empty_when_store_unavailable(self, client):
        """GET /literature/ingested returns {ids: []} on backend failure
        rather than 500 — the UI gracefully treats this as 'no persisted
        ingestion state known'."""
        with patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
            side_effect=RuntimeError("provider offline"),
        ):
            response = client.get("/api/v1/literature/ingested")

        assert response.status_code == 200
        data = response.json()
        assert data["ids"] == []

    def test_ingested_skips_entries_without_paper_id(self, client):
        """GET /literature/ingested ignores metadata entries lacking paper_id
        (e.g. locally uploaded documents that use a different schema)."""
        store = self._make_store([
            {"paper_id": "ss-1"},
            {"filename": "notes.pdf"},  # local upload, no paper_id
            {"paper_id": "arxiv-2"},
        ])

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=store,
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ):
            response = client.get("/api/v1/literature/ingested")

        assert response.status_code == 200
        assert response.json()["ids"] == ["ss-1", "arxiv-2"]
