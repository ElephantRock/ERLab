"""ClaimRenderer — convert structured typed claims to prose with sidecar audit trail.

Deterministic rendering: the renderer applies correct markers based on claim type.
- background → plain text with [SOURCE-X]
- method_proposed_mechanism → "We propose..."
- method_claimed_benefit → "We hypothesize that..."
- hypothesis → "We hypothesize that..."
- expected_contribution → "We aim to..."
- evaluation_benchmark/metric → cite precedent or "We introduce..."

CRITICAL INVARIANT: No validated structure → no structured rendering.
If schema validation fails, the section degrades to prose_fallback.
"""

from __future__ import annotations

import logging

from backend.pipeline.gateway.claim_types import (
    CLAIM_TYPE_VALUES,
    ClaimType,
)

logger = logging.getLogger(__name__)


class ClaimIDGenerator:
    """Deterministic claim IDs. Code-generated, not LLM-invented.

    Generates: P0-method-C001, P0-eval-C001, P0-method-A001
    """

    def __init__(self, proposal_id: int):
        self._proposal_id = proposal_id
        self._claim_counters: dict[str, int] = {}
        self._assumption_counters: dict[str, int] = {}

    def next_claim_id(self, section: str) -> str:
        """Generate: P0-method-C001"""
        key = section[:20]
        self._claim_counters[key] = self._claim_counters.get(key, 0) + 1
        return f"P{self._proposal_id}-{key}-C{self._claim_counters[key]:03d}"

    def next_assumption_id(self, section: str) -> str:
        """Generate: P0-method-A001"""
        key = section[:20]
        self._assumption_counters[key] = self._assumption_counters.get(key, 0) + 1
        return f"P{self._proposal_id}-{key}-A{self._assumption_counters[key]:03d}"


class InvalidStructuredOutput(Exception):
    """Raised when structured output fails schema validation."""

    def __init__(self, section: str, reason: str = ""):
        self.section = section
        self.reason = reason
        super().__init__(f"Invalid structured output for {section}: {reason}")


