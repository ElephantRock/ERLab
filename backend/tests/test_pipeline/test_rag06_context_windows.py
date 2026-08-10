"""Tests for BATCH-RAG-06: Context Window Registry."""


from backend.pipeline.knowledge.context_windows import (
    MODEL_CONTEXT_REGISTRY,
    ModelContextInfo,
    get_model_context,
    get_recommended_budget,
    list_models,
)


def test_registry_has_models():
    """Registry contains known models."""
    assert "qwen/qwen3-4b-2507" in MODEL_CONTEXT_REGISTRY
    assert "gpt-4o" in MODEL_CONTEXT_REGISTRY
    assert "default" in MODEL_CONTEXT_REGISTRY


def test_exact_match():
    """get_model_context finds exact match."""
    info = get_model_context("qwen/qwen3-4b-2507")
    assert info.max_tokens == 4096
    assert info.provider == "local"


def test_prefix_match():
    """get_model_context falls back to prefix match."""
    info = get_model_context("qwen/qwen3-4b-2507-instruct")
    assert info.family == "qwen"


def test_family_match():
    """get_model_context falls back to family match."""
    info = get_model_context("my-custom-llama-v2")
    assert info.family == "llama"


def test_default_fallback():
    """get_model_context returns default for unknown model."""
    info = get_model_context("completely-unknown-model-xyz")
    assert info.model_id == "default"
    assert info.max_tokens == 4096


def test_recommended_budget():
    """get_recommended_budget returns 80% of max by default."""
    budget = get_recommended_budget("qwen/qwen3-4b-2507")
    assert budget == int(4096 * 0.8)


def test_recommended_budget_custom_factor():
    """get_recommended_budget accepts custom safety factor."""
    budget = get_recommended_budget("qwen/qwen3-4b-2507", safety_factor=0.5)
    assert budget == 2048


def test_cloud_model_larger_context():
    """Cloud models have larger context windows."""
    local = get_model_context("qwen/qwen3-4b-2507")
    cloud = get_model_context("gpt-4o")
    assert cloud.max_tokens > local.max_tokens


def test_list_models():
    """list_models returns all non-default models."""
    models = list_models()
    assert len(models) > 0
    assert all("model_id" in m for m in models)
    assert all("max_tokens" in m for m in models)
    # Default should not be in the list
    assert not any(m["model_id"] == "default" for m in models)


def test_model_context_info_recommended_budget_auto():
    """ModelContextInfo auto-calculates recommended_budget."""
    info = ModelContextInfo(
        model_id="test-model",
        max_tokens=10000,
        provider="local",
    )
    assert info.recommended_budget == 8000


def test_model_context_info_explicit_budget():
    """ModelContextInfo respects explicit recommended_budget."""
    info = ModelContextInfo(
        model_id="test-model",
        max_tokens=10000,
        provider="local",
        recommended_budget=5000,
    )
    assert info.recommended_budget == 5000
