"""Tests for Semantic Scholar 429 retry with exponential backoff.

BATCH-60/TASK-02 — Semantic Scholar Rate-Limit Retry with Backoff

TEST-60-02-01: Mock 429 → retry called, eventually returns []
TEST-60-02-02: Mock 429 then 200 → results returned after retry
TEST-60-02-03: Max retries (5) exceeded → returns [] without raising
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.pipeline.literature.semantic_scholar import SemanticScholarSource


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


def _make_429_response() -> httpx.Response:
    """Build a fake HTTP 429 response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 429
    response.text = "Rate limit exceeded"
    response.json.return_value = {"error": "Rate limit exceeded"}
    return response


def _make_429_error() -> httpx.HTTPStatusError:
    """Build an HTTPStatusError wrapping a 429 response."""
    resp = _make_429_response()
    return httpx.HTTPStatusError(
        message="Rate limit exceeded",
        request=MagicMock(spec=httpx.Request),
        response=resp,
    )


def _make_500_error() -> httpx.HTTPStatusError:
    """Build an HTTPStatusError wrapping a 500 response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 500
    resp.text = "Internal Server Error"
    return httpx.HTTPStatusError(
        message="Internal Server Error",
        request=MagicMock(spec=httpx.Request),
        response=resp,
    )


def _make_success_response(data: list[dict] | None = None) -> httpx.Response:
    """Build a fake HTTP 200 response with paper data."""
    if data is None:
        data = [
            {
                "paperId": "abc123",
                "title": "Test Paper",
                "abstract": "Abstract text",
                "year": 2024,
                "authors": [{"name": "Author One", "authorId": "a1"}],
                "citationCount": 10,
                "url": "https://example.com",
                "externalIds": {"DOI": "10.1234/test"},
                "venue": "ACL",
                "fieldsOfStudy": ["NLP"],
                "relevanceScore": 0.95,
            }
        ]
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"data": data, "total": len(data)}
    response.raise_for_status = MagicMock()
    return response


# ---------------------------------------------------------------------------
# TEST-60-02-01: Mock 429 → retry called, eventually returns []
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_429_all_retries_exhausted_returns_empty():
    """All requests return 429, retries exhausted → failed outcome."""
    source = SemanticScholarSource()

    error = _make_429_error()
    success_resp = _make_success_response()
    success_resp.raise_for_status.side_effect = error

    plan = source.build_query_plan("test query")
    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=success_resp
    ), patch("backend.pipeline.literature.semantic_scholar.asyncio.sleep", new_callable=AsyncMock):
        outcome = await source.execute_query_plan(
            plan,
            retry_max_retries=3,
            retry_base_delay=0.01,
            retry_max_delay=0.1,
        )

    assert outcome.status == "failed"
    assert outcome.results == []
    assert outcome.failure_category == "rate_limit"
    assert outcome.failure_code == "http_429"


# ---------------------------------------------------------------------------
# TEST-60-02-02: Mock 429 then 200 → results returned after retry
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_429_then_200_returns_results():
    """First request returns 429, second returns 200 → results returned."""
    source = SemanticScholarSource()

    error_429 = _make_429_error()
    fail_resp = _make_success_response()
    fail_resp.raise_for_status.side_effect = error_429

    success_resp = _make_success_response()

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fail_resp
        return success_resp

    with patch.object(
        source._client, "get", new_callable=AsyncMock, side_effect=mock_get
    ), patch(
        "backend.pipeline.literature.semantic_scholar.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        plan = source.build_query_plan("test query")
        outcome = await source.execute_query_plan(
            plan,
            retry_max_retries=5,
            retry_base_delay=0.01,
            retry_max_delay=0.1,
        )

    assert outcome.status == "success"
    assert len(outcome.results) == 1
    assert outcome.results[0].paper.title == "Test Paper"
    assert outcome.results[0].source == "semantic_scholar"
    assert outcome.attempt_count == 2  # one 429 + one success
    # Verify sleep was called once (for the single retry)
    mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# TEST-60-02-03: Max retries (5) exceeded → returns [] without raising
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_max_5_retries_exceeded_returns_empty():
    """Exactly 5 retries (6 total attempts), all 429 → returns []."""
    source = SemanticScholarSource()

    error_429 = _make_429_error()
    fail_resp = _make_success_response()
    fail_resp.raise_for_status.side_effect = error_429

    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=fail_resp
    ) as mock_get, patch(
        "backend.pipeline.literature.semantic_scholar.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        plan = source.build_query_plan("test query")
        outcome = await source.execute_query_plan(
            plan,
            retry_max_retries=5,
            retry_base_delay=0.01,
            retry_max_delay=0.1,
        )

    assert outcome.status == "failed"
    assert outcome.results == []
    assert outcome.failure_category == "rate_limit"
    assert outcome.failure_code == "http_429"
    # 6 total attempts: 1 initial + 5 retries
    assert mock_get.call_count == 6
    assert outcome.attempt_count == 6
    # 5 sleep calls (one per retry)
    assert mock_sleep.call_count == 5


# ---------------------------------------------------------------------------
# Additional: Non-429 errors are NOT retried
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_non_429_error_not_retried():
    """A 500 error is not retried — immediate return []."""
    source = SemanticScholarSource()

    error_500 = _make_500_error()
    fail_resp = _make_success_response()
    fail_resp.raise_for_status.side_effect = error_500

    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=fail_resp
    ) as mock_get, patch(
        "backend.pipeline.literature.semantic_scholar.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        plan = source.build_query_plan("test query")
        outcome = await source.execute_query_plan(plan)

    assert outcome.status == "failed"
    assert outcome.results == []
    assert outcome.failure_category == "provider_internal"
    assert outcome.failure_code == "http_500"
    # Only one attempt — no retries for non-429
    assert mock_get.call_count == 1
    assert outcome.attempt_count == 1
    mock_sleep.assert_not_called()