class ClaimRenderer:
    """Convert structured typed claims to prose with sidecar audit trail."""

    # Type-specific rendering prefixes
    SPECULATIVE_PREFIXES = {
        ClaimType.METHOD_CLAIMED_BENEFIT.value: "We hypothesize that",
        ClaimType.HYPOTHESIS.value: "We hypothesize that",
        ClaimType.EXPECTED_CONTRIBUTION.value: "We aim to",
    }

    PROPOSAL_PREFIXES = {
        ClaimType.METHOD_PROPOSED_MECHANISM.value: "We propose",
        ClaimType.EVALUATION_PROTOCOL.value: "",
        ClaimType.EVALUATION_BENCHMARK.value: "",
        ClaimType.EVALUATION_METRIC.value: "",
    }

    def render_section(
        self,
        section_id: str,
        structured_output: dict,
        id_generator: ClaimIDGenerator,
    ) -> tuple[str, dict]:
        """Render structured claims to prose + sidecar.

        Args:
            section_id: The section identifier.
            structured_output: The LLM's structured claim output.
            id_generator: For deterministic claim IDs.

        Returns:
            (prose_text, sidecar_dict)

        Raises:
            InvalidStructuredOutput: If schema validation fails.
        """
        # 1. Schema validation — CRITICAL INVARIANT
        if not self._validate_schema(structured_output):
            raise InvalidStructuredOutput(section_id, "Schema validation failed")

        claims = structured_output.get("claims", [])
        assumptions_data = structured_output.get("assumptions", [])

        # 2. Normalize claim IDs (overwrite LLM-generated with deterministic)
        normalized_claims = []
        for claim in claims:
            claim = dict(claim)  # copy
            claim["claim_id"] = id_generator.next_claim_id(section_id)
            claim["section"] = section_id
            normalized_claims.append(claim)

        # 3. Normalize assumption IDs
        normalized_assumptions = []
        for assumption in assumptions_data:
            assumption = dict(assumption)
            assumption["assumption_id"] = id_generator.next_assumption_id(section_id)
            normalized_assumptions.append(assumption)

        # 4. Render prose
        prose_parts = []
        for claim in normalized_claims:
            rendered = self._render_claim(claim)
            prose_parts.append(rendered)

        prose = "\n\n".join(prose_parts)

        # 5. Build sidecar
        sidecar = {
            "section": section_id,
            "claims": [
                {
                    "claim_id": c["claim_id"],
                    "text": c["text"],
                    "type": c["type"],
                    "evidence_ids": c.get("evidence_ids", []),
                    "speculative": c.get("speculative", False),
                    "rendered_as": self._render_claim(c),
                }
                for c in normalized_claims
            ],
            "assumptions": normalized_assumptions,
            "claim_count": len(normalized_claims),
            "assumption_count": len(normalized_assumptions),
        }

        return prose, sidecar

    def _render_claim(self, claim: dict) -> str:
        """Render a single claim with appropriate markers."""
        text = claim.get("text", "").strip()
        claim_type = claim.get("type", "")
        speculative = claim.get("speculative", False)
        evidence_ids = claim.get("evidence_ids", [])

        if not text:
            return ""

        # Apply speculative prefix if needed
        if speculative and claim_type in self.SPECULATIVE_PREFIXES:
            prefix = self.SPECULATIVE_PREFIXES[claim_type]
            if not text.lower().startswith(prefix.lower()):
                # Remove existing prefix if mismatched
                text = self._strip_existing_prefix(text)
                text = f"{prefix} {text[0].lower()}{text[1:]}"

        # Ensure evidence citations are present in text
        for eid in evidence_ids:
            if eid not in text:
                # Append citation if missing
                if not text.endswith("."):
                    text += f" [{eid}]."
                else:
                    text = text[:-1] + f" [{eid}]."

        return text

    @staticmethod
    def _strip_existing_prefix(text: str) -> str:
        """Remove existing speculative prefixes."""
        prefixes_to_strip = [
            "We hypothesize that ", "We expect that ",
            "We aim to ", "We believe that ",
            "We propose that ", "We hope to ",
        ]
        for prefix in prefixes_to_strip:
            if text.startswith(prefix):
                return text[len(prefix):]
        return text

    @staticmethod
    def _validate_schema(structured_output: dict) -> bool:
        """Validate structured output against CLAIM_SCHEMA.

        Checks:
        - Has 'section' key
        - Has 'claims' list
        - Each claim has required fields
        - Each claim type is a known ClaimType value
        """
        if not isinstance(structured_output, dict):
            return False

        if "section" not in structured_output:
            return False

        claims = structured_output.get("claims")
        if not isinstance(claims, list):
            return False

        required_fields = {"claim_id", "text", "type", "evidence_ids",
                          "speculative", "rationale", "section"}

        for claim in claims:
            if not isinstance(claim, dict):
                return False

            # Check required fields
            missing = required_fields - set(claim.keys())
            if missing:
                logger.warning("Claim missing fields: %s", missing)
                return False

            # Check type is valid
            claim_type = claim.get("type", "")
            if claim_type not in CLAIM_TYPE_VALUES:
                logger.warning("Unknown claim type: %s", claim_type)
                return False

            # Check evidence_ids is a list
            if not isinstance(claim.get("evidence_ids"), list):
                return False

        return True

    def render_assumption_register(self, assumptions: list[dict]) -> str:
        """Render assumption register as a structured list."""
        if not assumptions:
            return ""

        lines = ["### Design Assumptions\n"]

        for a in assumptions:
            text = a.get("text", "")
            basis = a.get("basis", "unknown")
            risk = a.get("risk", "medium")
            validation = a.get("validation_plan", "Not specified")

            lines.append(
                f"- **[{risk.upper()} RISK]** {text}\n"
                f"  - Basis: {basis}\n"
                f"  - Validation: {validation}"
            )

        return "\n".join(lines)
