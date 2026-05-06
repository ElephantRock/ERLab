"""Pipeline strategy architecture for configurable stage execution."""
from .models import PipelineStrategy, StageConfig, StrategyConfig
from .registry import StrategyRegistry
from .presets import register_presets

__all__ = [
    "PipelineStrategy",
    "StageConfig",
    "StrategyConfig",
    "StrategyRegistry",
    "register_presets",
]
