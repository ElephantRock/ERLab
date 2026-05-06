"""Data models for pipeline strategy configuration."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PipelineStrategy(str, Enum):
    """Available pipeline execution strategies."""

    FAST_SCAN = "fast_scan"
    DEEP_RESEARCH = "deep_research"
    ACADEMIC_PROPOSAL = "academic_proposal"
    LITERATURE_REVIEW = "literature_review"


@dataclass
class StageConfig:
    """Configuration for a single pipeline stage within a strategy."""

    enabled: bool = True
    timeout: float = 300.0
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "timeout": self.timeout,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageConfig:
        return cls(
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 300.0),
            params=data.get("params", {}),
        )


@dataclass
class StrategyConfig:
    """Full configuration for a pipeline strategy."""

    name: PipelineStrategy
    stages: dict[str, StageConfig] = field(default_factory=dict)
    max_total_time: float = 1800.0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "stages": {k: v.to_dict() for k, v in self.stages.items()},
            "max_total_time": self.max_total_time,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyConfig:
        stages_data = data.get("stages", {})
        stages = {k: StageConfig.from_dict(v) for k, v in stages_data.items()}
        return cls(
            name=PipelineStrategy(data["name"]),
            stages=stages,
            max_total_time=data.get("max_total_time", 1800.0),
            description=data.get("description", ""),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> StrategyConfig:
        return cls.from_dict(json.loads(json_str))
