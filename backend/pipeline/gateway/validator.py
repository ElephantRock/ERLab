"""Output validator — validates LLM output with confidence penalties.

Design principle: mechanical repair is ok, semantic repair is not.
- Missing bracket → fix it
- Score out of bounds → clamp + penalty
- Hallucinated citation → flag, do NOT silently remove

The validator does NOT become a laundering mechanism.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an LLM output."""

    valid: bool
    content: str | dict  # possibly repaired content
    confidence_penalty: float  # 0.0 = no penalty, 0.5 = severe
    warnings: list[str] = field(default_factory=list)
    repairs: list[str] = field(default_factory=list)  # what was fixed

    @property
    def was_repaired(self) -> bool:
        return len(self.repairs) > 0


class OutputValidator:
    """Validates LLM output with tiered repair semantics.

    Tier 1 (safe repair): JSON syntax, missing brackets
    Tier 2 (clamp + penalty): out-of-range scores
    Tier 3 (flag only): hallucinated citations, unsupported claims
    """

    # Score bounds for common scoring fields
    SCORE_FIELDS = {
        "similarity": (0.0, 1.0),
        "score": (0.0, 1.0),
        "confidence": (0.0, 1.0),
        "novelty": (0.0, 1.0),
        "feasibility": (0.0, 10.0),
        "overall": (0.0, 1.0),
    }

    def validate_structured(
        self,
        output: dict,
        schema: dict | None = None,
    ) -> ValidationResult:
        """Validate a structured (dict) output.

        Args:
            output: The parsed LLM output.
            schema: Expected JSON schema (for required field checking).

        Returns:
            ValidationResult with any repairs applied.
        """
        warnings: list[str] = []
        repairs: list[str] = []
        penalty = 0.0
        result = dict(output)

        # Check required fields from schema
        if schema:
            required = schema.get("required", [])
            for key in required:
                if key not in result:
                    warnings.append(f"Missing required field: {key}")
                    penalty += 0.1
                elif result[key] is None:
                    warnings.append(f"Null value in required field: {key}")
                    penalty += 0.05

        # Clamp out-of-range scores
        for field_name, (min_val, max_val) in self.SCORE_FIELDS.items():
            if field_name in result:
                val = result[field_name]
                if isinstance(val, (int, float)):
                    if val < min_val or val > max_val:
                        original = val
                        clamped = max(min_val, min(max_val, val))
                        result[field_name] = clamped
                        repairs.append(
                            f"Clamped {field_name}: {original} → {clamped}"
                        )
                        penalty += 0.2  # significant penalty for out-of-range

        # Check for empty string fields
        for key, val in result.items():
            if isinstance(val, str) and not val.strip():
                warnings.append(f"Empty string in field: {key}")
                penalty += 0.05

        return ValidationResult(
            valid=len(warnings) == 0 and penalty < 0.3,
            content=result,
            confidence_penalty=min(0.5, penalty),
            warnings=warnings,
            repairs=repairs,
        )

    def validate_text(
        self,
        output: str,
        min_length: int = 0,
    ) -> ValidationResult:
        """Validate a text output.

        Args:
            output: The raw text output from the LLM.
            min_length: Minimum expected length.

        Returns:
            ValidationResult.
        """
        warnings: list[str] = []

        if not output or not output.strip():
            warnings.append("Empty output")
            return ValidationResult(
                valid=False,
                content=output,
                confidence_penalty=0.5,
                warnings=warnings,
            )

        if len(output) < min_length:
            warnings.append(f"Output too short: {len(output)} < {min_length} chars")

        return ValidationResult(
            valid=len(warnings) == 0,
            content=output,
            confidence_penalty=0.05 * len(warnings),
            warnings=warnings,
        )

    def validate_citations(
        self,
        text: str,
        valid_citation_ids: set[str],
    ) -> tuple[list[str], list[str]]:
        """Check citations in text against a closed set of valid IDs.

        Returns:
            (valid_citations, invalid_citations) — both lists of citation strings.
        """
        # Common citation patterns: [1], (Author, Year), [PAPER_014], etc.
        bracket_cites = re.findall(r'\[(\d+)\]', text)
        author_cites = re.findall(r'\(([A-Z][a-z]+(?:\s+et\s+al\.?)?(?:,\s*\d{4})?)\)', text)

        valid_found: list[str] = []
        invalid_found: list[str] = []

        # Bracket citations — check if the index maps to a valid ID
        for cite in bracket_cites:
            cite_str = f"[{cite}]"
            if cite in valid_citation_ids or cite_str in valid_citation_ids:
                valid_found.append(cite_str)
            else:
                invalid_found.append(cite_str)

        # Author citations — can't validate against IDs without a mapping
        # These are always flagged as potentially unverifiable
        for cite in author_cites:
            invalid_found.append(f"({cite})")

        return valid_found, invalid_found

    def repair_json(self, text: str) -> tuple[dict | None, list[str]]:
        """Try to repair malformed JSON from LLM output.

        Only performs mechanical repairs:
        - Missing closing bracket
        - Trailing comma
        - Extract JSON from markdown code fence

        Returns:
            (parsed_dict, repairs_made)
        """
        repairs: list[str] = []

        # Try direct parse
        try:
            return json.loads(text), []
        except json.JSONDecodeError:
            pass

        # Try extracting from code fence
        fence_match = re.search(r'```(?:json)?\s*\n(.*?)```', text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()
            repairs.append("Extracted JSON from code fence")
            try:
                return json.loads(text), repairs
            except json.JSONDecodeError:
                pass

        # Try fixing common issues
        fixed = text.strip()

        # Remove trailing comma before closing brace/bracket
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
        if fixed != text:
            repairs.append("Removed trailing commas")
            try:
                return json.loads(fixed), repairs
            except json.JSONDecodeError:
                pass

        # Add missing closing bracket
        open_braces = fixed.count('{') - fixed.count('}')
        open_brackets = fixed.count('[') - fixed.count(']')

        if open_braces > 0:
            fixed += '}' * open_braces
            repairs.append(f"Added {open_braces} closing brace(s)")
        if open_brackets > 0:
            fixed += ']' * open_brackets
            repairs.append(f"Added {open_brackets} closing bracket(s)")

        try:
            return json.loads(fixed), repairs
        except json.JSONDecodeError:
            return None, repairs
