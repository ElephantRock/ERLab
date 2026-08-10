"""Pipeline strategy architecture for configurable stage execution."""
from .models import PipelineStrategy, StageConfig, StrategyConfig
from .presets import register_presets
from .registry import StrategyRegistry

__all__ = [
    "PipelineStrategy",
    "StageConfig",
    "StrategyConfig",
    "StrategyRegistry",
    "register_presets",
]
