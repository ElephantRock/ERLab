"""Tests for academic source reordering (BATCH-74/TASK-04)."""

from unittest.mock import patch, MagicMock


class TestSourceReordering:
    def test_openalex_first_when_no_s2_key(self):
        """TEST-74-04-04: OpenAlex is first when no S2 API key."""
        mock_settings = MagicMock()
        mock_settings.semantic_scholar_api_key = None
        mock_settings.openalex_email = None

        with patch("backend.pipeline.literature.search_service.get_settings", return_value=mock_settings):
            # Need to reimport to trigger the function
            from backend.pipeline.literature.search_service import SearchService

            sources = SearchService._default_sources()

            assert sources[0].__class__.__name__ == "OpenAlexSource"
            assert sources[1].__class__.__name__ == "ArxivSource"
            assert sources[2].__class__.__name__ == "SemanticScholarSource"

    def test_s2_first_when_api_key_present(self):
        """TEST-74-04-05: S2 is first when API key is present."""
        mock_settings = MagicMock()
        mock_settings.semantic_scholar_api_key = "test-key-123"
        mock_settings.openalex_email = None

        with patch("backend.pipeline.literature.search_service.get_settings", return_value=mock_settings):
            from backend.pipeline.literature.search_service import SearchService

            sources = SearchService._default_sources()

            assert sources[0].__class__.__name__ == "SemanticScholarSource"
            assert sources[1].__class__.__name__ == "ArxivSource"
            assert sources[2].__class__.__name__ == "OpenAlexSource"
