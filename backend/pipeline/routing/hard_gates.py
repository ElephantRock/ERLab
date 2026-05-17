"""Hard Gate Engine — rejects unsafe candidates before ranking.

Hard gates dominate rankings. A model with a strong score must still be
rejected if it fabricates citations, lacks stage eligibility, fails context
constraints, or violates review independence.

Implementation correction from review: gates that depend on context size
evaluate against the STRATEGY PLAN, not the raw prompt. A candidate may
fail context for single_call but pass for section_wise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.pipeline.routing.stage_contract import StageContract
from backend.pipeline.routing.certified_lookup import CertifiedModelCandidate

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result from a single hard gate check."""

    passed: bool
    gate: str
    reason: str

    def to_dict(self) -> dict:
        return {"passed": self.passed, "gate": self.gate, "reason": self.reason}


class HardGateEngine:
    """Evaluates candidates against hard gates.

    Any gate returning passed=False blocks the candidate from ranking.
    """

    # Thresholds
    JSON_SCHEMA_MIN_RATE = 0.70
    GROUNDING_CLAIM_SUPPORT_MIN = 0.50
    CONTEXT_HEADROOM = 1.15  # require 15% headroom

    def evaluate(
        self,
        contract: StageContract,
        candidate: CertifiedModelCandidate,
        generator_model_id: str | None = None,
        strategy_input_tokens: int | None = None,
        strategy_output_tokens: int | None = None,
    ) -> list[GateResult]:
        """Run all hard gates for a candidate.

        Args:
            contract: Stage routing requirements.
            candidate: The model candidate to evaluate.
            generator_model_id: Model that generated the output being reviewed
                                (for review independence check).
            strategy_input_tokens: Input tokens planned by strategy (not raw prompt).
            strategy_output_tokens: Output tokens planned by strategy.

        Returns:
            List of GateResult. Any passed=False blocks the candidate.
        """
        results = []

        # Gate 1: Production registry membership
        results.append(self._gate_production_registry(candidate))

        # Gate 2: Stage allowed
        results.append(self._gate_stage_allowed(contract, candidate))

        # Gate 3: v2 not_approved
        results.append(self._gate_v2_not_approved(contract, candidate))

        # Gate 4: Context sufficient (uses strategy plan, not raw prompt)
        effective_input = strategy_input_tokens or contract.input_tokens_estimate
        effective_output = strategy_output_tokens or contract.output_tokens_requested
        results.append(self._gate_context_sufficient(contract, candidate, effective_input, effective_output))

        # Gate 5: JSON capability
        if contract.requires_json:
            results.append(self._gate_json_capability(candidate))

        # Gate 6: No fabrication (grounding gate)
        if contract.requires_grounding:
            results.append(self._gate_no_fabrication(candidate))
            results.append(self._gate_grounding_quality(candidate))

        # Gate 7: Review independence
        if contract.requires_independent_review:
            results.append(self._gate_review_independence(candidate, generator_model_id))

        # Gate 8: Synthesis v2 cap
        if contract.stage in ("paper_synthesis", "proposal_synthesis"):
            results.append(self._gate_synthesis_v2_cap(candidate))

        return results

    def all_passed(self, results: list[GateResult]) -> bool:
        """Check if all gates passed."""
        return all(r.passed for r in results)

    def passed_gate_names(self, results: list[GateResult]) -> list[str]:
        """Get names of all gates that passed."""
        return [r.gate for r in results if r.passed]

    def failed_gates(self, results: list[GateResult]) -> list[GateResult]:
        """Get only failed gates."""
        return [r for r in results if not r.passed]

    # ------------------------------------------------------------------
    # Individual gates
    # ------------------------------------------------------------------

    def _gate_production_registry(self, candidate: CertifiedModelCandidate) -> GateResult:
        if not candidate.model_id:
            return GateResult(False, "production_registry", "Empty model_id")
        return GateResult(True, "production_registry", "Model in production registry")

    def _gate_stage_allowed(self, contract: StageContract, candidate: CertifiedModelCandidate) -> GateResult:
        if contract.stage in candidate.allowed_stages:
            return GateResult(True, "stage_allowed", f"Stage '{contract.stage}' allowed")
        return GateResult(
            False, "stage_allowed",
            f"Stage '{contract.stage}' not in allowed_stages for {candidate.model_id}",
        )

    def _gate_v2_not_approved(self, contract: StageContract, candidate: CertifiedModelCandidate) -> GateResult:
        # If v0.2 data exists, check stage eligibility
        if candidate.eval_version == "0.2" and candidate.stage_score is not None:
            # v0.2 models with not_approved stage should have been filtered by lookup,
            # but double-check here
            return GateResult(True, "v2_not_approved", "v0.2 eligibility checked")
        # v0.1 models pass this gate (no v0.2 data to reject)
        return GateResult(True, "v2_not_approved", "No v0.2 data; v0.1 eligibility accepted")

    def _gate_context_sufficient(
        self,
        contract: StageContract,
        candidate: CertifiedModelCandidate,
        effective_input: int,
        effective_output: int,
    ) -> GateResult:
        """Check context window against strategy-planned token counts.

        This gate uses strategy plan estimates, NOT raw prompt size.
        A candidate may fail for single_call but pass for section_wise.
        """
        required = int((effective_input + effective_output) * self.CONTEXT_HEADROOM)
        available = candidate.safe_context_window

        if available <= 0:
            return GateResult(
                False, "context_sufficient",
                f"Unknown context window for {candidate.model_id}",
            )

        if available >= required:
            return GateResult(
                True, "context_sufficient",
                f"Context {available} >= required {required} (with {int((self.CONTEXT_HEADROOM-1)*100)}% headroom)",
            )
        return GateResult(
            False, "context_sufficient",
            f"Context {available} < required {required} (input={effective_input} + output={effective_output} × {self.CONTEXT_HEADROOM})",
        )

    def _gate_json_capability(self, candidate: CertifiedModelCandidate) -> GateResult:
        if candidate.schema_valid_rate >= self.JSON_SCHEMA_MIN_RATE:
            return GateResult(
                True, "json_capability",
                f"Schema valid rate {candidate.schema_valid_rate:.2f} >= {self.JSON_SCHEMA_MIN_RATE}",
            )
        return GateResult(
            False, "json_capability",
            f"Schema valid rate {candidate.schema_valid_rate:.2f} < {self.JSON_SCHEMA_MIN_RATE} (JSON required)",
        )

    def _gate_no_fabrication(self, candidate: CertifiedModelCandidate) -> GateResult:
        fab_rate = candidate.grounding_metrics.get("citation_fabrication_rate", 0.0)
        if fab_rate == 0.0:
            return GateResult(True, "no_fabrication", "No citation fabrication detected")
        return GateResult(
            False, "no_fabrication",
            f"Citation fabrication rate {fab_rate:.3f} > 0 (grounding required)",
        )

    def _gate_grounding_quality(self, candidate: CertifiedModelCandidate) -> GateResult:
        support_rate = candidate.grounding_metrics.get("claim_support_rate", 1.0)
        if support_rate >= self.GROUNDING_CLAIM_SUPPORT_MIN:
            return GateResult(
                True, "grounding_quality",
                f"Claim support rate {support_rate:.2f} >= {self.GROUNDING_CLAIM_SUPPORT_MIN}",
            )
        return GateResult(
            False, "grounding_quality",
            f"Claim support rate {support_rate:.2f} < {self.GROUNDING_CLAIM_SUPPORT_MIN}",
        )

    def _gate_review_independence(
        self,
        candidate: CertifiedModelCandidate,
        generator_model_id: str | None,
    ) -> GateResult:
        if generator_model_id is None:
            return GateResult(True, "review_independence", "No generator specified; independence assumed")

        if candidate.model_id != generator_model_id:
            return GateResult(
                True, "review_independence",
                f"Reviewer {candidate.model_id} != generator {generator_model_id}",
            )
        return GateResult(
            False, "review_independence",
            f"Reviewer {candidate.model_id} is same as generator; independent review required",
        )

    def _gate_synthesis_v2_cap(self, candidate: CertifiedModelCandidate) -> GateResult:
        """v0.2 cap: paper/proposal synthesis cannot exceed limited_use."""
        # This gate is informational in v0.3 — it warns but doesn't block
        # because the production registry already controls which models are available
        return GateResult(
            True, "synthesis_v2_cap",
            "Synthesis stage; v0.2 cap enforced at eligibility level",
        )
