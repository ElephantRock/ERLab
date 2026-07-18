"""Tests for CrossRefSource wrapper behavior.

Verifies that the source correctly:
- Parses CrossRef API responses into Paper/SearchResult objects
- Handles empty / malformed responses gracefully
- Strips HTML tags from abstracts
- Extracts authors, year, DOI, venue, citation count
- Respects the limit parameter
- Does not crash on network errors (returns empty list)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.pipeline.literature.crossref_source import CrossRefSource
from backend.pipeline.literature.models import Paper, SearchResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CROSSREF_RESPONSE = {
    "status": "ok",
    "message": {
        "items": [
            {
                "DOI": "10.1234/test.001",
                "title": ["Attention Is All You Need"],
                "author": [
                    {"given": "Ashish", "family": "Vaswani"},
                    {"given": "Noam", "family": "Shazeer"},
                ],
                "published-print": {"date-parts": [[2017, 6, 12]]},
                "abstract": "<jats:p>We propose a <jats:italic>new</jats:italic> architecture.</jats:p>",
                "container-title": ["Advances in Neural Information Processing Systems"],
                "is-referenced-by-count": 90000,
            },
            {
                "DOI": "10.1234/test.002",
                "title": ["BERT: Pre-training of Deep Bidirectional Transformers"],
                "author": [{"given": "Jacob", "family": "Devlin"}],
                "published-online": {"date-parts": [[2018, 10, 11]]},
                "abstract": None,
                "container-title": ["arXiv preprint arXiv:1810.04805"],
                "is-referenced-by-count": 50000,
            },
            {
                # Paper with no title — should be skipped
                "DOI": "10.1234/test.003",
                "title": [],
                "author": [],
                "is-referenced-by-count": 0,
            },
        ],
        "total-results": 3,
    },
}


def _make_mock_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = data
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock,
        )
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrossRefSearch:
    """Tests for CrossRefSource.search()."""

    @pytest.fixture
    def source(self) -> CrossRefSource:
        """Create a CrossRefSource with a mocked HTTP client."""
        s = CrossRefSource(mailto="test@example.com")
        s._client = MagicMock(spec=httpx.AsyncClient)
        return s

    @pytest.mark.asyncio
    async def test_basic_search_returns_results(self, source: CrossRefSource):
        """Valid CrossRef response produces SearchResult objects."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("transformer attention", limit=5)

        assert outcome.status == "success"
        assert outcome.attempt_count >= 1
        assert len(outcome.results) == 2  # third item has no title → skipped
        assert all(isinstance(r, SearchResult) for r in outcome.results)
        assert all(r.source == "crossref" for r in outcome.results)

    @pytest.mark.asyncio
    async def test_paper_fields_parsed_correctly(self, source: CrossRefSource):
        """Paper fields are extracted from CrossRef JSON correctly."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("transformer attention", limit=5)

        paper = outcome.results[0].paper
        assert paper.title == "Attention Is All You Need"
        assert paper.doi == "10.1234/test.001"
        assert paper.year == 2017
        assert paper.source == "crossref"
        assert paper.citation_count == 90000
        assert paper.venue == "Advances in Neural Information Processing Systems"
        assert len(paper.authors) == 2
        assert paper.authors[0].name == "Ashish Vaswani"

    @pytest.mark.asyncio
    async def test_html_tags_stripped_from_abstract(self, source: CrossRefSource):
        """JATS/XML tags in abstracts are stripped."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("transformer attention", limit=5)

        # First paper has JATS tags in abstract
        assert "We propose a new architecture." == outcome.results[0].paper.abstract
        assert "<jats:" not in outcome.results[0].paper.abstract

    @pytest.mark.asyncio
    async def test_paper_without_title_skipped(self, source: CrossRefSource):
        """Items with empty title list are skipped."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("anything", limit=10)

        titles = [r.paper.title for r in outcome.results]
        assert "" not in titles

    @pytest.mark.asyncio
    async def test_limit_respected(self, source: CrossRefSource):
        """The limit parameter caps the number of results."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("anything", limit=1)
        assert len(outcome.results) == 1

    @pytest.mark.asyncio
    async def test_empty_response(self, source: CrossRefSource):
        """Empty items list returns empty results."""
        empty_resp = {"message": {"items": []}}
        source._client.get = AsyncMock(
            return_value=_make_mock_response(empty_resp)
        )

        outcome = await source.search("anything", limit=5)
        assert outcome.status == "success"
        assert outcome.results == []

    @pytest.mark.asyncio
    async def test_network_error_returns_empty(self, source: CrossRefSource):
        """Network errors return a failed outcome with empty results, not crash."""
        source._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        outcome = await source.search("anything", limit=5)
        assert outcome.status == "failed"
        assert outcome.results == []
        assert outcome.attempt_count >= 1
        assert outcome.error_detail is not None

    @pytest.mark.asyncio
    async def test_http_error_returns_empty(self, source: CrossRefSource):
        """HTTP 4xx/5xx errors return a failed outcome with empty results."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response({}, status_code=429)
        )

        outcome = await source.search("anything", limit=5)
        assert outcome.status == "failed"
        assert outcome.results == []
        assert outcome.attempt_count >= 1
        assert outcome.error_detail is not None

    @pytest.mark.asyncio
    async def test_year_filter_applied(self, source: CrossRefSource):
        """Year filters are added to query params."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        await source.search("anything", limit=5, year_from=2020, year_to=2024)

        call_args = source._client.get.call_args
        params = call_args.kwargs.get("params", {})
        assert "from-pub-date:2020" in params.get("filter", "")
        assert "until-pub-date:2024" in params.get("filter", "")

    @pytest.mark.asyncio
    async def test_null_abstract_handled(self, source: CrossRefSource):
        """Paper with null abstract gets empty string, not crash."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response(CROSSREF_RESPONSE)
        )

        outcome = await source.search("anything", limit=5)

        # Second paper has abstract=None
        paper2 = outcome.results[1].paper
        assert paper2.abstract == ""


class TestCrossRefGetPaper:
    """Tests for CrossRefSource.get_paper()."""

    @pytest.fixture
    def source(self) -> CrossRefSource:
        s = CrossRefSource(mailto="test@example.com")
        s._client = MagicMock(spec=httpx.AsyncClient)
        return s

    @pytest.mark.asyncio
    async def test_get_paper_by_doi(self, source: CrossRefSource):
        """get_paper retrieves a single paper by DOI."""
        resp = {
            "message": {
                "DOI": "10.1234/test.001",
                "title": ["A Test Paper"],
                "is-referenced-by-count": 42,
            }
        }
        source._client.get = AsyncMock(
            return_value=_make_mock_response(resp)
        )

        paper = await source.get_paper("10.1234/test.001")

        assert paper is not None
        assert paper.title == "A Test Paper"
        assert paper.doi == "10.1234/test.001"
        assert paper.citation_count == 42

    @pytest.mark.asyncio
    async def test_get_paper_not_found(self, source: CrossRefSource):
        """get_paper returns None on error."""
        source._client.get = AsyncMock(
            return_value=_make_mock_response({}, status_code=404)
        )

        paper = await source.get_paper("invalid-doi")
        assert paper is None
