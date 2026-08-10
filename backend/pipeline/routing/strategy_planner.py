"""Strategy Planner — selects execution strategy per candidate.

Strategy selection happens BEFORE final model ranking. This prevents:
    pick model → discover prompt doesn't fit → emergency fallback

Instead:
    stage contract → strategy feasibility → hard gates → ranking

Each strategy estimates token budgets differently:
    single_call: full prompt + full output
    section_wise: max(section_size + output_per_section, full_input_for_overview + output)
    map_reduce: map_input + map_output per chunk, then reduce_input + reduce_output
    compressed_review_packet: compressed input + output
    closed_set_audit: structured input + structured output
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.pipeline.routing.certified_lookup import CertifiedModelCandidate
from backend.pipeline.routing.stage_contract import StageContract

logger = logging.getLogger(__name__)


@dataclass
class StrategyPlan:
    """Result of strategy planning for a candidate."""

    strategy: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    fits_context: bool
    reason: str
    warnings: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens


class StrategyPlanner:
    """Plans execution strategy for each candidate."""

    # Strategy-specific token multipliers (vs raw contract estimates)
    SECTION_WISE_INPUT_FACTOR = 0.35      # each section is ~35% of total input
    SECTION_WISE_OUTPUT_FACTOR = 0.40     # output per section
    COMPRESSED_REVIEW_FACTOR = 0.50       # compressed packet is ~50% of raw
    MAP_REDUCE_MAP_FACTOR = 0.30          # each chunk is ~30% of input
    MAP_REDUCE_REDUCE_INPUT = 2000        # reduction step input estimate

    def plan(
        self,
        contract: StageContract,
        candidate: CertifiedModelCandidate,
    ) -> StrategyPlan:
        """Plan the best strategy for a candidate.

        Tries strategies in order of preference (from contract.allowed_strategies).
        Returns the first strategy that fits the candidate's context window.
        """
        strategies_to_try = list(contract.allowed_strategies)

        for strategy in strategies_to_try:
            plan = self._evaluate_strategy(strategy, contract, candidate)
            if plan.fits_context:
                return plan

        # Nothing fits — try fallback
        if contract.fallback_strategy not in strategies_to_try:
            plan = self._evaluate_strategy(contract.fallback_strategy, contract, candidate)
            if plan.fits_context:
                return plan

        # Nothing fits at all
        return StrategyPlan(
            strategy="skip_with_degraded_result",
            estimated_input_tokens=0,
            estimated_output_tokens=0,
            fits_context=False,
            reason=f"No strategy fits {candidate.model_id} (ctx={candidate.safe_context_window})",
            warnings=[f"All strategies exceed context window for {candidate.model_id}"],
        )

    def plan_all(
        self,
        contract: StageContract,
        candidates: list[CertifiedModelCandidate],
    ) -> list[tuple[CertifiedModelCandidate, StrategyPlan]]:
        """Plan strategy for each candidate."""
        results = []
        for candidate in candidates:
            plan = self.plan(contract, candidate)
            results.append((candidate, plan))
        return results

    def _evaluate_strategy(
        self,
        strategy: str,
        contract: StageContract,
        candidate: CertifiedModelCandidate,
    ) -> StrategyPlan:
        """Evaluate a single strategy for a candidate."""
        if strategy == "single_call":
            return self._plan_single_call(contract, candidate)
        elif strategy == "section_wise":
            return self._plan_section_wise(contract, candidate)
        elif strategy == "map_reduce":
            return self._plan_map_reduce(contract, candidate)
        elif strategy == "compressed_review_packet":
            return self._plan_compressed_review(contract, candidate)
        elif strategy == "section_wise_review":
            return self._plan_section_wise_review(contract, candidate)
        elif strategy == "closed_set_audit":
            return self._plan_closed_set_audit(contract, candidate)
        elif strategy == "evidence_first":
            return self._plan_evidence_first(contract, candidate)
        elif strategy == "prose_fallback":
            return self._plan_prose_fallback(contract, candidate)
        else:
            return self._plan_single_call(contract, candidate)

    def _fits(self, input_tokens: int, output_tokens: int, candidate: CertifiedModelCandidate) -> bool:
        """Check if estimated tokens fit in candidate's context with 15% headroom."""
        required = int((input_tokens + output_tokens) * 1.15)
        return candidate.safe_context_window >= required

    def _plan_single_call(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        inp = contract.input_tokens_estimate
        out = contract.output_tokens_requested
        fits = self._fits(inp, out, candidate)
        warnings = []
        if fits and candidate.safe_context_window < int((inp + out) * 1.3):
            warnings.append("Tight fit for single_call")
        return StrategyPlan(
            strategy="single_call",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Single call: {inp}+{out} tokens" + (" (fits)" if fits else " (too large)"),
            warnings=warnings,
        )

    def _plan_section_wise(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        # Each section: ~35% of input, ~40% of output
        inp = int(contract.input_tokens_estimate * self.SECTION_WISE_INPUT_FACTOR)
        out = int(contract.output_tokens_requested * self.SECTION_WISE_OUTPUT_FACTOR)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="section_wise",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Section-wise: {inp}+{out} per section" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_map_reduce(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        # Map phase: ~30% of input per chunk
        inp = int(contract.input_tokens_estimate * self.MAP_REDUCE_MAP_FACTOR)
        out = int(contract.output_tokens_requested * 0.25)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="map_reduce",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Map-reduce: {inp}+{out} per chunk" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_compressed_review(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        inp = int(contract.input_tokens_estimate * self.COMPRESSED_REVIEW_FACTOR)
        out = int(contract.output_tokens_requested * 0.60)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="compressed_review_packet",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Compressed review: {inp}+{out}" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_section_wise_review(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        inp = int(contract.input_tokens_estimate * 0.40)
        out = int(contract.output_tokens_requested * 0.50)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="section_wise_review",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Section-wise review: {inp}+{out} per section" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_closed_set_audit(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        # Structured audit: input is citation list + claims, output is structured verdict
        inp = int(contract.input_tokens_estimate * 0.70)
        out = int(contract.output_tokens_requested * 0.60)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="closed_set_audit",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Closed-set audit: {inp}+{out}" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_evidence_first(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        # Evidence gathering then generation — two calls
        inp = int(contract.input_tokens_estimate * 0.60)
        out = int(contract.output_tokens_requested * 0.50)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="evidence_first",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Evidence-first: {inp}+{out} per call" + (" (fits)" if fits else " (too large)"),
        )

    def _plan_prose_fallback(self, contract: StageContract, candidate: CertifiedModelCandidate) -> StrategyPlan:
        # Minimal output, no JSON requirements
        inp = contract.input_tokens_estimate
        out = min(contract.output_tokens_requested, 2048)
        fits = self._fits(inp, out, candidate)
        return StrategyPlan(
            strategy="prose_fallback",
            estimated_input_tokens=inp,
            estimated_output_tokens=out,
            fits_context=fits,
            reason=f"Prose fallback: {inp}+{out}" + (" (fits)" if fits else " (too large)"),
            warnings=["Using prose fallback — no structured output"] if fits else [],
        )
