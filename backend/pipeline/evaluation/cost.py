"""Evaluation-specific cost tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class EvaluationCostRecord(BaseModel):
    scorer_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False


class EvaluationCostTracker:
    """Tracks LLM token usage and cost for evaluation operations."""

    def __init__(self) -> None:
        self._records: list[EvaluationCostRecord] = []

    def record(self, record: EvaluationCostRecord) -> None:
        self._records.append(record)

    def summary(self) -> dict[str, Any]:
        if not self._records:
            return {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "eval_count": 0,
                "cached_count": 0,
            }
        return {
            "total_cost_usd": sum(r.cost_usd for r in self._records),
            "total_tokens": sum(r.input_tokens + r.output_tokens for r in self._records),
            "total_input_tokens": sum(r.input_tokens for r in self._records),
            "total_output_tokens": sum(r.output_tokens for r in self._records),
            "eval_count": len(self._records),
            "cached_count": sum(1 for r in self._records if r.cached),
            "by_scorer": {
                name: {
                    "calls": sum(
                        1 for r in self._records if r.scorer_name == name and not r.cached
                    ),
                    "cost_usd": sum(
                        r.cost_usd for r in self._records if r.scorer_name == name
                    ),
                }
                for name in {r.scorer_name for r in self._records}
            },
        }

    def reset(self) -> None:
        self._records.clear()
