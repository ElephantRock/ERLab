"""SmartRouter v0.3 — Certified routing for ERLab pipeline stages.

Moves from static/default provider selection to contract-aware,
certification-backed routing that selects both model + execution strategy.

Flow:
    StageContract
    → CertifiedLookup (preliminary candidates)
    → StrategyPlanner (per candidate)
    → HardGateEngine (candidate + strategy plan)
    → rank surviving candidate-plan pairs
    → RoutingDecision
"""

__all__ = [
    "StageContract",
    "CertifiedModelCandidate",
    "CertifiedCapabilityLookup",
    "GateResult",
    "HardGateEngine",
    "StrategyPlan",
    "StrategyPlanner",
    "RoutingDecision",
    "RoutingRuntimeContext",
    "SmartRouter",
    "DryRunLogger",
]
