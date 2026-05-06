"""Tests for arXiv HTTP 429 retry with exponential backoff.

BATCH-75/TASK-04 — arXiv Rate-Limit Retry with Backoff

TEST-75-04-01: 429 then 200 → retries and succeeds on second attempt
TEST-75-04-02: Persistent 429 → retries up to 3 times then gives up
TEST-75-04-03: Non-429 error (500) → no retry, immediate failure
TEST-75-04-04: Backoff delays are 5s, 15s, 30s (exponential)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.pipeline.literature.arxiv_source import ArxivSource


ARXIV_XML_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001</id>
    <title>Test Paper on AI</title>
    <summary>A test abstract about artificial intelligence.</summary>
    <author><name>Test Author</name></author>
    <published>2023-01-01T00:00:00Z</published>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>
"""


def _make_response(status_code: int, text: str = "") -> MagicMock:
    """Build a fake HTTP response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = text
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(spec=httpx.Request),
            response=response,
        )
    return response


# ---------------------------------------------------------------------------
# TEST-75-04-01: arXiv retries on 429 and succeeds on second attempt
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_429_then_200_returns_results():
    """First request returns 429, second returns 200 → results returned."""
    source = ArxivSource()

    resp_429 = _make_response(429, "Rate limit exceeded")
    resp_200 = _make_response(200, ARXIV_XML_RESPONSE)

    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return resp_429 if call_count == 1 else resp_200

    with patch.object(
        source._client, "get", new_callable=AsyncMock, side_effect=mock_get
    ), patch(
        "backend.pipeline.literature.arxiv_source.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        results = await source.search("artificial intelligence")

    assert len(results) > 0
    assert results[0].paper.title == "Test Paper on AI"


# ---------------------------------------------------------------------------
# TEST-75-04-02: arXiv retries up to 3 times then gives up on persistent 429
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_persistent_429_gives_up_after_3_retries():
    """All requests return 429 → retries 3 times then returns empty list."""
    source = ArxivSource()
    resp_429 = _make_response(429, "Rate limit exceeded")

    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=resp_429
    ) as mock_get, patch(
        "backend.pipeline.literature.arxiv_source.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        results = await source.search("quantum computing")

    assert results == []
    # 1 initial + 3 retries = 4 total GET attempts
    assert mock_get.call_count == 4


# ---------------------------------------------------------------------------
# TEST-75-04-03: arXiv does NOT retry on non-429 errors (e.g., 500)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_non_429_error_no_retry():
    """A 500 error is not retried — immediate return []."""
    source = ArxivSource()
    resp_500 = _make_response(500, "Internal Server Error")

    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=resp_500
    ) as mock_get, patch(
        "backend.pipeline.literature.arxiv_source.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        results = await source.search("machine learning")

    assert results == []
    # Only one GET attempt — no retries for non-429 errors
    assert mock_get.call_count == 1
    # Only the pre-request sleep(3), no backoff sleeps
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_once_with(3)


# ---------------------------------------------------------------------------
# TEST-75-04-04: Backoff delays are 5s, 15s, 30s (exponential)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_backoff_delays_are_5_15_30():
    """Backoff delays match [5, 15, 30] for the three retries."""
    source = ArxivSource()
    resp_429 = _make_response(429, "Rate limit exceeded")

    with patch.object(
        source._client, "get", new_callable=AsyncMock, return_value=resp_429
    ), patch(
        "backend.pipeline.literature.arxiv_source.asyncio.sleep",
        new_callable=AsyncMock,
    ) as mock_sleep:
        results = await source.search("deep learning")

    assert results == []

    # Collect all sleep call arguments
    sleep_args = [call.args[0] for call in mock_sleep.call_args_list]

    # First call is the pre-request delay (3s), then backoff delays [5, 15, 30]
    assert sleep_args == [3, 5, 15, 30]
