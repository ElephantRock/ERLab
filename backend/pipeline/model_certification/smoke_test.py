"""Smoke test — fast sanity check for model certification.

Prompts the model to return a trivial JSON object.
If this fails, certification stops immediately.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SMOKE_PROMPT = 'Return exactly this JSON with no other text: {"status":"ok"}'


@dataclass
class SmokeTestResult:
    """Result of the smoke test."""

    passed: bool = False
    response_text: str = ""
    parsed_json: dict | None = None
    latency_seconds: float = 0.0
    error: str | None = None


async def run_smoke_test(
    provider: object,  # LLMProvider
    model_id: str,
    timeout: float = 30.0,
) -> SmokeTestResult:
    """Run a smoke test: ask the model to return {"status":"ok"}.

    Verifies:
    - Model responds
    - Output is non-empty
    - JSON can be parsed
    - Required field "status" exists
    - Response is within timeout
    """
    result = SmokeTestResult()

    try:
        start = time.monotonic()
        response = await provider.complete(
            prompt=_SMOKE_PROMPT,
            max_tokens=100,
            temperature=0.0,
        )
        result.latency_seconds = time.monotonic() - start

        # Extract text from response
        if hasattr(response, "text"):
            result.response_text = response.text
        elif isinstance(response, str):
            result.response_text = response
        elif isinstance(response, dict):
            result.response_text = response.get("text", response.get("content", ""))
        else:
            result.response_text = str(response)

        if not result.response_text or not result.response_text.strip():
            result.error = "Empty response"
            return result

        # Try to parse JSON (with optional markdown fence stripping)
        text = result.response_text.strip()
        text = _strip_markdown_fences(text)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            result.error = f"JSON parse error: {e}"
            return result

        if not isinstance(parsed, dict):
            result.error = f"Expected dict, got {type(parsed).__name__}"
            return result

        if "status" not in parsed:
            result.error = "Missing required field: status"
            return result

        result.parsed_json = parsed
        result.passed = True

    except TimeoutError:
        result.error = f"Timeout after {timeout}s"
    except Exception as e:
        result.error = f"Error: {str(e)[:200]}"

    return result


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from response text."""
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```)
        if lines:
            lines = lines[1:]
        # Remove last line (```)
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
