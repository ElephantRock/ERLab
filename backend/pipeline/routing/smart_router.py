"""SmartRouter — contract-aware, certification-backed model + strategy routing.

Flow:
    StageContract
    → CertifiedLookup (preliminary candidates)
    → StrategyPlanner (per candidate)
    → HardGateEngine (candidate + strategy plan)
    → rank surviving candidate-plan pairs
    → RoutingDecision

The router selects both model AND execution strategy, not just a model name.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.routing.stage_contract import (
    StageContract,
    get_smart_router_config,
)
from backend.pipeline.routing.certified_lookup import (
    CertifiedCapabilityLookup,
    CertifiedModelCandidate,
)
from backend.pipeline.routing.hard_gates import HardGateEngine
from backend.pipeline.routing.strategy_planner import StrategyPlanner, StrategyPlan
from backend.pipeline.routing.routing_decision import RoutingDecision

logger = logging.getLogger(__name__)


@dataclass
class RoutingRuntimeContext:
    """Runtime context for a routing decision."""

    run_id: str = ""
    generator_model_id: str | None = None   # for review independence check
    total_budget_remaining: float | None = None
    forced_model: str | None = None          # override: still applies hard gates
    forced_model_unsafe: str | None = None   # override: bypasses hard gates (test-only)
    registry_dir: str = "data/model_certification"


# Default ranking weights
DEFAULT_WEIGHTS = {
    "stage_score": 0.35,
    "grounding_score": 0.25,
    "schema_score": 0.15,
    "context_fit": 0.10,
    "latency": 0.10,
    "cost": 0.05,
}


class SmartRouter:
    """Main router: lookup → gate → plan → rank → decide."""

    def __init__(
        self,
        lookup: CertifiedCapabilityLookup,
        gates: HardGateEngine | None = None,
        planner: StrategyPlanner | None = None,
        mode: str = "dry_run",
        ranking_weights: dict[str, float] | None = None,
    ) -> None:
        self._lookup = lookup
        self._gates = gates or HardGateEngine()
        self._planner = planner or StrategyPlanner()
        self._mode = mode
        self._weights = ranking_weights or dict(DEFAULT_WEIGHTS)
        self._decision_log: list[RoutingDecision] = []

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        if value not in ("dry_run", "enforce", "disabled"):
            raise ValueError(f"Invalid mode: {value}")
        self._mode = value

    def route(
        self,
        contract: StageContract,
        context: RoutingRuntimeContext,
    ) -> RoutingDecision:
        """Main routing entry point.

        Steps:
            1. Load certified candidates for stage
            2. Apply forced model overrides (if any)
            3. Plan strategy per candidate
            4. Apply hard gates using strategy-planned token counts
            5. Rank surviving candidate-plan pairs
            6. Return RoutingDecision
        """
        # Step 0: Check for unsafe forced model override (test-only)
        if context.forced_model_unsafe:
            logger.warning(
                "UNSAFE forced model override: %s (hard gates bypassed)",
                context.forced_model_unsafe,
            )
            return RoutingDecision(
                stage=contract.stage,
                model_id=context.forced_model_unsafe,
                provider="override",
                eligibility="forced_unsafe",
                strategy="single_call",
                confidence=0.0,
                reason=f"Forced model (unsafe override, hard gates bypassed)",
                warnings=["UNSAFE: Hard gates bypassed by forced_model_unsafe override"],
            )

        # Step 1: Load certified candidates
        candidates = self._lookup.get_candidates_for_stage(contract.stage)

        # Step 1b: Apply safe forced model filter
        if context.forced_model:
            forced = [c for c in candidates if c.model_id == context.forced_model]
            if forced:
                candidates = forced
            else:
                # Forced model not in certified list — check if it exists at all
                all_models = self._lookup.production_models
                if context.forced_model in all_models:
                    # Exists but not eligible for this stage
                    return RoutingDecision.degraded_decision(
                        contract.stage,
                        f"Forced model {context.forced_model} not eligible for stage '{contract.stage}'",
                    )
                else:
                    return RoutingDecision.degraded_decision(
                        contract.stage,
                        f"Forced model {context.forced_model} not found in production registry",
                    )

        if not candidates:
            return RoutingDecision.degraded_decision(
                contract.stage,
                f"No certified candidates for stage '{contract.stage}'",
            )

        # Step 2: Plan strategy per candidate
        plans = self._planner.plan_all(contract, candidates)

        # Step 3: Apply hard gates using strategy-planned token counts
        surviving: list[tuple[CertifiedModelCandidate, StrategyPlan, list[str]]] = []
        for candidate, plan in plans:
            if plan.strategy == "skip_with_degraded_result":
                continue  # strategy planner already gave up

            gate_results = self._gates.evaluate(
                contract, candidate,
                generator_model_id=context.generator_model_id,
                strategy_input_tokens=plan.estimated_input_tokens,
                strategy_output_tokens=plan.estimated_output_tokens,
            )

            if self._gates.all_passed(gate_results):
                gates_passed = self._gates.passed_gate_names(gate_results)
                surviving.append((candidate, plan, gates_passed))
            else:
                failed = self._gates.failed_gates(gate_results)
                logger.debug(
                    "Candidate %s gated out for %s: %s",
                    candidate.model_id, contract.stage,
                    "; ".join(f"{g.gate}: {g.reason}" for g in failed),
                )

        if not surviving:
            return RoutingDecision.degraded_decision(
                contract.stage,
                f"All candidates gated out for stage '{contract.stage}'",
            )

        # Step 4: Rank surviving pairs
        ranked = self._rank(surviving)

        # Step 5: Return top decision
        best_candidate, best_plan, best_gates = ranked[0]
        alternatives = len(ranked) - 1

        warnings = list(best_plan.warnings)
        if best_candidate.eval_version == "0.2" and best_candidate.stage_score is not None:
            if best_candidate.stage_score < 0.70:
                warnings.append(f"Low stage score: {best_candidate.stage_score:.2f}")

        decision = RoutingDecision(
            stage=contract.stage,
            model_id=best_candidate.model_id,
            provider=best_candidate.provider,
            eligibility=best_candidate.stage_eligibility,
            strategy=best_plan.strategy,
            confidence=self._compute_confidence(best_candidate, best_plan),
            reason=best_plan.reason,
            hard_gates_passed=best_gates,
            warnings=warnings,
            alternative_candidates=alternatives,
            eval_version=best_candidate.eval_version,
        )

        self._decision_log.append(decision)
        return decision

    def _rank(
        self,
        surviving: list[tuple[CertifiedModelCandidate, StrategyPlan, list[str]]],
    ) -> list[tuple[CertifiedModelCandidate, StrategyPlan, list[str]]]:
        """Rank surviving candidate-plan pairs by composite score."""

        def score_pair(pair: tuple[CertifiedModelCandidate, StrategyPlan, list[str]]) -> float:
            candidate, plan, _ = pair
            return self._score_candidate(candidate, plan)

        return sorted(surviving, key=score_pair, reverse=True)

    def _score_candidate(self, candidate: CertifiedModelCandidate, plan: StrategyPlan) -> float:
        """Compute composite score for a candidate-plan pair."""
        w = self._weights

        # Stage score (0.35) — use measured score or neutral 0.5
        stage = candidate.stage_score if candidate.stage_score is not None else 0.5

        # Grounding score (0.25) — claim support rate or neutral
        grounding = candidate.grounding_metrics.get("claim_support_rate", 0.5)

        # Schema score (0.15)
        schema = candidate.schema_valid_rate if candidate.schema_valid_rate > 0 else 0.5

        # Context fit (0.10) — how much headroom remains
        if candidate.safe_context_window > 0 and plan.total_tokens > 0:
            context_fit = min(1.0, candidate.safe_context_window / (plan.total_tokens * 1.5))
        else:
            context_fit = 0.5

        # Latency (0.10) — local_fast=1.0, local_medium=0.7, cloud=0.4
        latency_map = {"local_fast": 1.0, "local_medium": 0.7, "cloud_medium": 0.4, "cloud_slow": 0.2}
        latency = latency_map.get(candidate.latency_class or "", 0.5)

        # Cost (0.05) — free=1.0, cheap=0.8, expensive=0.3
        if candidate.provider in ("lmstudio", "ollama", "local"):
            cost = 1.0
        elif candidate.provider in ("anthropic", "openai"):
            cost = 0.3
        else:
            cost = 0.5

        return (
            w.get("stage_score", 0.35) * stage
            + w.get("grounding_score", 0.25) * grounding
            + w.get("schema_score", 0.15) * schema
            + w.get("context_fit", 0.10) * context_fit
            + w.get("latency", 0.10) * latency
            + w.get("cost", 0.05) * cost
        )

    def _compute_confidence(self, candidate: CertifiedModelCandidate, plan: StrategyPlan) -> float:
        """Compute confidence score for the decision."""
        base = self._score_candidate(candidate, plan)

        # Reduce confidence for tight fits
        if plan.warnings:
            base -= 0.05 * len(plan.warnings)

        # Reduce for limited_use
        if candidate.stage_eligibility == "limited_use":
            base -= 0.05

        return max(0.0, min(1.0, base))

    def get_decision_log(self, stage: str = "", limit: int = 100) -> list[RoutingDecision]:
        """Get logged routing decisions."""
        decisions = self._decision_log
        if stage:
            decisions = [d for d in decisions if d.stage == stage]
        return decisions[-limit:]
