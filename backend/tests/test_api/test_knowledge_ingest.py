"""Tests for BATCH-24/TASK-01: PDF ingest endpoint and enriched stats."""

import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

# Minimal valid PDF: %PDF-1.4 header + minimal body
VALID_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF\n"
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00"  # PE executable header
TEXT_BYTES = b"This is just plain text, not a PDF."


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _make_mock_store(chunk_count=0, unique_paper_ids=None):
    """Build a mock VectorStore with get_stats and _collection.get."""
    mock_store = MagicMock()
    mock_store.get_stats.return_value = {
        "collection": "research_papers",
        "document_count": chunk_count,
    }
    metas = []
    for pid in (unique_paper_ids or []):
        metadatas_inner = [{"paper_id": pid}]
        metas.extend(metadatas_inner)
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"metadatas": metas}
    mock_store._collection = mock_collection
    mock_store.add_papers = AsyncMock(return_value=chunk_count)
    return mock_store


class TestIngestEndpoint:
    """TEST-24-01-01 through TEST-24-01-03."""

    # ── TEST-24-01-01: POST /ingest with valid PDF returns success ──
    def test_ingest_valid_pdf_returns_success(self, client):
        """POST /knowledge/ingest with a valid PDF returns success with chunk count."""
        pdf_file = io.BytesIO(VALID_PDF_BYTES)

        mock_pdf = AsyncMock()
        mock_pdf.parse_and_chunk = AsyncMock(return_value=[])

        with patch(
            "backend.pipeline.ingestion.pdf_service.PDFService",
            return_value=mock_pdf,
        ), patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=_make_mock_store(chunk_count=0),
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ):
            response = client.post(
                "/api/v1/knowledge/ingest",
                files={"file": ("test-paper.pdf", pdf_file, "application/pdf")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ingested"
            assert data["filename"] == "test-paper.pdf"
            assert "chunks" in data

    # ── TEST-24-01-02: POST /ingest with non-PDF returns 400 ──
    def test_ingest_non_pdf_returns_400(self, client):
        """POST /knowledge/ingest with a non-PDF file returns 400 (HB-01)."""
        exe_file = io.BytesIO(EXE_BYTES)
        response = client.post(
            "/api/v1/knowledge/ingest",
            files={"file": ("malware.exe", exe_file, "application/octet-stream")},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "BAD_REQUEST"
        assert "pdf" in data["error"]["message"].lower()

    def test_ingest_text_file_returns_400(self, client):
        """POST /knowledge/ingest with a plain text file returns 400 (HB-01)."""
        text_file = io.BytesIO(TEXT_BYTES)
        response = client.post(
            "/api/v1/knowledge/ingest",
            files={"file": ("notes.txt", text_file, "text/plain")},
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "BAD_REQUEST"

    # ── TEST-24-01-03: POST /ingest with no file returns 422 ──
    def test_ingest_no_file_returns_422(self, client):
        """POST /knowledge/ingest without a file returns 422."""
        response = client.post("/api/v1/knowledge/ingest")

        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "UNPROCESSABLE_ENTITY"


class TestEnrichedStats:
    """TEST-24-01-04: GET /stats returns enriched stats."""

    def test_stats_returns_enriched_fields(self, client):
        """GET /knowledge/stats includes total_documents and total_chunks."""
        mock_store = _make_mock_store(
            chunk_count=42,
            unique_paper_ids=["paper-1", "paper-2", "paper-1"],
        )

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=mock_store,
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ):
            response = client.get("/api/v1/knowledge/stats")

            assert response.status_code == 200
            data = response.json()
            # Original fields still present
            assert "chroma_persist_dir" in data
            assert "embedding_provider" in data
            assert "embedding_model" in data
            # Enriched fields
            assert "total_documents" in data
            assert "total_chunks" in data
            assert data["total_chunks"] == 42
            assert data["total_documents"] == 2  # 2 unique paper_ids
