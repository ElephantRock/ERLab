"""Cost tracker: estimates LLM API costs per pipeline run.

Tracks token usage and computes cost estimates based on
model pricing. Helps users understand resource consumption.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Approximate pricing per 1K tokens (USD)
MODEL_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "ollama": {"input": 0.0, "output": 0.0},
    "default": {"input": 0.005, "output": 0.015},
}


@dataclass
class TokenUsage:
    """Token usage for a single API call."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stage: str = ""


@dataclass
class CostReport:
    """Cost report for a pipeline run."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_stage: dict[str, dict] = field(default_factory=dict)
    by_model: dict[str, dict] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens


class CostTracker:
    """Tracks token usage and computes cost estimates."""

    def __init__(self) -> None:
        self._usages: list[TokenUsage] = []

    def record(self, usage: TokenUsage) -> None:
        """Record a token usage event."""
        self._usages.append(usage)

    def report(self) -> CostReport:
        """Generate a cost report from recorded usages."""
        total_input = 0
        total_output = 0
        total_cost = 0.0
        by_stage: dict[str, dict] = {}
        by_model: dict[str, dict] = {}

        for u in self._usages:
            pricing = MODEL_PRICING.get(u.model, MODEL_PRICING["default"])
            cost = (u.input_tokens / 1000 * pricing["input"]) + \
                   (u.output_tokens / 1000 * pricing["output"])

            total_input += u.input_tokens
            total_output += u.output_tokens
            total_cost += cost

            # Aggregate by stage
            if u.stage:
                if u.stage not in by_stage:
                    by_stage[u.stage] = {"input": 0, "output": 0, "cost": 0.0}
                by_stage[u.stage]["input"] += u.input_tokens
                by_stage[u.stage]["output"] += u.output_tokens
                by_stage[u.stage]["cost"] += cost

            # Aggregate by model
            if u.model not in by_model:
                by_model[u.model] = {"input": 0, "output": 0, "cost": 0.0}
            by_model[u.model]["input"] += u.input_tokens
            by_model[u.model]["output"] += u.output_tokens
            by_model[u.model]["cost"] += cost

        return CostReport(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_cost_usd=round(total_cost, 6),
            by_stage=by_stage,
            by_model=by_model,
        )

    @property
    def usage_count(self) -> int:
        return len(self._usages)
