"""Output validator with reask loop.

Guardrails-ai inspired declarative output validation that checks
pipeline outputs against boundary contracts and re-asks the LLM
to fix issues when validation fails.
"""

import logging

from backend.pipeline.gateway.transport import GatewayTransportError
from backend.pipeline.governance.contracts import (
    DEFAULT_CONTRACTS,
    BoundaryContract,
    GovernanceCheck,
    OutputVerdict,
)
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

VALIDATION_PROMPT = """Evaluate this research output for compliance issues.

## Content to validate:
{content}

## Checks:
{checks}

For each check, determine if the content passes or fails.
Respond with JSON: {{"checks": [{{"contract_name": "...", "verdict": "accepted|rejected", "reason": "..."}}]}}
"""


class OutputValidator:
    """Guardrails-ai inspired declarative output validation with reask loop."""

    def __init__(
        self,
        provider: LLMProvider,
        contracts: list[BoundaryContract] | None = None,
    ):
        self._provider = provider
        self._contracts = contracts or DEFAULT_CONTRACTS

    async def validate(self, content: str, output_type: str = "proposal") -> list[GovernanceCheck]:
        """Validate content against all contracts."""
        # Quick structural checks (no LLM needed)
        checks = []
        for contract in self._contracts:
            check = self._structural_check(content, contract)
            if check:
                checks.append(check)

        # LLM-based content check if no structural failures
        if all(c.verdict != OutputVerdict.REJECTED for c in checks):
            llm_checks = await self._llm_check(content)
            checks.extend(llm_checks)

        return checks

    async def validate_with_reask(
        self,
        content: str,
        output_type: str = "proposal",
        max_reasks: int = 2,
    ) -> tuple[str, list[GovernanceCheck]]:
        """Validate and re-ask the LLM to fix issues if validation fails."""
        all_checks: list[GovernanceCheck] = []
        current_content = content

        for _attempt in range(max_reasks + 1):
            checks = await self.validate(current_content, output_type)
            all_checks.extend(checks)

            if all(c.verdict != OutputVerdict.REJECTED for c in checks):
                return current_content, all_checks

            # Build reask prompt with rejection reasons
            rejections = [
                f"- {c.contract_name}: {c.reason}"
                for c in checks
                if c.verdict == OutputVerdict.REJECTED
            ]
            current_content = await self._reask(current_content, rejections)

        return current_content, all_checks

    def _structural_check(self, content: str, contract: BoundaryContract) -> GovernanceCheck | None:
        """Perform structural (non-LLM) validation checks."""
        if contract.constraint_type == "max_length":
            max_chars = contract.params.get("max_chars", 50000)
            if len(content) > max_chars:
                return GovernanceCheck(
                    contract_name=contract.name,
                    verdict=OutputVerdict.REJECTED,
                    reason=f"Content length {len(content)} exceeds max {max_chars}",
                )

        if contract.constraint_type == "min_length":
            min_chars = contract.params.get("min_chars", 100)
            if len(content) < min_chars:
                return GovernanceCheck(
                    contract_name=contract.name,
                    verdict=OutputVerdict.NEEDS_REVISION,
                    reason=f"Content length {len(content)} below minimum {min_chars}",
                )

        return None

    async def _llm_check(self, content: str) -> list[GovernanceCheck]:
        """Use LLM to validate content quality."""
        checks_desc = "\n".join(f"- {c.name} ({c.constraint_type})" for c in self._contracts)

        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You validate research output quality."},
                    {
                        "role": "user",
                        "content": VALIDATION_PROMPT.format(
                            content=content[:3000],  # Truncate for cost
                            checks=checks_desc,
                        ),
                    },
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "checks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "contract_name": {"type": "string"},
                                    "verdict": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["contract_name", "verdict", "reason"],
                            },
                        }
                    },
                    "required": ["checks"],
                },
                temperature=0.1,
            )

            checks = []
            for c in result.get("checks", []):
                verdict_str = c.get("verdict", "accepted")
                try:
                    verdict = OutputVerdict(verdict_str)
                except ValueError:
                    verdict = OutputVerdict.ACCEPTED
                checks.append(
                    GovernanceCheck(
                        contract_name=c.get("contract_name", "unknown"),
                        verdict=verdict,
                        reason=c.get("reason", ""),
                    )
                )
            return checks

        except GatewayTransportError:
            # Case-4 R2 (adjudicated GENERIC_PRODUCT_DEFECT, 2026-08-18): a
            # typed provider/transport failure must keep its identity. The Q2
            # stage-loop terminalization converts it to FAILED_EXECUTION; it
            # must never become fallback output on a dead provider.
            raise
        except Exception as e:
            logger.error("Governance LLM check failed: %s", e)
            return []

    async def _reask(self, content: str, rejections: list[str]) -> str:
        """Ask the LLM to revise content based on rejection reasons."""
        try:
            result = await self._provider.structured_output(
                messages=[
                    {"role": "system", "content": "You revise research output to fix issues."},
                    {
                        "role": "user",
                        "content": (
                            "Revise this research output to address these issues:\n"
                            + "\n".join(rejections)
                            + f"\n\nOriginal content:\n{content[:2000]}"
                        ),
                    },
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "revised_content": {"type": "string"},
                    },
                    "required": ["revised_content"],
                },
            )
            return result.get("revised_content", content)
        except Exception as e:
            logger.error("Governance reask failed: %s", e)
            return content
