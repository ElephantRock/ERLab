"""Shared utility for extracting structured JSON from LLM responses.

LLM providers frequently return JSON wrapped in markdown code fences
(```json ... ```) or with leading/trailing text. This module provides
a single, well-tested extraction function that handles all known patterns.

Usage:
    from backend.pipeline.utils.json_extraction import extract_json

    data = extract_json(llm_response_text)
    # Returns dict or list; raises JsonExtractionError on failure.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class JsonExtractionError(ValueError):
    """Raised when JSON cannot be extracted from LLM response text."""

    def __init__(self, text: str, reason: str = ""):
        self.raw_text = text[:200]
        super().__init__(
            f"Could not extract JSON from LLM response: {reason}. "
            f"Text preview: {text[:100]!r}..."
        )


def extract_json(text: str, *, strict: bool = False) -> dict | list:
    """Extract and parse JSON from an LLM response string.

    Tries these strategies in order:
    1. Direct parse (text is already valid JSON)
    2. Extract from ```json ... ``` code fence
    3. Extract from ``` ... ``` code fence
    4. Find first { ... } or [ ... ] via regex
    5. (if strict=False) Return empty dict on total failure

    Args:
        text: Raw LLM response text.
        strict: If True, raise JsonExtractionError on failure.
                If False, return {} on failure with a warning log.

    Returns:
        Parsed dict or list.

    Raises:
        JsonExtractionError: If strict=True and no JSON found.
    """
    if not text or not text.strip():
        if strict:
            raise JsonExtractionError(text, "Empty response")
        logger.warning("Empty LLM response — returning empty dict")
        return {}

    text = text.strip()

    # Strategy 1: Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, (dict, list)):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: ```json ... ``` code fence
    json_fence = _extract_code_fence(text, "json")
    if json_fence is not None:
        try:
            result = json.loads(json_fence)
            if isinstance(result, (dict, list)):
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 3: ``` ... ``` code fence (no language tag)
    plain_fence = _extract_code_fence(text, None)
    if plain_fence is not None:
        try:
            result = json.loads(plain_fence)
            if isinstance(result, (dict, list)):
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 4: Regex — find first { ... } or [ ... ]
    bracket_result = _extract_by_brackets(text)
    if bracket_result is not None:
        return bracket_result

    # Strategy 5: Failure
    if strict:
        raise JsonExtractionError(text, "No JSON found via any strategy")
    logger.warning("Could not extract JSON from LLM response (returning empty dict): %s", text[:100])
    return {}


def _extract_code_fence(text: str, lang: str | None) -> str | None:
    """Extract content from a markdown code fence.

    Args:
        text: Full response text.
        lang: Language tag to match (e.g., "json"), or None for any fence.

    Returns:
        Fence content or None.
    """
    if lang:
        pattern = rf"```{lang}\s*\n?(.*?)```"
    else:
        pattern = r"```\s*\n?(.*?)```"

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _extract_by_brackets(text: str) -> dict | list | None:
    """Find the first valid JSON object or array using bracket matching.

    Returns:
        Parsed dict/list or None.
    """
    # Find first [ or { — try whichever appears first
    bracket_pairs = [("[", "]"), ("{", "}")]
    candidates = []
    for start_char, end_char in bracket_pairs:
        idx = text.find(start_char)
        if idx != -1:
            candidates.append((idx, start_char, end_char))
    candidates.sort()

    for _, start_char, end_char in candidates:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue

        # Find matching close bracket
        depth = 0
        in_string = False
        escape = False

        for i in range(start_idx, len(text)):
            ch = text[i]

            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue

            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx : i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, (dict, list)):
                            return result
                    except json.JSONDecodeError:
                        break  # Try next start_char

    return None
