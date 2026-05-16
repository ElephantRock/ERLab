"""LLM Gateway — centralized control plane for all LLM calls.

Provides token budgeting, capability-aware routing, output validation,
and observability for every LLM interaction in the pipeline.

Architecture:
    GatewayProvider (LLMProvider adapter)
        → LLMGateway.call(LLMRequest)
            → TokenBudgeter.check()
            → ContextCompiler.compile()
            → SmartRouter.route()
            → provider.complete() / structured_output()
            → OutputValidator.validate()
            → CallLogger.log()
"""
