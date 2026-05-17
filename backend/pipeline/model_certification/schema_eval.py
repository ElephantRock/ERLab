"""Schema compliance evaluation.

Tests whether a model can produce valid JSON matching specific schemas.
Tracks three layers of compliance:
  1. raw_json_valid_rate      — parseable without any repair
  2. recoverable_json_rate    — parseable after fence-stripping
  3. schema_valid_rate        — passes JSON Schema validation (after repair)
  4. schema_valid_after_repair_rate — final valid rate after repair pipeline
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Number of cases per schema
_CASES_PER_SCHEMA = 5


@dataclass
class SchemaEvalResult:
    """Result of schema compliance evaluation."""

    total_cases: int = 0

    # Three-layer JSON compliance
    raw_json_valid_rate: float = 0.0         # parseable without any repair
    recoverable_json_rate: float = 0.0       # parseable after fence-stripping
    schema_valid_rate: float = 0.0           # passes JSON Schema (after repair)

    # Additional metrics
    required_field_completion: float = 0.0
    markdown_contamination_rate: float = 0.0
    truncation_rate: float = 0.0

    # Repair-adjusted metrics
    repair_attempted_count: int = 0
    repair_success_rate: float = 0.0
    schema_valid_after_repair_rate: float = 0.0

    # Native JSON mode support (from manifest, not tested)
    native_json_mode_support: bool = False

    # Structured output (response_format json_schema) results
    structured_schema_valid_rate: float = 0.0
    structured_total_cases: int = 0
    structured_failures: list[dict[str, Any]] = field(default_factory=list)

    # Per-schema breakdown
    per_schema: dict[str, dict[str, float]] = field(default_factory=dict)

    # Detailed failures
    failures: list[dict[str, Any]] = field(default_factory=list)


async def run_schema_eval(
    provider: object,  # LLMProvider
    model_id: str,
    schema_dir: str | Path,
    supports_json_mode: bool = False,
    cases_per_schema: int = _CASES_PER_SCHEMA,
) -> SchemaEvalResult:
    """Run schema compliance tests.

    For each JSON schema file in schema_dir:
      1. Load the schema
      2. Generate N prompts asking the model to produce matching JSON
      3. Evaluate raw JSON validity, recoverability, and schema compliance
      4. Track repair-adjusted metrics
      5. If provider supports structured output, also run structured eval
    """
    schema_dir = Path(schema_dir)
    result = SchemaEvalResult(
        native_json_mode_support=supports_json_mode,
    )

    # Find schema files
    schema_files = sorted(schema_dir.glob("*.schema.json"))
    if not schema_files:
        logger.warning("No schema files found in %s", schema_dir)
        return result

    try:
        import jsonschema as _js
        has_jsonschema = True
    except ImportError:
        has_jsonschema = False
        logger.warning("jsonschema not installed — schema validation skipped")

    # Check for structured output support
    has_structured = hasattr(provider, "structured_complete") and hasattr(provider, "supports_structured_output")
    if has_structured:
        logger.info("Provider supports structured output — running both prompted and structured eval")

    total_raw_valid = 0
    total_recoverable = 0
    total_schema_valid = 0
    total_fields_required = 0
    total_fields_present = 0
    total_markdown = 0
    total_truncated = 0
    total_cases = 0
    total_repair_attempted = 0
    total_repair_success = 0

    # Structured-output counters
    structured_total = 0
    structured_parse_valid = 0
    structured_schema_valid = 0
    structured_failures: list[dict[str, Any]] = []

    for schema_file in schema_files:
        schema_name = schema_file.stem.replace(".schema", "")
        schema = json.loads(schema_file.read_text(encoding="utf-8"))

        schema_raw = 0
        schema_recoverable = 0
        schema_valid = 0
        schema_cases = 0

        # Structured per-schema
        struct_schema_cases = 0
        struct_schema_valid = 0

        prompt = _build_schema_prompt(schema, schema_name)

        for case_idx in range(cases_per_schema):
            total_cases += 1
            schema_cases += 1
            case_result: dict[str, Any] = {
                "schema": schema_name,
                "case": case_idx,
            }

            try:
                response = await provider.complete(
                    prompt=prompt,
                    max_tokens=2000,
                    temperature=0.3,
                )

                text = _extract_text(response)
                if not text or not text.strip():
                    case_result["error"] = "Empty response"
                    total_truncated += 1
                    result.failures.append(case_result)
                    continue

                text = text.strip()

                # Check for markdown contamination
                has_fences = text.startswith("```")
                if has_fences:
                    total_markdown += 1
                    total_repair_attempted += 1

                # Try raw parse
                raw_valid = False
                try:
                    json.loads(text)
                    raw_valid = True
                    total_raw_valid += 1
                    schema_raw += 1
                except json.JSONDecodeError:
                    pass

                # Try after fence stripping
                cleaned = _strip_markdown_fences(text)
                recovered = False
                if not raw_valid:
                    try:
                        json.loads(cleaned)
                        recovered = True
                    except json.JSONDecodeError:
                        pass

                if raw_valid or recovered:
                    total_recoverable += 1
                    schema_recoverable += 1
                    if recovered and not raw_valid:
                        total_repair_success += 1

                # Schema validation
                try:
                    parsed = json.loads(cleaned)
                    if isinstance(parsed, dict):
                        # Count required fields
                        required = schema.get("required", [])
                        if required:
                            total_fields_required += len(required)
                            present = sum(1 for f in required if f in parsed)
                            total_fields_present += present

                        # Validate against schema
                        if has_jsonschema:
                            _js.validate(instance=parsed, schema=schema)
                        else:
                            # Basic validation: check required fields
                            missing = [
                                f for f in schema.get("required", [])
                                if f not in parsed
                            ]
                            if missing:
                                raise ValueError(f"Missing: {missing}")

                        total_schema_valid += 1
                        schema_valid += 1
                except (json.JSONDecodeError, Exception) as e:
                    case_result["error"] = str(e)[:100]

                    # Detect truncation
                    if not text.rstrip().endswith("}"):
                        total_truncated += 1

            except Exception as e:
                case_result["error"] = f"Provider error: {str(e)[:100]}"

            if "error" in case_result:
                result.failures.append(case_result)

            # --- Structured output eval ---
            if has_structured:
                structured_total += 1
                struct_schema_cases += 1
                try:
                    struct_text = await provider.structured_complete(
                        prompt=prompt,
                        schema_name=schema_name,
                        schema=schema,
                        max_tokens=2000,
                        temperature=0.3,
                    )
                    if struct_text and struct_text.strip():
                        try:
                            json.loads(struct_text)
                            structured_parse_valid += 1
                            # Schema validation
                            try:
                                parsed = json.loads(struct_text)
                                if has_jsonschema:
                                    _js.validate(instance=parsed, schema=schema)
                                else:
                                    missing = [f for f in schema.get("required", []) if f not in parsed]
                                    if missing:
                                        raise ValueError(f"Missing: {missing}")
                                structured_schema_valid += 1
                                struct_schema_valid += 1
                            except Exception as e:
                                structured_failures.append({
                                    "schema": schema_name, "case": case_idx,
                                    "mode": "structured", "error": str(e)[:100],
                                })
                        except json.JSONDecodeError:
                            structured_failures.append({
                                "schema": schema_name, "case": case_idx,
                                "mode": "structured", "error": "JSON parse error",
                            })
                except Exception as e:
                    structured_failures.append({
                        "schema": schema_name, "case": case_idx,
                        "mode": "structured", "error": f"Request error: {str(e)[:100]}",
                    })

        # Per-schema breakdown (prompted)
        if schema_cases > 0:
            result.per_schema[schema_name] = {
                "raw_json_valid_rate": schema_raw / schema_cases,
                "recoverable_json_rate": schema_recoverable / schema_cases,
                "schema_valid_rate": schema_valid / schema_cases,
                "cases": schema_cases,
            }
            if has_structured and struct_schema_cases > 0:
                result.per_schema[schema_name]["structured_schema_valid_rate"] = (
                    struct_schema_valid / struct_schema_cases
                )
                result.per_schema[schema_name]["structured_cases"] = struct_schema_cases

    # Aggregate (prompted)
    result.total_cases = total_cases
    if total_cases > 0:
        result.raw_json_valid_rate = total_raw_valid / total_cases
        result.recoverable_json_rate = total_recoverable / total_cases
        result.schema_valid_rate = total_schema_valid / total_cases
        result.markdown_contamination_rate = total_markdown / total_cases
        result.truncation_rate = total_truncated / total_cases

        if total_repair_attempted > 0:
            result.repair_success_rate = total_repair_success / total_repair_attempted

        if total_fields_required > 0:
            result.required_field_completion = total_fields_present / total_fields_required

        # schema_valid_after_repair_rate = schema_valid (which used cleaned JSON)
        result.schema_valid_after_repair_rate = result.schema_valid_rate

    result.repair_attempted_count = total_repair_attempted

    # Structured output results
    if has_structured and structured_total > 0:
        result.structured_schema_valid_rate = structured_schema_valid / structured_total
        result.structured_total_cases = structured_total
        result.structured_failures = structured_failures
        logger.info(
            "Structured output eval: %d/%d schema valid (%.1f%%)",
            structured_schema_valid, structured_total,
            result.structured_schema_valid_rate * 100,
        )

    return result


def _build_schema_prompt(schema: dict, schema_name: str) -> str:
    """Build a prompt asking the model to produce JSON matching the schema."""
    required = schema.get("required", [])
    props = schema.get("properties", {})
    prop_desc = ", ".join(
        f'"{k}": ({v.get("type", "any")})'
        for k, v in props.items()
    )

    return (
        f"Return valid JSON matching this schema. "
        f"Schema name: {schema_name}. "
        f"Required fields: {required}. "
        f"Properties: {{{prop_desc}}}. "
        f"Return ONLY the JSON object, no other text."
    )


def _extract_text(response: Any) -> str:
    """Extract text from various response formats."""
    if hasattr(response, "text"):
        return response.text
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return response.get("text", response.get("content", ""))
    return str(response)


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences from response text."""
    if text.startswith("```"):
        lines = text.split("\n")
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
