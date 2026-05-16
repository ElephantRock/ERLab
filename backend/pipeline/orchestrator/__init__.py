"""Pipeline orchestrator — modular decomposition.

All callers can continue to use:
    from backend.pipeline.orchestrator import PipelineOrchestrator

Modules:
    _orchestrator.py    — PipelineOrchestrator class (run, resume, autonomous_cycle)
    service_registry.py — ServiceRegistry (20 init methods, 69 service attrs)
    stage_executor.py   — StageExecutor (retry, timeout, recording)
    result_processor.py — ResultProcessor (verify, evaluate, fingerprint, persist)
"""

from ._orchestrator import PipelineOrchestrator

__all__ = ["PipelineOrchestrator"]
