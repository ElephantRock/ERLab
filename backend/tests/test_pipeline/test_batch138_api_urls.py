"""BATCH-138 / TASK-01 — Verify externalized API URLs in config and literature sources.

Tests:
  TEST-138-01-01: config has crossref_api_url with correct default
  TEST-138-01-02: config has openalex_api_url with correct default
  TEST-138-01-03: config has semantic_scholar_api_url with correct default
  TEST-138-01-04: literature sources read URL from settings
"""

from unittest.mock import patch

from backend.config import Settings


class TestConfigApiUrls:
    """TEST-138-01-01 / 01-02 / 01-03 — new config fields with correct defaults."""

    def test_crossref_api_url_default(self) -> None:
        s = Settings()
        assert s.crossref_api_url == "https://api.crossref.org"

    def test_openalex_api_url_default(self) -> None:
        s = Settings()
        assert s.openalex_api_url == "https://api.openalex.org"

    def test_semantic_scholar_api_url_default(self) -> None:
        s = Settings()
        assert s.semantic_scholar_api_url == "https://api.semanticscholar.org/graph/v1"

    def test_crossref_api_url_override(self) -> None:
        s = Settings(crossref_api_url="https://custom.crossref.org")
        assert s.crossref_api_url == "https://custom.crossref.org"

    def test_openalex_api_url_override(self) -> None:
        s = Settings(openalex_api_url="https://custom.openalex.org")
        assert s.openalex_api_url == "https://custom.openalex.org"

    def test_semantic_scholar_api_url_override(self) -> None:
        s = Settings(semantic_scholar_api_url="https://custom.s2.org")
        assert s.semantic_scholar_api_url == "https://custom.s2.org"


class TestLiteratureSourcesReadSettings:
    """TEST-138-01-04 — literature sources read URL from settings."""

    def test_crossref_source_reads_settings(self) -> None:
        from backend.pipeline.literature.crossref_source import CrossRefSource, _get_api_base

        # Default reads from Settings
        base = _get_api_base()
        assert base == "https://api.crossref.org"

        # Constructor accepts explicit override
        src = CrossRefSource(api_base="https://custom.crossref.org")
        assert src._client.base_url == "https://custom.crossref.org"

    def test_openalex_source_reads_settings(self) -> None:
        from backend.pipeline.literature.openalex_source import OpenAlexSource, _get_api_base

        base = _get_api_base()
        assert base == "https://api.openalex.org"

        src = OpenAlexSource(api_base="https://custom.openalex.org")
        assert src._client.base_url == "https://custom.openalex.org"

    def test_semantic_scholar_source_reads_settings(self) -> None:
        from backend.pipeline.literature.semantic_scholar import (
            SemanticScholarSource,
            _get_api_base,
        )

        base = _get_api_base()
        assert base == "https://api.semanticscholar.org/graph/v1"

        src = SemanticScholarSource(api_base="https://custom.s2.org")
        assert src._client.base_url == "https://custom.s2.org"

    def test_crossref_source_uses_settings_override(self) -> None:
        """Verify CrossRef picks up a custom config value via settings."""
        from backend.pipeline.literature.crossref_source import _get_api_base

        with patch("backend.config.get_settings") as mock_gs:
            mock_gs.return_value.crossref_api_url = "https://override.crossref.org"
            assert _get_api_base() == "https://override.crossref.org"

    def test_pdf_service_reads_settings(self) -> None:
        """PDFService reads s1_parser_url from settings when not provided."""
        from backend.pipeline.ingestion.pdf_service import PDFService

        svc = PDFService()
        # Should have read from settings — default is http://localhost:8000
        assert svc._s1_url == "http://localhost:8000"

        # Explicit override wins
        svc2 = PDFService(s1_parser_url="http://custom:9000")
        assert svc2._s1_url == "http://custom:9000"
