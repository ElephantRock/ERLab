"""DAG-to-Stage Adapter — delegates to PipelineOrchestrator with YAML config.

BATCH-183: Instead of rebuilding stages from scratch (which triggers heavy
imports), this adapter creates a PipelineOrchestrator with the requested
strategy and runs through its stages using YAML-defined plan ordering.

The DAG contribution is:
1. YAML-defined stage ordering (strategy → plan)
2. StageLogger for structured JSON logging
3. Trimmer stage injected after ingestion
4. Progress reporting per-stage

The heavy lifting (LLM calls, embedding, search) is delegated to the
existing, battle-tested PipelineOrchestrator.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def new_to_old_ctx(new) -> Any:
    """Convert new dag.StageContext to old stages.StageContext."""
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import StageContext as OldCtx

    result = PipelineResult()
    result.run_id = new.run_id
    result.papers = new.papers
    result.gaps = new.gaps
    result.ideas = new.ideas
    result.proposals = new.proposals

    old = OldCtx(
        result=result,
        domain=new.domain,
        run_id=new.run_id,
        params={},
        max_gaps=new.config.get("budgets", {}).get("max_gaps", 5) if new.config else 5,
    )
    old.all_papers = new.papers
    old.export_format = new.config.get("export_format", "markdown") if new.config else "markdown"
    return old


def old_to_new_ctx(old: Any, new: Any) -> None:
    """Write back from old StageContext to new dag.StageContext (in-place)."""
    new.papers = old.all_papers
    new.gaps = old.result.gaps
    new.ideas = old.result.ideas
    new.proposals = old.result.proposals


class DAGStageAdapter:
    """Delegates to PipelineOrchestrator with YAML strategy and structured logging.

    Instead of rebuilding stages, we create a PipelineOrchestrator with the
    requested strategy and let it handle stage construction. The DAG layer
    adds structured logging and progress reporting.
    """

    def __init__(self, settings: Any = None) -> None:
        self._settings = settings

    @property
    def available_stages(self) -> list[str]:
        """Return stage names from the YAML config (no heavy imports)."""
        from backend.pipeline.dag.runner import DAGRunner
        runner = DAGRunner()
        config = runner.load_config()
        all_stages = set()
        for strat in config.get("strategies", {}).values():
            all_stages.update(strat.get("stages", []))
        return sorted(all_stages)

    async def execute(
        self,
        strategy: str,
        domain: str,
        run_id: str,
        stage_callback: Any = None,
        search_queries: list[str] | None = None,
        max_gaps: int = 5,
        export_format: str = "markdown",
    ) -> Any:
        """Execute a full pipeline run by delegating to PipelineOrchestrator.

        Returns the PipelineResult from the orchestrator.
        """
        from backend.pipeline.orchestrator import PipelineOrchestrator
        from backend.pipeline.dag.stage_log import StageLogger

        # Create stage logger
        dag_logger = StageLogger(run_id=run_id)

        # Build orchestrator with the requested strategy
        orchestrator = PipelineOrchestrator(
            stage_callback=stage_callback,
            strategy=strategy,
            settings=self._settings,
        )

        # Run the pipeline
        t0 = time.time()
        try:
            result = await orchestrator.run(
                domain=domain,
                search_queries=search_queries,
                max_gaps=max_gaps,
                export_format=export_format,
                run_id=run_id,
            )
            elapsed = time.time() - t0

            # Log final summary
            dag_logger.log(
                stage="pipeline",
                event="complete",
                config={"strategy": strategy, "domain": domain},
                inputs={},
                outputs={
                    "papers": len(result.papers_found) if result.papers_found else 0,
                    "gaps": len(result.gaps) if result.gaps else 0,
                    "ideas": len(result.ideas) if result.ideas else 0,
                    "proposals": len(result.proposals) if result.proposals else 0,
                },
                elapsed_s=elapsed,
            )
            logger.info(
                "DAG run %s completed in %.1fs: %d papers, %d gaps, %d ideas, %d proposals",
                run_id, elapsed,
                len(result.papers_found) if result.papers_found else 0,
                len(result.gaps) if result.gaps else 0,
                len(result.ideas) if result.ideas else 0,
                len(result.proposals) if result.proposals else 0,
            )
            return result

        except Exception as e:
            elapsed = time.time() - t0
            dag_logger.log_error(
                stage="pipeline",
                event="fatal_error",
                error=str(e),
                elapsed_s=elapsed,
            )
            logger.error("DAG run %s failed after %.1fs: %s", run_id, elapsed, e)
            raise
