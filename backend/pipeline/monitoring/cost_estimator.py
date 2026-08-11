"""Pre-flight cost and time estimation for pipeline runs.

Ported from huggingface/ml-intern agent/core/cost_estimation.py (Apache 2.0).
Estimates cost and duration before a pipeline run starts.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# ── Model pricing (per 1M tokens, input/output) ──────────────────────
# Local models via LM Studio are free. Cloud models have known prices.
MODEL_PRICING: dict[str, dict[str, float]] = {
    # Local models (free — compute cost is electricity)
    "qwen/qwen3-4b-2507": {"input": 0.0, "output": 0.0, "label": "local (LM Studio)"},
    "text-embedding-bge-m3": {"input": 0.0, "output": 0.0, "label": "local (LM Studio GPU)"},
    "system": {"input": 0.0, "output": 0.0, "label": "system (no LLM)"},
    # Cloud models via z.ai proxy
    "glm-5.1": {"input": 0.15, "output": 0.60, "label": "cloud (z.ai)"},
    # Codebase-wide documented assumption: glm-5.2 uses glm-5.1 pricing parity
    # until a dedicated production price is configured.
    "glm-5.2": {"input": 0.15, "output": 0.60, "label": "cloud (z.ai; glm-5.1 pricing parity)"},
    "gpt-4o": {"input": 2.50, "output": 10.00, "label": "cloud (OpenAI)"},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00, "label": "cloud (Anthropic)"},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 0.0, "output": 0.0, "label": "unknown"}

# ── Average token usage per stage (from historical runs) ─────────────
STAGE_AVG_TOKENS: dict[str, dict[str, int]] = {
    "literature_search": {"input": 2000, "output": 5000},
    "ingestion": {"input": 30000, "output": 500},
    "gap_analysis": {"input": 15000, "output": 3000},
    "gap_reflection": {"input": 5000, "output": 2000},
    "idea_generation": {"input": 10000, "output": 4000},
    "idea_reflection": {"input": 5000, "output": 2000},
    "novelty_checking": {"input": 8000, "output": 1000},
    "feasibility_scoring": {"input": 8000, "output": 2000},
    "mechanical_metrics": {"input": 500, "output": 200},
    "proposal_synthesis": {"input": 20000, "output": 30000},
    "adversarial_review": {"input": 25000, "output": 5000},
    "evaluation": {"input": 15000, "output": 3000},
    "experiment_execution": {"input": 0, "output": 0},
    "paper_synthesis": {"input": 20000, "output": 25000},
    "citation_audit": {"input": 10000, "output": 2000},
    "proposal_deepening": {"input": 25000, "output": 30000},
    "export": {"input": 500, "output": 500},
    "trimmer": {"input": 2000, "output": 500},
}

# ── Average time per stage (seconds) ─────────────────────────────────
STAGE_AVG_TIME: dict[str, float] = {
    "literature_search": 60.0,
    "ingestion": 45.0,
    "gap_analysis": 120.0,
    "gap_reflection": 30.0,
    "idea_generation": 180.0,
    "idea_reflection": 30.0,
    "novelty_checking": 60.0,
    "feasibility_scoring": 45.0,
    "mechanical_metrics": 5.0,
    "proposal_synthesis": 300.0,
    "adversarial_review": 120.0,
    "evaluation": 90.0,
    "experiment_execution": 60.0,
    "paper_synthesis": 240.0,
    "citation_audit": 60.0,
    "proposal_deepening": 180.0,
    "export": 10.0,
    "trimmer": 15.0,
}

# ── Strategy stage lists ─────────────────────────────────────────────
# pipeline.yaml is the production source of truth.  Keep this public mapping
# for callers/tests, but derive it instead of maintaining a second stage graph.
def _load_pipeline_truth() -> tuple[dict[str, list[str]], dict[str, str]]:
    try:
        from backend.pipeline.dag.config import ConfigLoader

        config = ConfigLoader().load()
        strategy_stages = {
            name: list(cfg.get("stages", []))
            for name, cfg in config.get("strategies", {}).items()
        }
        model_defaults = {
            category: str(cfg.get("model", ""))
            for category, cfg in config.get("models", {}).items()
            if isinstance(cfg, dict) and cfg.get("model")
        }
        return strategy_stages, model_defaults
    except Exception as exc:
        logger.warning("Could not load pipeline.yaml for cost estimation: %s", exc)
        # Fail-soft compatibility fallback. This mirrors the current production
        # topology rather than the historical pre-YAML estimator lists.
        return {
            "fast_scan": [
                "literature_search", "ingestion", "gap_analysis",
                "idea_generation", "feasibility_scoring",
                "proposal_synthesis", "export",
            ],
            "deep_research": [
                "literature_search", "ingestion", "gap_analysis",
                "gap_reflection", "idea_generation", "idea_reflection",
                "novelty_checking", "feasibility_scoring", "mechanical_metrics",
                "proposal_synthesis", "adversarial_review", "evaluation",
                "experiment_execution", "paper_synthesis", "citation_audit",
                "proposal_deepening", "export",
            ],
            "academic_proposal": [
                "literature_search", "ingestion", "gap_analysis",
                "gap_reflection", "idea_generation", "idea_reflection",
                "novelty_checking", "feasibility_scoring", "mechanical_metrics",
                "proposal_synthesis", "adversarial_review", "evaluation",
                "experiment_execution", "paper_synthesis", "citation_audit",
                "proposal_deepening", "export",
            ],
            "literature_review": [
                "literature_search", "ingestion", "gap_analysis", "export",
            ],
        }, {
            "thinking": "glm-5.2",
            "generation": "glm-5.2",
            "embedding": "text-embedding-bge-m3",
            "reranker": "qwen/qwen3-4b-2507",
        }


STRATEGY_STAGES, _YAML_MODEL_DEFAULTS = _load_pipeline_truth()

# ── Stage → model category mapping ──────────────────────────────────
STAGE_MODEL_CATEGORY: dict[str, str] = {
    "literature_search": "thinking",
    "ingestion": "embedding",
    "trimmer": "system",
    "gap_analysis": "thinking",
    "gap_reflection": "thinking",
    "idea_generation": "thinking",
    "idea_reflection": "thinking",
    "novelty_checking": "embedding",
    "feasibility_scoring": "thinking",
    "mechanical_metrics": "system",
    "proposal_synthesis": "generation",
    "adversarial_review": "thinking",
    "evaluation": "thinking",
    "experiment_execution": "system",
    "paper_synthesis": "generation",
    "citation_audit": "thinking",
    "proposal_deepening": "generation",
    "export": "system",
}

# ── Category → default model ─────────────────────────────────────────
# Model IDs also come from pipeline.yaml.  "system" denotes a non-LLM stage.
CATEGORY_DEFAULT_MODEL: dict[str, str] = {
    "thinking": _YAML_MODEL_DEFAULTS.get("thinking", "glm-5.2"),
    "generation": _YAML_MODEL_DEFAULTS.get("generation", "glm-5.2"),
    "embedding": _YAML_MODEL_DEFAULTS.get("embedding", "text-embedding-bge-m3"),
    "system": "system",
}


@dataclass
class CostEstimate:
    """Estimated cost and time for a pipeline run."""

    strategy: str
    stages: int
    estimated_cost_usd: float
    estimated_time_seconds: float
    local_cost_usd: float
    cloud_cost_usd: float
    breakdown: list[dict[str, Any]]  # per-stage cost

    @property
    def estimated_time_minutes(self) -> float:
        return self.estimated_time_seconds / 60.0

    @property
    def time_display(self) -> str:
        mins = self.estimated_time_minutes
        if mins < 1:
            return f"{self.estimated_time_seconds:.0f}s"
        return f"{mins:.1f} min"

    @property
    def cost_display(self) -> str:
        if self.estimated_cost_usd == 0:
            return "$0.00 (all local)"
        return f"${self.estimated_cost_usd:.4f}"


def get_model_pricing(model_id: str) -> dict[str, Any]:
    """Get pricing for a model. Falls back to default if unknown."""
    # Strip provider prefix
    clean = model_id.split("/")[-1] if "/" in model_id else model_id
    for key, pricing in MODEL_PRICING.items():
        if key in model_id or clean in key:
            return pricing
    return DEFAULT_PRICING


def estimate_run_cost(
    strategy: str,
    model_overrides: dict[str, str] | None = None,
    *,
    include_experiment: bool = False,
) -> CostEstimate:
    """Estimate cost and time for a pipeline run.

    Args:
        strategy: Pipeline strategy name (fast_scan, deep_research, etc.)
        model_overrides: Optional dict mapping stage name to model id.
                         If not provided, uses pipeline.yaml model routing.
        include_experiment: Include the opt-in experiment_execution stage.
                            False by default because ordinary frontend runs do
                            not provide an experiment_spec_id.

    Returns:
        CostEstimate with per-stage breakdown.
    """
    stages = list(STRATEGY_STAGES.get(strategy, STRATEGY_STAGES["deep_research"]))
    if not include_experiment:
        stages = [s for s in stages if s != "experiment_execution"]
    model_overrides = model_overrides or {}

    total_cost = 0.0
    local_cost = 0.0
    cloud_cost = 0.0
    total_time = 0.0
    breakdown = []

    for stage_name in stages:
        # Determine model for this stage
        if stage_name in model_overrides:
            model_id = model_overrides[stage_name]
        else:
            category = STAGE_MODEL_CATEGORY.get(stage_name, "system")
            model_id = CATEGORY_DEFAULT_MODEL.get(category, "qwen/qwen3-4b-2507")

        pricing = get_model_pricing(model_id)
        avg_tokens = STAGE_AVG_TOKENS.get(stage_name, {"input": 5000, "output": 2000})
        avg_time = STAGE_AVG_TIME.get(stage_name, 60.0)

        # Cost = (input_tokens / 1M) * input_price + (output_tokens / 1M) * output_price
        input_cost = (avg_tokens["input"] / 1_000_000) * pricing["input"]
        output_cost = (avg_tokens["output"] / 1_000_000) * pricing["output"]
        stage_cost = input_cost + output_cost

        total_cost += stage_cost
        total_time += avg_time

        if pricing["input"] == 0.0 and pricing["output"] == 0.0:
            local_cost += stage_cost
        else:
            cloud_cost += stage_cost

        breakdown.append({
            "stage": stage_name,
            "model": model_id,
            "label": pricing.get("label", "unknown"),
            "input_tokens": avg_tokens["input"],
            "output_tokens": avg_tokens["output"],
            "cost_usd": round(stage_cost, 6),
            "time_seconds": avg_time,
        })

    return CostEstimate(
        strategy=strategy,
        stages=len(stages),
        estimated_cost_usd=round(total_cost, 6),
        estimated_time_seconds=total_time,
        local_cost_usd=round(local_cost, 6),
        cloud_cost_usd=round(cloud_cost, 6),
        breakdown=breakdown,
    )
