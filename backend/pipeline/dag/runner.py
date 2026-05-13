"""DAGRunner — reads pipeline YAML and executes stages in declared order.

BATCH-180: The DAGRunner is the new pipeline execution engine.
It reads pipeline.yaml (via ConfigLoader), builds a stage execution plan
from the selected strategy, and runs stages sequentially.

AUTH-03: dry_run() prints the plan without executing anything.
"""
from __future__ import annotations

import io
import time
import uuid
from typing import Any, Callable

from .config import ConfigLoader
from .context import StageContext
from .registry import STAGE_REGISTRY
from .stage_log import StageLogger


class DAGRunner:
    """Read pipeline YAML and execute stages in declared order."""

    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        log_dir: str = "logs/pipeline",
    ) -> None:
        self._loader = config_loader or ConfigLoader()
        self._log_dir = log_dir

    # ── public API ────────────────────────────────────────────

    def load_config(self) -> dict[str, Any]:
        """Load and validate the pipeline YAML config."""
        return self._loader.load()

    def build_plan(self, strategy: str) -> list[str]:
        """Return the ordered list of stages for a strategy.

        Raises ``ValueError`` if the strategy name is unknown.
        """
        config = self.load_config()
        strategies = config.get("strategies", {})
        if strategy not in strategies:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Available: {', '.join(strategies.keys())}"
            )
        return list(strategies[strategy]["stages"])

    def run_stage(
        self,
        stage_name: str,
        ctx: StageContext,
        stage_fn: Callable[[StageContext], dict[str, Any] | None] | None = None,
    ) -> dict[str, Any]:
        """Execute a single stage and log the result.

        If *stage_fn* is ``None``, a no-op placeholder is used.
        Returns a dict with {status, elapsed_s, outputs, error}.
        """
        logger: StageLogger = ctx.log
        model_cat = STAGE_REGISTRY.get(stage_name, "thinking")
        model_cfg = ctx.config.get("models", {}).get(model_cat, {})

        start = time.time()

        # Log start
        logger.log(
            stage=stage_name,
            event="start",
            elapsed_s=0.0,
            config=model_cfg,
            inputs=self._count_inputs(ctx),
        )

        try:
            if stage_fn is not None:
                result = stage_fn(ctx)
            else:
                result = {}

            elapsed = time.time() - start
            outputs = result if isinstance(result, dict) else {}

            logger.log(
                stage=stage_name,
                event="complete",
                elapsed_s=elapsed,
                config=model_cfg,
                inputs=self._count_inputs(ctx),
                outputs=outputs,
            )

            return {"status": "complete", "elapsed_s": elapsed, "outputs": outputs, "error": None}

        except Exception as exc:
            elapsed = time.time() - start
            logger.log_error(
                stage=stage_name,
                event="error",
                elapsed_s=elapsed,
                error=str(exc),
                config=model_cfg,
                inputs=self._count_inputs(ctx),
            )
            return {"status": "error", "elapsed_s": elapsed, "outputs": {}, "error": str(exc)}

    def execute(
        self,
        domain: str,
        strategy: str = "deep_research",
        stage_fns: dict[str, Callable] | None = None,
    ) -> StageContext:
        """Execute the full pipeline for a domain and strategy.

        *stage_fns* is an optional mapping of stage_name → callable.
        Missing entries use no-op placeholders.
        """
        config = self.load_config()
        plan = self.build_plan(strategy)
        run_id = uuid.uuid4().hex[:12]

        logger = StageLogger(run_id=run_id, log_dir=self._log_dir)
        ctx = StageContext(
            domain=domain,
            config=config,
            run_id=run_id,
            strategy=strategy,
            log=logger,
        )

        for stage_name in plan:
            fn = (stage_fns or {}).get(stage_name)
            self.run_stage(stage_name, ctx, fn)

        return ctx

    def dry_run(
        self,
        domain: str,
        strategy: str = "deep_research",
        out: io.TextIOBase | None = None,
    ) -> str:
        """Print the execution plan without running any stages (AUTH-03).

        Returns the plan text. If *out* is provided, also writes to it.
        """
        config = self.load_config()
        plan = self.build_plan(strategy)
        models_cfg = config.get("models", {})

        lines: list[str] = [
            f"dry_run: strategy={strategy}, domain={domain}",
            "run_id: (not generated \u2014 dry run)",
            f"stages: {len(plan)}",
            "",
        ]

        for idx, stage_name in enumerate(plan, 1):
            model_cat = STAGE_REGISTRY.get(stage_name, "thinking")
            model_info = models_cfg.get(model_cat, {})
            model_name = model_info.get("model", "unknown")
            provider = model_info.get("provider", "unknown")
            lines.append(
                f"  {idx:>2}. {stage_name:<25s} → {model_cat} ({provider}/{model_name})"
            )

        lines.append("")
        text = "\n".join(lines)

        if out is not None:
            out.write(text)

        return text

    # ── internal helpers ──────────────────────────────────────

    @staticmethod
    def _count_inputs(ctx: StageContext) -> dict[str, int]:
        return {
            "papers_count": ctx.paper_count,
            "gaps_count": ctx.gap_count,
            "ideas_count": ctx.idea_count,
            "proposals_count": ctx.proposal_count,
        }
