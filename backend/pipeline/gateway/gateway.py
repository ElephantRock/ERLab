"""LLM Gateway — the single entry point for all LLM calls.

Every LLM interaction in the pipeline should pass through this gateway.
It provides:
- Token budgeting (refuse oversized prompts)
- Capability-aware routing (right model for the task)
- Output validation (mechanical repair, semantic flagging)
- Call logging (every call recorded for observability)
- Degraded result semantics (no fake-perfect scores)

Flow:
    LLMRequest → resolve model → check budget → compile context →
    execute → validate → log → return LLMResponse
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.gateway.capability_registry import ModelCapabilities, ModelCapabilityRegistry
from backend.pipeline.gateway.token_budget import PromptTooLargeError, TokenBudgeter

logger = logging.getLogger(__name__)


@dataclass
class LLMRequest:
    """Unified request spec for all LLM calls."""

    task: str                         # e.g., "proposal_synthesis", "citation_audit"
    messages: list[dict]              # the prompt
    max_output_tokens: int = 4096     # desired output length
    temperature: float = 0.7
    schema: dict | None = None        # if set, uses structured_output
    tools: list[dict] | None = None   # if set, uses complete_with_tools
    role: str = "draft"               # "draft", "reason", "synthesize", "critique"
    risk_level: str = "normal"        # "low", "normal", "high"
    requires_independent_judgment: bool = False
    stage: str = ""                   # pipeline stage name
    run_id: str = ""                  # pipeline run ID
    context_window_override: int | None = None  # force a specific context size


@dataclass
class LLMResponse:
    """Gateway response with full observability."""

    content: str | dict               # the LLM output
    input_tokens: int = 0
    output_tokens: int = 0
    model_used: str = ""
    provider: str = ""
    confidence: float = 1.0           # 0-1, based on validation
    warnings: list[str] = field(default_factory=list)
    fallback_used: bool = False       # true if compaction/splitting happened
    degraded: bool = False            # true if result is degraded
    latency_ms: float = 0.0

    @property
    def is_reliable(self) -> bool:
        """Whether this response is reliable enough to use without review."""
        return self.confidence >= 0.5 and not self.degraded


@dataclass
class GatewayCallLog:
    """Record of a single gateway call for observability."""

    timestamp: float
    task: str
    stage: str
    run_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    confidence: float
    fallback_used: bool
    degraded: bool
    warnings: list[str]
    error: str | None = None
    # SmartRouter fields
    routed_model: str = ""
    routed_strategy: str = ""
    routing_confidence: float = 0.0
    routing_degraded: bool = False
    routing_reason: str = ""
    enforcement_applied: bool = False
    certification_status: str = ""
    stage_eligibility: str = ""
    hard_gate_failures: list[str] = field(default_factory=list)


class LLMGateway:
    """Single entry point for ALL LLM calls in the pipeline.

    Usage:
        gateway = LLMGateway(registry, budgeter)
        response = await gateway.call(LLMRequest(
            task="proposal_synthesis",
            messages=[...],
            max_output_tokens=4096,
            role="synthesize",
        ))
    """

    def __init__(
        self,
        capability_registry: ModelCapabilityRegistry,
        token_budgeter: TokenBudgeter,
        default_model: str = "",
    ):
        self._registry = capability_registry
        self._budgeter = token_budgeter
        self._default_model = default_model
        self._call_log: list[GatewayCallLog] = []
        self._provider_fn = None  # set via set_provider_fn

        # SmartRouter (optional, set via set_smart_router)
        self._smart_router = None
        self._routing_mode = "disabled"  # disabled | dry_run | enforce
        self._dry_run_logger = None

        # Hard pre-call budget authority (optional, set via set_budget_authority).
        # When set, every billable call through call() is reserved before it
        # proceeds and reconciled after. None = no cost enforcement (legacy).
        self._budget_authority = None

    def set_budget_authority(self, authority) -> None:
        """Set the run-scoped hard budget authority.

        When set, LLMGateway.call() reserves a conservative maximum cost
        before each provider call and reconciles actual usage after. A
        refused call raises BudgetExceededError (a PromptTooLargeError
        subclass) so GatewayProvider re-raises rather than billing via the
        inner fallback.
        """
        self._budget_authority = authority

    def set_provider_fn(self, fn) -> None:
        """Set the function that executes LLM calls.

        Signature: async fn(messages, temperature, max_tokens, schema=None, tools=None) -> str | dict
        """
        self._provider_fn = fn

    def set_smart_router(self, router, mode: str = "dry_run", dry_run_logger=None, enforced_stages: list[str] | None = None) -> None:
        """Set the SmartRouter for routing decisions.

        Args:
            router: SmartRouter instance.
            mode: "disabled", "dry_run", or "enforce".
            dry_run_logger: DryRunLogger instance for logging decisions.
            enforced_stages: List of stage names to enforce routing for.
                Other stages will be dry-run or legacy even in enforce mode.
        """
        self._smart_router = router
        self._routing_mode = mode
        self._dry_run_logger = dry_run_logger
        self._enforced_stages = set(enforced_stages) if enforced_stages else set()

    async def call(self, request: LLMRequest) -> LLMResponse:
        """Execute an LLM call through the full gateway pipeline."""

        t0 = time.monotonic()
        error = None
        response = None

        try:
            # ── Hard pre-call budget reservation (if authority is set) ──
            # This is the single chokepoint covering every billable call.
            # The refusal exception subclasses PromptTooLargeError, so the
            # except clause below re-raises it rather than degrading.
            budget_projection = None
            if self._budget_authority is not None:
                # Conservative maximum: estimate input tokens from the
                # request plus the full requested output reserve, then let
                # the authority translate that into a worst-case cost.
                est_input = sum(len(str(m.get("content", "")).split())
                                for m in (request.messages or []))
                est_output = request.max_output_tokens or 4096
                budget_projection = self._budget_authority.project_call(
                    max_input_tokens=est_input,
                    max_output_tokens=est_output,
                    stage=request.stage or request.task or "",
                    run_id=request.run_id,
                )
                _reservation_id = self._budget_authority.reserve(budget_projection)

            # 0. SmartRouter routing (if enabled)
            routing_decision = None
            enforcement_applied = False
            if self._smart_router and self._routing_mode != "disabled":
                routing_decision = self._route_request(request)
                request._routing_decision = routing_decision  # attach for logging

                # Determine if this stage should be enforced
                stage = request.stage or request.task or ""
                is_enforced = stage in self._enforced_stages

                if is_enforced and routing_decision:
                    if self._routing_mode == "enforce":
                        enforcement_applied = True
                        # Check if routing decision is degraded (no valid candidate)
                        if routing_decision.degraded:
                            logger.warning(
                                "[ENFORCE] stage=%s DEGRADED: %s",
                                stage, routing_decision.reason,
                            )
                            # Return degraded result explicitly
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            return LLMResponse(
                                content="",
                                confidence=0.0,
                                degraded=True,
                                warnings=[
                                    f"SmartRouter enforcement: no certified candidate for '{stage}'",
                                    f"Reason: {routing_decision.reason}",
                                ],
                                latency_ms=elapsed_ms,
                            )
                        else:
                            logger.info(
                                "[ENFORCE] stage=%s model=%s strategy=%s confidence=%.2f",
                                stage, routing_decision.model_id,
                                routing_decision.strategy, routing_decision.confidence,
                            )
                    elif self._routing_mode == "dry_run" and self._dry_run_logger:
                        self._dry_run_logger.log(
                            routing_decision,
                            actual_model_used=self._default_model,
                            actual_strategy="legacy",
                            actual_provider="default",
                            run_id=request.run_id,
                        )
                        logger.info(
                            "[DRY-RUN] stage=%s routed=%s/%s actual=%s confidence=%.2f",
                            stage, routing_decision.model_id, routing_decision.strategy,
                            self._default_model, routing_decision.confidence,
                        )
                elif not is_enforced and routing_decision and self._dry_run_logger:
                    # Non-enforced stage: dry-run logging only
                    self._dry_run_logger.log(
                        routing_decision,
                        actual_model_used=self._default_model,
                        actual_strategy="legacy",
                        actual_provider="default",
                        run_id=request.run_id,
                    )
                    logger.info(
                        "[DRY-RUN] stage=%s routed=%s/%s actual=%s confidence=%.2f",
                        stage, routing_decision.model_id, routing_decision.strategy,
                        self._default_model, routing_decision.confidence,
                    )

            request._enforcement_applied = enforcement_applied

            # 1. Resolve model capabilities
            model_id = self._default_model
            caps = self._resolve_model(request, model_id)

            # 2. Pre-flight token check
            ctx_window = request.context_window_override or caps.context_window
            budget = self._budgeter.check(
                request.messages,
                request.max_output_tokens,
                context_window=ctx_window,
            )

            # 3. If prompt doesn't fit, try to adapt
            messages = request.messages
            fallback_used = False

            if not budget.fits:
                # Try reducing max_output to fit
                reduced_output = budget.available_for_output
                if reduced_output >= 256:
                    logger.info(
                        "Reducing output budget: %d → %d to fit context",
                        request.max_output_tokens, reduced_output,
                    )
                    request.max_output_tokens = reduced_output
                    budget = self._budgeter.check(
                        messages, reduced_output, context_window=ctx_window,
                    )
                    fallback_used = True
                else:
                    # Prompt is genuinely too large
                    raise PromptTooLargeError(
                        input_tokens=budget.input_tokens,
                        output_reserve=request.max_output_tokens,
                        context_window=ctx_window,
                        available=budget.available_for_input,
                    )

            # 4. Execute the LLM call
            if self._provider_fn is None:
                raise RuntimeError("LLMGateway has no provider function. Call set_provider_fn() first.")

            # Propagate the authoritative request context (stage, run_id) to
            # the provider callback. Detect whether the callback accepts these
            # kwargs so legacy callbacks (without stage/run_id params) still work.
            import contextlib
            import inspect as _inspect

            _cb_params: set = set()
            with contextlib.suppress(ValueError, TypeError):
                _cb_params = set(_inspect.signature(self._provider_fn).parameters)
            _ctx_kwargs: dict = {}
            if "stage" in _cb_params:
                _ctx_kwargs["stage"] = request.stage
            if "run_id" in _cb_params:
                _ctx_kwargs["run_id"] = request.run_id

            content = await self._provider_fn(
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_output_tokens,
                schema=request.schema,
                tools=request.tools,
                **_ctx_kwargs,
            )

            # 5. Validate output
            warnings = self._validate_output(content, request)
            confidence = self._score_confidence(warnings, caps)

            # 6. Build response
            elapsed_ms = (time.monotonic() - t0) * 1000
            response = LLMResponse(
                content=content,
                input_tokens=budget.input_tokens,
                output_tokens=self._estimate_output_tokens(content),
                model_used=caps.model_id,
                provider=caps.provider,
                confidence=confidence,
                warnings=warnings,
                fallback_used=fallback_used,
                latency_ms=elapsed_ms,
            )

            # ── Reconcile the budget reservation with actual usage ──
            if self._budget_authority is not None and budget_projection is not None:
                actual_cost = self._budget_authority.cost_for_tokens(
                    response.input_tokens, response.output_tokens,
                )
                self._budget_authority.reconcile(_reservation_id, actual_cost)

            return response

        except PromptTooLargeError:
            # Includes BudgetExceededError (refusal). A refused call never
            # reached the provider, so there is no reservation to release —
            # reserve() raised before any reservation was recorded.
            raise  # propagate to caller for compaction/splitting
        except Exception as e:
            # Provider/transport failure: release the outstanding reservation
            # so the budget authority does not hold a phantom reservation.
            if self._budget_authority is not None:
                self._budget_authority.release(_reservation_id)
            error = str(e)[:200]
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error("Gateway call failed for task '%s': %s", request.task, error)

            # Q2 (Case-3 3B–3D specimens): transport/provider failure
            # keeps its identity instead of becoming success-shaped
            # empty content. The StageExecutor's bounded retries and
            # typed stage-failure machinery take over from here.
            from backend.pipeline.gateway.transport import (
                GatewayTransportError,
            )

            raise GatewayTransportError(
                request.task or request.stage or "unknown",
                error,
            ) from e

        finally:
            # Always log
            self._log_call(request, response, error)

    def _resolve_model(self, request: LLMRequest, default_model: str) -> ModelCapabilities:
        """Resolve model capabilities for this request."""
        model_id = default_model or self._default_model
        return self._registry.get(model_id)

    def _route_request(self, request: LLMRequest) -> Any:
        """Ask SmartRouter for a routing decision. Returns RoutingDecision or None."""
        try:
            from backend.pipeline.routing.smart_router import RoutingRuntimeContext
            from backend.pipeline.routing.stage_contract import (
                get_contract,
                load_contracts,
            )

            stage = request.stage or request.task
            if not stage:
                logger.debug("No stage/task for routing, skipping")
                return None

            contracts = load_contracts()

            # Try direct match first
            contract = None
            try:
                contract = get_contract(stage, contracts)
            except KeyError:
                pass

            # Try normalized match (e.g., 'gap_analysis' -> no contract, skip)
            if contract is None:
                # Map common internal stage names to contract names
                stage_map = {
                    "complete": None,  # generic, skip
                    "structured_output": None,  # generic, skip
                    "literature_search": "literature_search",
                    "gap_analysis": None,  # no direct LLM routing
                    "idea_generation": "idea_generation",
                    "novelty_checking": "idea_generation",
                    "feasibility_scoring": "idea_generation",
                    "proposal_synthesis": "proposal_synthesis",
                    "adversarial_review": "adversarial_review",
                    "paper_synthesis": "paper_synthesis",
                    "citation_audit": "citation_audit",
                    "evidence_repair": "repair",
                    "repair": "repair",
                    "query_generation": "query_generation",
                    "proposal_deepening": "proposal_synthesis",
                    "evaluation": "adversarial_review",
                    "export": None,
                    "ingestion": "literature_search",
                    "retrieval": "literature_search",
                }
                mapped = stage_map.get(stage)
                if mapped is None:
                    logger.debug("No contract mapping for stage '%s', skipping routing", stage)
                    return None
                try:
                    contract = get_contract(mapped, contracts)
                except KeyError:
                    logger.debug("No contract for mapped stage '%s', skipping", mapped)
                    return None

            ctx = RoutingRuntimeContext(
                run_id=request.run_id,
            )
            decision = self._smart_router.route(contract, ctx)
            return decision

        except Exception as e:
            logger.warning("SmartRouter routing failed for stage '%s': %s",
                           request.stage or request.task, e)
            return None

    def _validate_output(self, content: str | dict, request: LLMRequest) -> list[str]:
        """Validate LLM output. Returns list of warnings.

        Only performs mechanical validation here:
        - JSON validity check (if schema was requested)
        - Empty output check
        - Basic sanity checks

        Does NOT perform semantic validation (citation grounding, claim evidence).
        That's the ClaimEvidenceValidator's job.
        """
        warnings = []

        # Empty output
        if not content:
            warnings.append("Empty output from LLM")
            return warnings

        # String output sanity
        if isinstance(content, str):
            if len(content) < 10:
                warnings.append(f"Suspiciously short output: {len(content)} chars")
            return warnings

        # Dict output (structured) — check basic validity
        if isinstance(content, dict):
            if request.schema:
                # Check required keys exist
                required = request.schema.get("required", [])
                properties = request.schema.get("properties", {})
                if isinstance(properties, dict):
                    for key in required:
                        if key not in content:
                            warnings.append(f"Missing required field: {key}")

            # Check for None/null values in required fields
            for key, value in content.items():
                if value is None:
                    warnings.append(f"Null value in field: {key}")

        return warnings

    def _score_confidence(self, warnings: list[str], caps: ModelCapabilities) -> float:
        """Assign confidence score based on warnings and model reliability.

        Starts at 1.0, reduced by:
        - Each warning: -0.1
        - Model reliability: scales confidence by reliability score
        """
        score = 1.0

        # Penalty per warning
        score -= len(warnings) * 0.1

        # Scale by model's overall reliability
        reliability_scores = caps.reliability.values()
        if reliability_scores:
            avg_reliability = sum(reliability_scores) / len(reliability_scores)
            score *= avg_reliability

        return max(0.0, min(1.0, score))

    def _estimate_output_tokens(self, content: str | dict) -> int:
        """Estimate output tokens."""
        if isinstance(content, str):
            return int(len(content) / 3.8)
        return int(len(str(content)) / 3.8)

    def _log_call(self, request: LLMRequest, response: LLMResponse | None, error: str | None) -> None:
        """Log every call for observability."""
        # Extract routing decision if available
        routed_model = ""
        routed_strategy = ""
        routing_confidence = 0.0
        routing_degraded = False
        routing_reason = ""
        enforcement_applied = getattr(request, '_enforcement_applied', False)
        certification_status = ""
        stage_eligibility = ""
        hard_gate_failures = []

        if hasattr(request, '_routing_decision') and request._routing_decision:
            rd = request._routing_decision
            routed_model = rd.model_id
            routed_strategy = rd.strategy
            routing_confidence = rd.confidence
            routing_degraded = rd.degraded
            routing_reason = rd.reason
            stage_eligibility = getattr(rd, 'eligibility', '')
            hard_gate_failures = getattr(rd, 'warnings', [])
            # Certification status from routing decision
            if routing_degraded:
                certification_status = "no_certified_candidate"
            elif routed_model:
                certification_status = "certified"
            else:
                certification_status = "unknown"

        entry = GatewayCallLog(
            timestamp=time.time(),
            task=request.task,
            stage=request.stage,
            run_id=request.run_id,
            model=response.model_used if response else "",
            provider=response.provider if response else "",
            input_tokens=response.input_tokens if response else 0,
            output_tokens=response.output_tokens if response else 0,
            latency_ms=response.latency_ms if response else 0,
            confidence=response.confidence if response else 0,
            fallback_used=response.fallback_used if response else False,
            degraded=response.degraded if response else True,
            warnings=response.warnings if response else [],
            error=error,
            routed_model=routed_model,
            routed_strategy=routed_strategy,
            routing_confidence=round(routing_confidence, 3),
            routing_degraded=routing_degraded,
            routing_reason=routing_reason,
            enforcement_applied=enforcement_applied,
            certification_status=certification_status,
            stage_eligibility=stage_eligibility,
            hard_gate_failures=hard_gate_failures,
        )
        self._call_log.append(entry)

        # Keep log bounded (last 1000 calls)
        if len(self._call_log) > 1000:
            self._call_log = self._call_log[-500:]

    def get_call_log(self, run_id: str = "", stage: str = "", limit: int = 100) -> list[dict]:
        """Get call log entries, optionally filtered."""
        entries = self._call_log
        if run_id:
            entries = [e for e in entries if e.run_id == run_id]
        if stage:
            entries = [e for e in entries if e.stage == stage]

        entries = entries[-limit:]

        return [
            {
                "timestamp": e.timestamp,
                "task": e.task,
                "stage": e.stage,
                "run_id": e.run_id,
                "model": e.model,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "latency_ms": round(e.latency_ms, 1),
                "confidence": round(e.confidence, 2),
                "fallback_used": e.fallback_used,
                "degraded": e.degraded,
                "warnings": e.warnings,
                "error": e.error,
                "routed_model": e.routed_model,
                "routed_strategy": e.routed_strategy,
                "routing_confidence": e.routing_confidence,
                "routing_degraded": e.routing_degraded,
                "routing_reason": e.routing_reason,
                "enforcement_applied": e.enforcement_applied,
                "certification_status": e.certification_status,
                "stage_eligibility": e.stage_eligibility,
                "hard_gate_failures": e.hard_gate_failures,
            }
            for e in entries
        ]
