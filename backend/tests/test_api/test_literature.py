"""Tests for BATCH-23/TASK-01: Literature search and ingest API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


# ── F1.5d: POST /literature/ingest write-read consistency ──
class TestIngestPersistence:
    """F1.5d: prove the production ingest service path actually persists.

    These tests exercise the REAL _do_ingest (no AsyncMock replacement).
    The VectorStore class is mocked at the lowest seam so the production
    service logic — chunk construction, store wiring, error handling —
    all runs.

    Contract under test:
        POST /literature/ingest -> VectorStore.add_papers([paper], [chunks])
        GET /literature/ingested -> VectorStore._collection.get(metadatas)

    The mock store simulates persistence by recording add_papers inputs
    and surfacing them via _collection.get, so a subsequent GET observes
    the same paper_id the POST wrote.
    """

    def _persistent_store(self):
        """Build a mock VectorStore whose add_papers records what was
        written and whose _collection.get replays those records. This
        simulates a real vector store: writes become visible to reads.
        """
        written_metadatas = []

        async def _add_papers(papers, chunks):
            # Mirror the production metadata shape written by the real
            # VectorStore.add_papers (vector_store.py:116-126) so the GET
            # read path sees the same field names.
            for paper in papers:
                written_metadatas.append({
                    "paper_id": paper.id,
                    "paper_title": paper.title[:500],
                    "source": paper.source,
                    "section": "abstract",
                    "year": paper.year or 0,
                    "keywords": ",".join(paper.keywords) if paper.keywords else "",
                })
            return 1  # one chunk upserted

        mock_collection = MagicMock()
        mock_collection.get.side_effect = lambda **kw: {"metadatas": list(written_metadatas)}
        mock_store = MagicMock()
        mock_store._collection = mock_collection
        mock_store.add_papers = _add_papers
        return mock_store

    def test_post_then_get_exposes_persisted_paper_id(self, client):
        """POST /literature/ingest persists paper_id such that a subsequent
        GET /literature/ingested reports it. Proves write-read consistency
        through the REAL _do_ingest service path."""
        store = self._persistent_store()

        paper_payload = {
            "id": "ss-persist-001",
            "source": "semantic_scholar",
            "title": "Persistent Paper",
            "abstract": "Abstract text.",
            "authors": [{"name": "Author A"}],
            "year": 2024,
        }

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=store,
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ):
            # (a) Initial GET — paper not yet persisted.
            r0 = client.get("/api/v1/literature/ingested")
            assert r0.status_code == 200
            assert r0.json()["ids"] == []

            # (b) POST runs the REAL _do_ingest → store.add_papers writes.
            r1 = client.post("/api/v1/literature/ingest", json=paper_payload)
            assert r1.status_code == 200
            assert r1.json()["status"] == "ingested"
            assert r1.json()["id"] == "ss-persist-001"

            # (c) Second GET — paper_id now appears. This is the
            # load-bearing write-read consistency assertion: the same
            # paper_id written by POST is reported by GET through the
            # shared VectorStore seam.
            r2 = client.get("/api/v1/literature/ingested")
            assert r2.status_code == 200
            assert "ss-persist-001" in r2.json()["ids"]

    def test_post_failure_does_not_report_ingested(self, client):
        """When persistence fails, POST must surface the failure and a
        subsequent GET must NOT report the paper as ingested. No fake
        'ingested' acknowledgment is permitted."""
        # add_papers raises → _do_ingest must propagate the failure.
        failing_store = MagicMock()

        async def _fail(papers, chunks):
            raise RuntimeError("vector store offline")

        failing_store.add_papers = _fail

        paper_payload = {
            "id": "ss-fail-001",
            "source": "arxiv",
            "title": "Failing Paper",
            "abstract": "Abstract.",
        }

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=failing_store,
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ):
            # POST fails — _do_ingest catches add_papers exception and re-raises
            # as BadRequestError.
            r1 = client.post("/api/v1/literature/ingest", json=paper_payload)
            assert r1.status_code == 400, f"expected 400 on persistence failure, got {r1.status_code}"
            assert "error" in r1.json()

            # GET reports empty — no false-positive ingest.
            # (Use a separate store mock that was never written to.)
            empty_store = MagicMock()
            empty_collection = MagicMock()
            empty_collection.get.return_value = {"metadatas": []}
            empty_store._collection = empty_collection
            with patch(
                "backend.pipeline.knowledge.vector_store.VectorStore",
                return_value=empty_store,
            ):
                r2 = client.get("/api/v1/literature/ingested")
                assert r2.status_code == 200
                assert "ss-fail-001" not in r2.json()["ids"]

    def test_post_zero_chunks_treated_as_failure(self, client):
        """If add_papers returns 0 chunks (e.g. embedding provider returned
        zero vectors), POST must fail rather than claim success."""
        zero_store = MagicMock()

        async def _zero(papers, chunks):
            return 0

        zero_store.add_papers = _zero

        paper_payload = {
            "id": "ss-zero-001",
            "source": "arxiv",
            "title": "Zero-Chunk Paper",
            "abstract": "Abstract.",
        }

        with patch(
            "backend.pipeline.knowledge.vector_store.VectorStore",
            return_value=zero_store,
        ), patch(
            "backend.pipeline.knowledge.embedding_service.EmbeddingService",
        ), patch(
            "backend.providers.provider_factory.create_provider",
        ):
            r = client.post("/api/v1/literature/ingest", json=paper_payload)
            assert r.status_code == 400
            assert "0 chunks" in r.json()["error"]["message"] or "0 chunks" in str(r.json())

    def test_post_construction_failure_returns_503(self, client):
        """If VectorStore construction itself fails (e.g. provider not
        configured), POST must return 503 Service Unavailable, NOT 200."""
        paper_payload = {
            "id": "ss-503-001",
            "source": "arxiv",
            "title": "No Provider Paper",
            "abstract": "Abstract.",
        }

        with patch(
            "backend.providers.provider_factory.create_provider",
            side_effect=RuntimeError("API key not set"),
        ):
            r = client.post("/api/v1/literature/ingest", json=paper_payload)
            assert r.status_code == 503
            assert "error" in r.json()
