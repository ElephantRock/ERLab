"""Pipeline orchestrator — modular decomposition.

All callers can continue to use:
    from backend.pipeline.orchestrator import PipelineOrchestrator
"""

from ._orchestrator import PipelineOrchestrator

__all__ = ["PipelineOrchestrator"]
