"""Composition Root — factory for wiring PipelineOrchestrator dependencies.

Extracted from PipelineOrchestrator.__init__ to isolate dependency wiring
from orchestration logic. The composition root is the ONLY place that
knows how to assemble the orchestrator's components.

This module creates:
- Provider chain (inner provider → GatewayProvider → StageAwareProvider)
- Service registry (search, embedding, memory, KG, etc.)
- Stage executor, result processor, lifecycle
- Gateway, capability registry, token budgeter
- Model manager, task router, model selector

Usage::

    deps = CompositionRoot.create(settings, provider, stage_callback, strategy)
    orchestrator = PipelineOrchestrator(deps=deps)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider
    from backend.config import Settings

logger = logging.getLogger(__name__)


class CompositionRoot:
    """Assembles all PipelineOrchestrator dependencies.

    This is a pure factory — it creates and wires objects but
    contains no runtime behavior. Called once per orchestrator
    instance.
    """

    @staticmethod
    def create(
        settings: "Settings",
        provider: "LLMProvider | None",
        stage_callback,
        strategy: str | None,
    ) -> dict:
        """Create and wire all orchestrator dependencies.

        Returns a dict of named components that the orchestrator
        stores as attributes.
        """
        from backend.config import get_settings
        from backend.pipeline.registry import get_registry

        settings = settings or get_settings()
        registry = get_registry()

        # Guard against Settings passed as provider
        if provider is not None and not hasattr(provider, "structured_output"):
            logger.warning(
                "PipelineOrchestrator received %s as 'provider'; ignoring and creating default",
                type(provider).__name__,
            )
            provider = None

        provider = provider or registry.create(settings=settings)
        cost_tracker = registry.cost_tracker

        components: dict = {
            "provider": provider,
            "cost_tracker": cost_tracker,
            "stage_callback": stage_callback,
            "settings": settings,
            "registry": registry,
            "_last_stage_retries": 0,
        }

        # ── Model Manager ─────────────────────────────────
        components["_model_manager"] = None
        try:
            from backend.providers.model_manager import get_model_manager
            mm = get_model_manager()
            if mm.is_initialized:
                components["_model_manager"] = mm
                assignments = mm.get_assignments()
                logger.info(
                    "Universal Model Manager wired to orchestrator (%d stages assigned)",
                    len(assignments),
                )
        except Exception as e:
            logger.debug("ModelManager not available, using legacy routing: %s", e)

        components["_mm_stage_aliases"] = {
            "proposal_deepening": "deepening",
        }

        # ── Model Selector (hybrid routing) ───────────────
        components["_model_selector"] = None
        components["_thinking_provider"] = None
        if getattr(settings, 'lmstudio_enabled', False) or getattr(settings, 'thinking_model', ''):
            try:
                from backend.pipeline.model_selection import ModelSelector
                components["_model_selector"] = ModelSelector(settings)
                components["_thinking_provider"] = components["_model_selector"].resolve('classify')
                logger.info(
                    "Hybrid model routing enabled: thinking=%s, generation=%s",
                    getattr(components["_thinking_provider"], 'provider_name', 'local'),
                    provider.provider_name if hasattr(provider, 'provider_name') else 'cloud',
                )
            except Exception as e:
                logger.warning("Model selector init failed, using single provider: %s", e)

        # ── Strategy ──────────────────────────────────────
        # Strategy resolution requires the orchestrator's _load_yaml_strategy
        # which is an instance method. We store the name and let the
        # orchestrator resolve it. This avoids circular dependency.
        components["_strategy_name"] = strategy or "deep_research"

        # ── Task Router ───────────────────────────────────
        components["_task_router"] = None
        if getattr(settings, "model_routing_enabled", False) or getattr(settings, "cost_routing_enabled", False):
            from backend.providers.task_router import create_router
            components["_task_router"] = create_router(
                registry=registry,
                cost_tracker=cost_tracker,
                settings=settings,
            )

        logger.info("CompositionRoot: wiring complete for strategy '%s'", components["_strategy_name"])
        return components


def init_orchestrator(orchestrator, settings, provider, stage_callback, strategy):
    """Initialize an orchestrator instance using CompositionRoot.

    This is called from PipelineOrchestrator.__init__ and sets all
    the attributes that the old __init__ body used to set inline.
    """
    from backend.pipeline.tracing import InMemoryProcessor
    from backend.pipeline.governance.guardrails import default_input_guardrails

    components = CompositionRoot.create(settings, provider, stage_callback, strategy)

    # Set all components as orchestrator attributes
    for key, value in components.items():
        setattr(orchestrator, key, value)

    # Tracing
    orchestrator._trace_processor = InMemoryProcessor()

    # Guardrails
    orchestrator._input_guardrails = default_input_guardrails()

    # Strategy config (needs instance method)
    orchestrator._strategy_config = orchestrator._load_yaml_strategy(orchestrator._strategy_name)
    logger.info("Pipeline strategy: %s (from pipeline.yaml)", orchestrator._strategy_name)

    # The remaining wiring (gateway, services, executor, lifecycle)
    # requires the orchestrator instance to exist, so it stays in __init__.
    # This function handles the first phase of wiring; __init__ handles
    # the second phase that needs cross-references.
