"""StageContract — per-stage routing requirements.

Each pipeline stage declares what it needs from a model:
  risk level, JSON capability, grounding, citations, context budget,
  latency constraints, and allowed execution strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_RISK_LEVELS = frozenset({"low", "medium", "high", "critical"})
VALID_SCHEMA_STRICTNESSES = frozenset({"none", "low", "medium", "high"})
VALID_COST_SENSITIVITIES = frozenset({"low", "medium", "high"})

VALID_STRATEGIES = frozenset({
    "single_call",
    "section_wise",
    "map_reduce",
    "compressed_review_packet",
    "section_wise_review",
    "closed_set_audit",
    "evidence_first",
    "prose_fallback",
    "skip_with_degraded_result",
})


@dataclass
class StageContract:
    """Routing requirements for a pipeline stage."""

    stage: str
    task_type: str                      # search | generation | audit | review
    risk_level: str                     # low | medium | high | critical
    schema_strictness: str = "none"     # none | low | medium | high
    requires_json: bool = False
    requires_grounding: bool = False
    requires_independent_review: bool = False
    requires_citations: bool = False
    input_tokens_estimate: int = 2000
    output_tokens_requested: int = 4096
    min_context_window: int = 4096
    recommended_context_length: int = 8192  # suggested per-request context for v1 chat
    latency_budget_seconds: float | None = None
    cost_sensitivity: str = "medium"
    allowed_strategies: list[str] = field(default_factory=lambda: ["single_call"])
    fallback_strategy: str = "single_call"

    def validate(self) -> list[str]:
        """Validate contract fields. Returns list of errors."""
        errors = []

        if not self.stage:
            errors.append("stage is required")
        if not self.task_type:
            errors.append("task_type is required")
        if self.risk_level not in VALID_RISK_LEVELS:
            errors.append(f"risk_level must be one of {sorted(VALID_RISK_LEVELS)}")
        if self.schema_strictness not in VALID_SCHEMA_STRICTNESSES:
            errors.append(f"schema_strictness must be one of {sorted(VALID_SCHEMA_STRICTNESSES)}")
        if self.cost_sensitivity not in VALID_COST_SENSITIVITIES:
            errors.append(f"cost_sensitivity must be one of {sorted(VALID_COST_SENSITIVITIES)}")

        invalid_strategies = [
            s for s in self.allowed_strategies
            if s not in VALID_STRATEGIES
        ]
        if invalid_strategies:
            errors.append(f"Invalid strategies: {invalid_strategies}")

        if self.fallback_strategy not in VALID_STRATEGIES:
            errors.append(f"Invalid fallback_strategy: {self.fallback_strategy}")

        if self.min_context_window < 0:
            errors.append("min_context_window must be >= 0")
        if self.input_tokens_estimate < 0:
            errors.append("input_tokens_estimate must be >= 0")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "task_type": self.task_type,
            "risk_level": self.risk_level,
            "schema_strictness": self.schema_strictness,
            "requires_json": self.requires_json,
            "requires_grounding": self.requires_grounding,
            "requires_independent_review": self.requires_independent_review,
            "requires_citations": self.requires_citations,
            "input_tokens_estimate": self.input_tokens_estimate,
            "output_tokens_requested": self.output_tokens_requested,
            "min_context_window": self.min_context_window,
            "latency_budget_seconds": self.latency_budget_seconds,
            "cost_sensitivity": self.cost_sensitivity,
            "allowed_strategies": self.allowed_strategies,
            "fallback_strategy": self.fallback_strategy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageContract:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def load_contracts(path: str | Path | None = None) -> dict[str, StageContract]:
    """Load stage contracts from YAML file.

    Returns dict mapping stage name → StageContract.
    """
    if path is None:
        path = Path(__file__).parent / "config" / "routing_policy.yaml"
    else:
        path = Path(path)

    if not path.exists():
        return {}

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}

    contracts = {}
    for stage_name, contract_data in data.get("stage_contracts", {}).items():
        if isinstance(contract_data, dict):
            contract_data.setdefault("stage", stage_name)
            contracts[stage_name] = StageContract.from_dict(contract_data)

    return contracts


def get_contract(stage: str, contracts: dict[str, StageContract]) -> StageContract:
    """Get contract for a stage. Raises KeyError if not found."""
    if stage not in contracts:
        raise KeyError(f"No contract defined for stage '{stage}'")
    return contracts[stage]


def get_smart_router_config(path: str | Path | None = None) -> dict[str, Any]:
    """Load smart router configuration from routing policy."""
    if path is None:
        path = Path(__file__).parent / "config" / "routing_policy.yaml"
    else:
        path = Path(path)

    if not path.exists():
        return _DEFAULT_ROUTER_CONFIG

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return _DEFAULT_ROUTER_CONFIG

    return data.get("smart_router", _DEFAULT_ROUTER_CONFIG)


_DEFAULT_ROUTER_CONFIG: dict[str, Any] = {
    "enabled": False,
    "mode": "disabled",
    "require_certified_models": False,
    "ranking_weights": {
        "stage_score": 0.35,
        "grounding_score": 0.25,
        "schema_score": 0.15,
        "context_fit": 0.10,
        "latency": 0.10,
        "cost": 0.05,
    },
}
