"""Shared utility for extracting structured JSON from LLM responses.

LLM providers frequently return JSON wrapped in markdown code fences
(```json ... ```) or with leading/trailing text. This module provides
a single, well-tested extraction function that handles all known patterns.

Repair flow (in order):
    1. Direct json.loads
    2. Fence stripping / mechanical normalization
    3. Bracket matching
    4. (async) LLMRepairService — only after deterministic repair fails
    5. Schema validation on repaired output

Usage:
    from backend.pipeline.utils.json_extraction import extract_json

    data = extract_json(llm_response_text)
    # Returns dict or list; raises JsonExtractionError on failure.

    # Async version with LLM repair fallback:
    data = await extract_json_with_llm_repair(text, gateway, run_id=...)
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
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


@dataclass
class RepairLog:
    """Tracks repair attempt details for observability."""
    repair_attempted: bool = False
    repair_method: str = ""  # "mechanical" | "llm_repair" | "failed" | ""
    enforcement_applied: bool = False
    routed_model: str = ""
    actual_model: str = ""
    schema_valid_after_repair: bool = False
    degraded: bool = False
    repair_error: str = ""
    original_invalid_json: str = ""
    llm_repair_log_fields: dict = field(default_factory=dict)


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

    # Strategy 4.5: Try to repair truncated JSON by adding closing brackets
    repaired = _repair_truncated_json(text)
    if repaired is not None:
        return repaired

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


def _repair_truncated_json(text: str) -> dict | list | None:
    """Try to repair truncated JSON by adding missing closing brackets.

    Finds the start of a JSON object/array and attempts to balance brackets.
    """
    import json
    # Find first { or [
    start_idx = -1
    for i, c in enumerate(text):
        if c in '{[':
            start_idx = i
            break
    if start_idx < 0:
        return None

    snippet = text[start_idx:].strip()

    # Count open vs close brackets
    open_braces = snippet.count('{')
    close_braces = snippet.count('}')
    open_brackets = snippet.count('[')
    close_brackets = snippet.count(']')

    # Try progressively adding closing characters
    for fix in ["]}" * max(0, open_braces - close_braces + max(0, open_brackets - close_brackets)),
                "\n}" + "\n]" * max(0, open_brackets - close_brackets),
                "\n}]\n}",
                "\n}\n]",
                "\n}]\n}",
    ]:
        # Actually, let's be smarter: add exactly what's missing
        pass

    # Simple approach: find the last complete value and close from there
    # Try adding brackets from the end
    suffixes = []
    missing_braces = open_braces - close_braces
    missing_brackets = open_brackets - close_brackets

    # Build suffix: close any open strings, arrays, objects
    # First close any unclosed string
    in_string = False
    escape_next = False
    for c in snippet:
        if escape_next:
            escape_next = False
            continue
        if c == '\\':
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string

    if in_string:
        suffixes.append('"')
    for _ in range(max(0, missing_brackets)):
        suffixes.append(']')
    for _ in range(max(0, missing_braces)):
        suffixes.append('}')

    trial = snippet + ''.join(suffixes)
    try:
        result = json.loads(trial)
        if isinstance(result, (dict, list)):
            return result
    except (json.JSONDecodeError, Exception):
        pass

    # Last resort: try to find the last complete key-value pair
    # Find last `}` before truncation and add outer closing brackets
    last_close = snippet.rfind('}')
    if last_close > 0:
        # Find what brackets are still open at that point
        sub = snippet[:last_close + 1]
        sub_open_b = sub.count('{')
        sub_close_b = sub.count('}')
        sub_open_sq = sub.count('[')
        sub_close_sq = sub.count(']')
        fix = ''
        if in_string:
            # Find if there's a string boundary issue
            pass
        fix += ']' * max(0, sub_open_sq - sub_close_sq)
        fix += '}' * max(0, sub_open_b - sub_close_b)
        trial2 = sub + fix
        try:
            result = json.loads(trial2)
            if isinstance(result, (dict, list)):
                return result
        except (json.JSONDecodeError, Exception):
            pass

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


async def extract_json_with_llm_repair(
    text: str,
    gateway: Any = None,
    *,
    schema: dict | None = None,
    schema_hint: str = "",
    run_id: str = "",
    strict: bool = False,
) -> tuple[dict | list, RepairLog]:
    """Extract JSON with LLM repair as final fallback.

    Flow:
        raw LLM output
          → extract_json (mechanical: direct parse, fence, brackets)
          → if mechanical succeeds: return with repair_method="mechanical"
          → if mechanical fails AND gateway provided:
              → LLMRepairService.repair_json (gateway-backed, stage=repair)
              → if schema provided, validate repaired output
              → return repaired result with repair_method="llm_repair"
          → if all fail: return ({} or raise) with repair_method="failed"

    Args:
        text: Raw LLM response text.
        gateway: LLMGateway instance for LLM repair. If None, skips LLM repair.
        schema: Optional JSON schema for validation after repair.
        schema_hint: Human-readable schema description for the LLM.
        run_id: Pipeline run ID for tracing.
        strict: If True, raise JsonExtractionError on total failure.

    Returns:
        Tuple of (parsed_data, RepairLog) for observability.
    """
    log = RepairLog(original_invalid_json=text[:500])

    # Step 1: Try mechanical extraction first
    try:
        result = extract_json(text, strict=True)
        log.repair_method = "mechanical"
        log.schema_valid_after_repair = True  # mechanical extraction always returns parseable JSON
        return result, log
    except (JsonExtractionError, Exception):
        pass  # Fall through to LLM repair

    # Step 2: LLM repair (if gateway provided)
    if gateway is not None:
        log.repair_attempted = True
        try:
            from backend.pipeline.gateway.llm_repair_and_query import LLMRepairService

            repair_svc = LLMRepairService(gateway)
            repaired = await repair_svc.repair_json(
                broken_json=text,
                schema_hint=schema_hint,
                run_id=run_id,
            )

            if repaired is not None:
                # Schema validation (if provided)
                schema_ok = True
                if schema:
                    schema_ok = _validate_against_schema(repaired, schema)

                log.repair_method = "llm_repair"
                log.schema_valid_after_repair = schema_ok

                # Capture enforcement fields from gateway call log
                call_log = gateway.get_call_log(limit=5)
                repair_calls = [c for c in call_log if c.get("stage") == "repair"]
                if repair_calls:
                    last = repair_calls[-1]
                    log.enforcement_applied = last.get("enforcement_applied", False)
                    log.routed_model = last.get("routed_model", "")
                    log.actual_model = last.get("model", "")
                    log.degraded = last.get("degraded", False)
                    log.llm_repair_log_fields = {
                        "enforcement_applied": log.enforcement_applied,
                        "routed_model": log.routed_model,
                        "actual_model": log.actual_model,
                        "certification_status": last.get("certification_status", ""),
                        "stage_eligibility": last.get("stage_eligibility", ""),
                        "hard_gate_failures": last.get("hard_gate_failures", []),
                        "degraded": log.degraded,
                    }

                if schema_ok:
                    logger.info(
                        "LLM repair succeeded (enforced=%s, model=%s)",
                        log.enforcement_applied, log.routed_model,
                    )
                    return repaired, log
                else:
                    logger.warning("LLM repair output failed schema validation")
                    log.repair_error = "schema_validation_failed"
            else:
                log.degraded = True
                log.repair_error = "llm_repair_returned_none"
                logger.warning("LLM repair returned None (possibly degraded)")

        except Exception as e:
            log.repair_error = f"llm_repair_exception: {e}"
            logger.warning("LLM repair failed: %s", e)
    else:
        log.repair_error = "no_gateway_provided"

    # Step 3: Total failure
    log.repair_method = "failed"
    if strict:
        raise JsonExtractionError(text, "All repair methods failed")
    logger.warning("All JSON repair methods failed, returning empty dict")
    return {}, log


def _validate_against_schema(data: dict | list, schema: dict) -> bool:
    """Basic schema validation. Returns True if data matches expected structure.

    This is NOT a full JSON Schema validator — it checks:
    - Type matches (object/array)
    - Required properties exist
    - Property types match
    """
    try:
        schema_type = schema.get("type", "object")

        # Type check
        if schema_type == "object" and not isinstance(data, dict):
            return False
        if schema_type == "array" and not isinstance(data, list):
            return False

        # Required properties
        if isinstance(data, dict):
            required = schema.get("required", [])
            for prop in required:
                if prop not in data:
                    logger.debug("Schema validation: missing required property '%s'", prop)
                    return False

            # Property type checks
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    expected_type = prop_schema.get("type")
                    if expected_type == "string" and not isinstance(data[prop_name], str) or expected_type == "number" and not isinstance(data[prop_name], (int, float)) or expected_type == "boolean" and not isinstance(data[prop_name], bool) or expected_type == "array" and not isinstance(data[prop_name], list) or expected_type == "object" and not isinstance(data[prop_name], dict):
                        return False

        return True
    except Exception as e:
        logger.debug("Schema validation error: %s", e)
        return False
