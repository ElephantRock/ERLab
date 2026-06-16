"""Model selector — maps pipeline stages to the best available model.

Replaces the 4-layer routing stack (ProviderFactory, TaskRouter,
LLMGateway, SmartRouter) with one simple selector that considers:
  1. Stage requirements (context, JSON, tools, thinking)
  2. Hardware constraints (VRAM)
  3. Measured capabilities (reliability, latency)
  4. Adversarial exclusion (different model for review)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.providers.catalog import ModelCatalog, ModelInfo
from backend.providers.hardware import GPUInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage requirements — what each pipeline stage actually needs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageRequirements:
    """What a pipeline stage actually needs from a model.

    Derived from the spec matrix analysis of actual stage code.
    """

    stage_name: str
    min_context: int = 4096
    min_output_tokens: int = 1024
    requires_json: bool = False
    requires_tools: bool = False
    requires_thinking: bool = False
    requires_different_model: bool = False  # for adversarial review
    creativity_level: str = "medium"  # low | medium | high
    quality_tier: int = 1  # 0-5: 0=no LLM, 1=basic, 5=creative


# Predefined requirements per stage — from the spec matrix
STAGE_REQUIREMENTS: dict[str, StageRequirements] = {
    # Tier 1: Basic instruction following
    "literature_search": StageRequirements(
        stage_name="literature_search",
        min_context=4096,
        min_output_tokens=512,
        quality_tier=1,
    ),
    "ingestion": StageRequirements(
        stage_name="ingestion",
        min_context=2048,
        min_output_tokens=256,
        quality_tier=1,
    ),
    "query_generation": StageRequirements(
        stage_name="query_generation",
        min_context=4096,
        min_output_tokens=512,
        quality_tier=1,
    ),
    "reranking": StageRequirements(
        stage_name="reranking",
        min_context=4096,
        min_output_tokens=256,
        quality_tier=1,
    ),
    "mechanical_metrics": StageRequirements(
        stage_name="mechanical_metrics",
        min_context=0,
        min_output_tokens=0,
        quality_tier=0,  # No LLM needed
    ),
    "export": StageRequirements(
        stage_name="export",
        min_context=0,
        min_output_tokens=0,
        quality_tier=0,  # No LLM needed
    ),
    # Tier 2: Instruction following + JSON-in-text
    "gap_analysis": StageRequirements(
        stage_name="gap_analysis",
        min_context=8192,
        min_output_tokens=4096,
        requires_json=True,
        quality_tier=2,
    ),
    "evaluation": StageRequirements(
        stage_name="evaluation",
        min_context=4096,
        min_output_tokens=1500,
        quality_tier=2,
    ),
    "gap_reflection": StageRequirements(
        stage_name="gap_reflection",
        min_context=4096,
        min_output_tokens=1024,
        quality_tier=2,
    ),
    "idea_reflection": StageRequirements(
        stage_name="idea_reflection",
        min_context=4096,
        min_output_tokens=1024,
        quality_tier=2,
    ),
    "deepening": StageRequirements(
        stage_name="deepening",
        min_context=4096,
        min_output_tokens=512,
        quality_tier=1,
    ),
    # Tier 3: structured_output + precision
    "novelty_checking": StageRequirements(
        stage_name="novelty_checking",
        min_context=4096,
        min_output_tokens=2048,
        requires_json=True,
        quality_tier=3,
    ),
    "feasibility_scoring": StageRequirements(
        stage_name="feasibility_scoring",
        min_context=4096,
        min_output_tokens=2048,
        requires_json=True,
        quality_tier=3,
    ),
    "citation_audit": StageRequirements(
        stage_name="citation_audit",
        min_context=16384,
        min_output_tokens=2048,
        requires_json=True,
        quality_tier=3,
    ),
    "governance": StageRequirements(
        stage_name="governance",
        min_context=4096,
        min_output_tokens=2048,
        requires_json=True,
        quality_tier=3,
    ),
    # Tier 4: High context + high output
    "proposal_synthesis": StageRequirements(
        stage_name="proposal_synthesis",
        min_context=16384,
        min_output_tokens=8192,
        quality_tier=4,
    ),
    "paper_synthesis": StageRequirements(
        stage_name="paper_synthesis",
        min_context=32768,
        min_output_tokens=8192,
        requires_json=True,
        quality_tier=4,
    ),
    # Tier 5: Creative + different model
    "idea_generation": StageRequirements(
        stage_name="idea_generation",
        min_context=8192,
        min_output_tokens=4096,
        requires_json=True,
        creativity_level="high",
        quality_tier=5,
    ),
    "adversarial_review": StageRequirements(
        stage_name="adversarial_review",
        min_context=8192,
        min_output_tokens=2048,
        requires_json=True,
        requires_different_model=True,
        quality_tier=5,
    ),
}


def get_stage_requirements(stage_name: str) -> StageRequirements:
    """Get requirements for a stage, with sensible defaults for unknown stages."""
    if stage_name in STAGE_REQUIREMENTS:
        return STAGE_REQUIREMENTS[stage_name]
    # Default: moderate requirements
    return StageRequirements(stage_name=stage_name)


# ---------------------------------------------------------------------------
# ModelSelector
# ---------------------------------------------------------------------------


class ModelSelector:
    """Selects the best model for a stage based on requirements and measurements.

    This replaces SmartRouter + TaskRouter + LLMGateway + ProviderFactory
    routing logic. One simple question: "What's the best model for this stage?"
    """

    def __init__(
        self,
        catalog: ModelCatalog,
        gpu: GPUInfo | None = None,
        preferred_model: str | None = None,
    ) -> None:
        self._catalog = catalog
        self._gpu = gpu
        self._preferred_model = preferred_model
        self._assignments: dict[str, str] = {}  # stage → model_id (cached)
        self._model_used_by: dict[str, str] = {}  # model_id → stage (for adversarial exclusion)

    def select(
        self,
        stage: str,
        exclude_models: set[str] | None = None,
    ) -> ModelInfo | None:
        """Select the best available model for a pipeline stage.

        Args:
            stage: Pipeline stage name (e.g. "proposal_synthesis").
            exclude_models: Models to exclude (for adversarial review).

        Returns:
            Best ModelInfo, or None if no model meets requirements.
        """
        req = get_stage_requirements(stage)

        # Stages that don't need LLM
        if req.quality_tier == 0:
            return None

        # ── Preferred model override ────────────────────────────────
        # When a preferred_model is configured and meets the stage's
        # requirements, use it directly. This gives the operator an
        # explicit, predictable choice instead of relying on the
        # fitness-score heuristic.
        if self._preferred_model and not exclude_models:
            pm = self._catalog.get_model(self._preferred_model)
            if pm and pm.health_status != "unreachable":
                meets_ctx = pm.context_length >= req.min_context
                meets_tools = (not req.requires_tools) or pm.supports_tools
                meets_thinking = (not req.requires_thinking) or pm.supports_thinking
                if meets_ctx and meets_tools and meets_thinking:
                    logger.debug(
                        "Preferred model '%s' used for stage '%s'",
                        pm.model_id, stage,
                    )
                    self._assignments[stage] = pm.model_id
                    return pm
                else:
                    logger.info(
                        "Preferred model '%s' does not meet requirements "
                        "for stage '%s' (ctx=%d/%d, tools=%s/%s, thinking=%s/%s) "
                        "— falling back to fitness selection",
                        pm.model_id, stage,
                        pm.context_length, req.min_context,
                        pm.supports_tools, req.requires_tools,
                        pm.supports_thinking, req.requires_thinking,
                    )

        # Get candidates that meet requirements
        candidates = self._catalog.get_models_for_stage(
            min_context=req.min_context,
            requires_json=req.requires_json,
            requires_tools=req.requires_tools,
            requires_thinking=req.requires_thinking,
            gpu=self._gpu,
        )

        # Filter out excluded models (adversarial review needs a different model)
        if exclude_models:
            candidates = [m for m in candidates if m.model_id not in exclude_models]

        if not candidates:
            logger.warning(
                "No model meets requirements for stage '%s' "
                "(min_ctx=%d, json=%s, tools=%s, thinking=%s, excluded=%s)",
                stage,
                req.min_context,
                req.requires_json,
                req.requires_tools,
                req.requires_thinking,
                exclude_models,
            )
            # Graceful degradation: prefer loaded models, then configured model
            fallback = self._catalog.get_healthy_models()
            if fallback:
                # 1. Prefer already-loaded models (no hot-swap needed)
                loaded = [m for m in fallback if m.is_loaded]
                if loaded:
                    fallback = loaded
                # 2. Among those, prefer the configured default model
                if self._preferred_model:
                    match = [
                        m for m in fallback
                        if m.model_id == self._preferred_model
                    ]
                    if match:
                        fallback = match
                logger.info(
                    "Graceful degradation: using %s for stage '%s'",
                    fallback[0].model_id,
                    stage,
                )
                return fallback[0]
            return None

        best = candidates[0]
        self._assignments[stage] = best.model_id
        return best

    def assign_all(self) -> dict[str, ModelInfo]:
        """Assign models to all stages. Returns stage → ModelInfo mapping.

        Handles adversarial review exclusion automatically: the review stage
        gets a different model than the generation stages.
        """
        assignments: dict[str, ModelInfo] = {}
        generator_model_id: str | None = None

        # First pass: assign all non-adversarial stages
        for stage_name, req in STAGE_REQUIREMENTS.items():
            if req.quality_tier == 0:
                continue  # Skip non-LLM stages

            if req.requires_different_model:
                continue  # Handle in second pass

            model = self.select(stage_name)
            if model:
                assignments[stage_name] = model
                self._model_used_by[model.model_id] = stage_name

                # Track which model generates proposals/papers
                if stage_name in ("proposal_synthesis", "paper_synthesis"):
                    generator_model_id = model.model_id

        # Second pass: assign adversarial review with generator exclusion
        for stage_name, req in STAGE_REQUIREMENTS.items():
            if not req.requires_different_model:
                continue

            exclude = {generator_model_id} if generator_model_id else set()
            model = self.select(stage_name, exclude_models=exclude)

            # If excluding the generator leaves only unloaded models,
            # skip the exclusion — using the same (loaded) model is
            # better than hot-swapping to a cold model that causes
            # multi-minute load delays.
            if model and not model.is_loaded and generator_model_id:
                gen_model = self._catalog.get_model(generator_model_id)
                if gen_model and gen_model.is_loaded:
                    logger.info(
                        "Adversarial review: using same model as generator "
                        "(%s) — no loaded alternative available",
                        generator_model_id,
                    )
                    model = gen_model

            if model:
                assignments[stage_name] = model
                self._model_used_by[model.model_id] = stage_name

        return assignments

    def get_assignment(self, stage: str) -> str | None:
        """Get the model_id assigned to a stage."""
        return self._assignments.get(stage)

    def get_all_assignments(self) -> dict[str, str]:
        """Return stage → model_id mapping."""
        return dict(self._assignments)
