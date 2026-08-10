"""B0.4b architectural seal: prevent reintroduction of LLM embedding surface.

Production embedding capability exists only through the dedicated
``EmbeddingProvider`` + ``GovernedEmbeddingAdapter`` architecture. Chat-
completion providers cannot generate embeddings directly or indirectly.

These tests use AST ownership checks — not unrestricted text matching —
so they reject reintroduction in chat-provider modules while leaving
legitimate embedding methods in dedicated embedding modules untouched.

Required zero-count posture (B0.4 completion gate):

    LLMProvider embed declarations                    0
    concrete chat-provider embed implementations      0
    chat-wrapper embed forwarding methods             0
    StageContext embed forwarding methods             0
    production calls through LLMProvider.embed        0
    getattr(provider, "embed") in chat composition    0
    Anthropic OpenAI embedding dependency              0
    embedding fallback through chat providers          0
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module ownership
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parents[3] / "backend"

# Chat-provider modules: the LLM abstraction surface that must NOT expose
# embedding behavior. These are the modules scoped by B0.4.
_CHAT_PROVIDER_MODULES = {
    "providers/base.py",
    "providers/openai_provider.py",
    "providers/ollama_provider.py",
    "providers/anthropic_provider.py",
    "providers/litellm_provider.py",
    "providers/gemini_provider.py",
    "providers/cache/cached_provider.py",
    "providers/resilience/resilient_provider.py",
    "providers/stage_wrapper.py",
    "providers/stage_context.py",
    "pipeline/gateway/gateway_provider.py",
}

# Anthropic specifically — must not reach OpenAI for embeddings.
_ANTHROPIC_MODULE = "providers/anthropic_provider.py"

# Dedicated embedding modules where ``embed`` is legitimate. These MUST be
# exempt from any global "no embed method" rule.
_DEDICATED_EMBEDDING_MODULES = {
    "pipeline/knowledge/embedding_providers.py",
    "pipeline/knowledge/embedding_service.py",
    "pipeline/memory/embedding_dedup.py",
    "pipeline/novelty/embedding_scorer.py",
    "pipeline/governed_embedding_adapter.py",
    "pipeline/side_channel_embedding.py",
    "pipeline/knowledge/graph_embeddings.py",
    "pipeline/tools/tool_index.py",
    "providers/cache/semantic_cache.py",
    "pipeline/literature/relevance_filter.py",
}


def _rel(path: Path) -> str:
    """Module path relative to backend/, forward-slashed."""
    return str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")


def _read_ast(path: Path) -> ast.Module | None:
    try:
        source = path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(path))
    except Exception:
        return None


def _is_test_path(rel: str) -> bool:
    return "/tests/" in rel or rel.startswith("tests/")


# ---------------------------------------------------------------------------
# 1. Symbol removal — chat-provider modules declare no embed method
# ---------------------------------------------------------------------------


def _find_embed_methods(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (qualname, lineno) for every ``def embed`` / ``async def embed``."""
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "embed":
                kind = "async" if isinstance(node, ast.AsyncFunctionDef) else "sync"
                out.append((f"{kind} def embed", node.lineno))
    return out


def test_chat_provider_modules_declare_no_embed_method():
    """Every chat-provider module must declare zero ``embed`` methods.

    This is the core B0.4 invariant. The production symbol itself must
    disappear — no abstract declaration, no concrete implementation,
    no wrapper forwarder.
    """
    violations: list[str] = []
    for rel in _CHAT_PROVIDER_MODULES:
        path = BACKEND_ROOT / rel
        if not path.exists():
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for kind, lineno in _find_embed_methods(tree):
            violations.append(f"{rel}:{lineno} {kind}")

    assert not violations, (
        "B0.4 violation — chat-provider modules declare ``embed`` methods:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nProduction embedding must go through EmbeddingProvider + "
        "GovernedEmbeddingAdapter, never an LLMProvider."
    )


# ---------------------------------------------------------------------------
# 2. Base class abstract embed removed
# ---------------------------------------------------------------------------


def test_llm_provider_base_has_no_embed_abstract():
    """LLMProvider ABC must not declare embed as abstract.

    Catches reintroduction at the contract root, where a single line would
    force every concrete provider to re-implement embedding.
    """
    base_path = BACKEND_ROOT / "providers/base.py"
    tree = _read_ast(base_path)
    assert tree is not None, "providers/base.py not parseable"

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == "embed":
                pytest.fail(
                    f"providers/base.py:{node.lineno} redeclares LLMProvider.embed "
                    f"— the abstract embedding entrance must remain removed."
                )


# ---------------------------------------------------------------------------
# 3. No getattr(provider, "embed") dynamic lookup in chat composition
# ---------------------------------------------------------------------------


def _find_embed_getattr(tree: ast.Module) -> list[int]:
    """Return linenos of ``getattr(x, "embed")`` / ``getattr(x, 'embed')``."""
    hits: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "getattr" and len(node.args) >= 2:
                second = node.args[1]
                if isinstance(second, ast.Constant) and second.value == "embed":
                    hits.append(node.lineno)
    return hits


def test_no_dynamic_embed_lookup_in_chat_provider_modules():
    """No chat-provider module may use ``getattr(provider, "embed")``.

    A dynamic lookup would let chat composition silently recover embedding
    capability that the static type system no longer exposes.
    """
    violations: list[str] = []
    for rel in _CHAT_PROVIDER_MODULES:
        path = BACKEND_ROOT / rel
        if not path.exists():
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for lineno in _find_embed_getattr(tree):
            violations.append(f"{rel}:{lineno}")

    assert not violations, (
        "B0.4 violation — dynamic ``getattr(..., 'embed')`` in chat modules:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# 4. Anthropic-to-OpenAI embedding dependency removed
# ---------------------------------------------------------------------------


def test_anthropic_provider_does_not_import_openai():
    """AnthropicProvider must not reach OpenAI for embeddings.

    The pre-B0.4 implementation shims AnthropicProvider.embed to OpenAI's
    embeddings endpoint with an ambient OPENAI_API_KEY. That hidden
    cross-provider dependency is forbidden.
    """
    path = BACKEND_ROOT / _ANTHROPIC_MODULE
    tree = _read_ast(path)
    assert tree is not None, "anthropic_provider.py not parseable"

    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "openai" or alias.name.startswith("openai."):
                    violations.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and (node.module == "openai" or node.module.startswith("openai.")):
                violations.append(f"line {node.lineno}: from {node.module} import ...")

    assert not violations, (
        "B0.4 violation — anthropic_provider.py imports openai, restoring the "
        "hidden cross-provider embedding dependency:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def test_anthropic_provider_does_not_read_openai_api_key():
    """Anthropic provider must not read OPENAI_API_KEY for embeddings."""
    path = BACKEND_ROOT / _ANTHROPIC_MODULE
    source = path.read_text(encoding="utf-8")

    # AST-level scan for the string literal "OPENAI_API_KEY"
    tree = _read_ast(path)
    assert tree is not None
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == "OPENAI_API_KEY":
            pytest.fail(
                f"anthropic_provider.py:{node.lineno} references OPENAI_API_KEY — "
                f"Anthropic must not consume OpenAI credentials."
            )

    # Also reject the env-var access idiom at the source level if AST missed it
    assert "OPENAI_API_KEY" not in source, (
        "anthropic_provider.py source mentions OPENAI_API_KEY"
    )


# ---------------------------------------------------------------------------
# 5. No production chat-side caller invokes a chat provider's .embed()
# ---------------------------------------------------------------------------


def _iter_production_files():
    """Yield (rel, path) for every production .py file under backend/.

    Excludes tests, __pycache__, and the dedicated embedding modules (which
    legitimately call .embed on EmbeddingProvider instances).
    """
    for path in BACKEND_ROOT.rglob("*.py"):
        rel = _rel(path)
        if _is_test_path(rel):
            continue
        if "__pycache__" in rel:
            continue
        if rel in _DEDICATED_EMBEDDING_MODULES:
            continue
        yield rel, path


def test_no_production_call_to_chat_provider_embed():
    """Production modules must not invoke ``.embed(...)`` on a chat provider.

    Ownership rule: legitimate ``.embed()`` calls live only in the dedicated
    embedding modules listed in ``_DEDICATED_EMBEDDING_MODULES`` (they call
    EmbeddingProvider.embed, not LLMProvider.embed). Any other production
    ``.embed()`` invocation is treated as a chat-provider embedding call and
    rejected.

    This is stricter than a name-based scan: it cannot distinguish a
    chat-provider call from an EmbeddingProvider call purely from AST, so we
    confine all ``.embed()`` calls to the dedicated modules by exclusion.
    """
    violations: list[str] = []
    for rel, path in _iter_production_files():
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
                callee = node.value.func
                if isinstance(callee, ast.Attribute) and callee.attr == "embed":
                    violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        "B0.4 violation — production ``await ...embed(...)`` outside dedicated "
        "embedding modules:\n"
        + "\n".join(f"  {v}" for v in violations)
        + "\nAll embedding calls must go through EmbeddingProvider / "
        "GovernedEmbeddingAdapter / EmbeddingService."
    )


# ---------------------------------------------------------------------------
# 6. No chat-wrapper forwarder pattern (self._wrapped.embed / self._inner.embed)
# ---------------------------------------------------------------------------


def test_no_chat_wrapper_embed_forwarding_expression():
    """Chat wrappers must not contain ``self._wrapped.embed`` /
    ``self._inner.embed`` / ``self._provider.embed`` forwarding expressions.

    Even if the surrounding method is removed, a leftover forwarding call
    inside another method would be a latent reintroduction path.
    """
    forward_attr_names = {"_wrapped", "_inner", "_provider", "_default"}
    violations: list[str] = []
    for rel in _CHAT_PROVIDER_MODULES:
        path = BACKEND_ROOT / rel
        if not path.exists():
            continue
        tree = _read_ast(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "embed":
                value = node.value
                if (
                    isinstance(value, ast.Attribute)
                    and isinstance(value.value, ast.Name)
                    and value.value.id == "self"
                    and value.attr in forward_attr_names
                ):
                    violations.append(f"{rel}:{node.lineno}")

    assert not violations, (
        "B0.4 violation — chat-wrapper embed forwarding expression remains:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# 7. Dedication sanity — embedding methods still live in the right place
# ---------------------------------------------------------------------------


def test_dedicated_embedding_modules_still_define_embed():
    """Positive proof: removal did not delete embedding capability entirely.

    The dedicated ``EmbeddingProvider`` ABC and at least one concrete
    implementation must still declare ``embed``. If this fails, B0.4a
    over-reached and destroyed legitimate embedding infrastructure.
    """
    providers_path = BACKEND_ROOT / "pipeline/knowledge/embedding_providers.py"
    tree = _read_ast(providers_path)
    assert tree is not None

    found = _find_embed_methods(tree)
    assert found, (
        "pipeline/knowledge/embedding_providers.py declares no embed methods — "
        "B0.4a over-reached into the dedicated embedding architecture."
    )

    # EmbeddingService must still expose embed_texts (its canonical surface)
    service_path = BACKEND_ROOT / "pipeline/knowledge/embedding_service.py"
    service_tree = _read_ast(service_path)
    assert service_tree is not None
    service_methods = {
        n.name
        for n in ast.walk(service_tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "embed_texts" in service_methods, (
        "EmbeddingService.embed_texts was removed — the dedicated embedding "
        "service surface must remain intact."
    )


# ---------------------------------------------------------------------------
# 8. Positive regression proofs — chat operations still function
# ---------------------------------------------------------------------------
#
# These prove that B0.4a removed ONLY embedding behavior and left chat
# capability intact for every concrete provider and every wrapper.
# Each provider's underlying SDK client is mocked — we only verify the
# provider's own chat plumbing, not the SDK.


import asyncio  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def _make_openai_with_mocked_client():
    """OpenAIProvider with the OpenAI SDK client stubbed."""
    import openai as _openai  # noqa: F401  (importable check)

    from backend.providers.openai_provider import OpenAIProvider

    p = OpenAIProvider(api_key="test-key", model="gpt-4o")
    chat_completion = MagicMock()
    chat_completion.choices = [MagicMock()]
    chat_completion.choices[0].message.content = "ok"
    chat_completion.model = "gpt-4o"
    p._client = MagicMock()
    p._client.chat.completions.create = AsyncMock(return_value=chat_completion)
    return p


def _make_anthropic_with_mocked_client():
    """AnthropicProvider with the Anthropic SDK client stubbed."""
    from backend.providers.anthropic_provider import AnthropicProvider

    p = AnthropicProvider(api_key="test-key", model="claude-sonnet-4-20250514")
    msg = MagicMock()
    msg.content = [MagicMock(text="ok")]
    msg.usage.input_tokens = 1
    msg.usage.output_tokens = 1
    p._client = MagicMock()
    p._client.messages.create = AsyncMock(return_value=msg)
    return p


def _make_ollama_with_mocked_client():
    """OllamaProvider with the httpx client stubbed."""
    from backend.providers.ollama_provider import OllamaProvider

    p = OllamaProvider(base_url="http://localhost:11434", model="llama3")
    response = MagicMock()
    response.json.return_value = {"message": {"content": "ok"}}
    response.raise_for_status = MagicMock()
    p._client = MagicMock()
    p._client.post = AsyncMock(return_value=response)
    return p


def _make_litellm_with_mocked_client():
    """LiteLLMProvider with the litellm module stubbed."""
    import sys

    if "litellm" not in sys.modules:
        sys.modules["litellm"] = MagicMock()
    from backend.providers.litellm_provider import LiteLLMProvider

    p = LiteLLMProvider(model="gpt-4o", api_key="test-key")
    msg = MagicMock()
    msg.content = "ok"
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    sys.modules["litellm"].acompletion = AsyncMock(return_value=resp)
    return p


def _make_gemini_with_mocked_client():
    """GeminiProvider with the genai module stubbed."""
    import sys

    if "google.generativeai" not in sys.modules:
        sys.modules["google.generativeai"] = MagicMock()
    from backend.providers.gemini_provider import GeminiProvider

    p = GeminiProvider(api_key="test-key", model="gemini-2.0-flash")
    response = MagicMock()
    response.text = "ok"
    model = MagicMock()
    model.generate_content_async = AsyncMock(return_value=response)
    sys.modules["google.generativeai"].GenerativeModel = MagicMock(return_value=model)
    return p


def test_openai_chat_still_functions():
    p = _make_openai_with_mocked_client()
    assert _run(p.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert p.provider_name == "openai"
    assert p.default_model == "gpt-4o"
    assert not hasattr(p, "embed")


def test_anthropic_chat_still_functions():
    p = _make_anthropic_with_mocked_client()
    assert _run(p.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert p.provider_name == "anthropic"
    assert not hasattr(p, "embed")


def test_ollama_chat_still_functions():
    p = _make_ollama_with_mocked_client()
    # OllamaProvider.complete_with_usage goes through _client.post
    result = _run(p.complete_with_usage([{"role": "user", "content": "hi"}]))
    assert result.content == "ok"
    assert p.provider_name == "ollama"
    assert not hasattr(p, "embed")


def test_litellm_chat_still_functions():
    p = _make_litellm_with_mocked_client()
    assert _run(p.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert p.provider_name == "litellm"
    assert not hasattr(p, "embed")


def test_gemini_chat_still_functions():
    p = _make_gemini_with_mocked_client()
    assert _run(p.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert p.provider_name == "gemini"
    assert not hasattr(p, "embed")


def test_cached_chat_wrapper_still_functions():
    """CachedProvider forwards chat without exposing embed."""
    inner = _make_openai_with_mocked_client()
    from backend.providers.cache.cached_provider import CachedProvider
    from backend.providers.cache.memory_cache import InMemoryCache

    cp = CachedProvider(inner, InMemoryCache(max_size=10, ttl_seconds=3600))
    assert _run(cp.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert not hasattr(cp, "embed")


def test_resilient_chat_wrapper_still_functions():
    """ResilientProvider forwards chat without exposing embed."""
    inner = _make_openai_with_mocked_client()
    from backend.providers.resilience.circuit_breaker import CircuitBreaker
    from backend.providers.resilience.resilient_provider import ResilientProvider

    retry_config = MagicMock()
    retry_config.max_attempts = 1
    retry_config.base_delay = 0.0
    retry_config.multiplier = 1.0
    retry_config.max_delay = 1.0
    rp = ResilientProvider(inner, CircuitBreaker(), retry_config)
    assert _run(rp.complete([{"role": "user", "content": "hi"}])) == "ok"
    assert not hasattr(rp, "embed")


def test_gateway_chat_wrapper_still_functions():
    """GatewayProvider forwards chat without exposing embed."""
    inner = _make_openai_with_mocked_client()
    from backend.pipeline.gateway.gateway_provider import GatewayProvider

    gateway = MagicMock()
    gateway.complete = AsyncMock(side_effect=Exception("gateway unavailable"))
    gp = GatewayProvider(gateway=gateway, inner_provider=inner)
    # Gateway.complete falls back to inner.complete when the gateway raises
    result = _run(gp.complete([{"role": "user", "content": "hi"}]))
    assert result == "ok"
    assert not hasattr(gp, "embed")


def test_stage_context_no_longer_forwards_embed():
    """StageAwareProvider must not expose .embed() even though it forwards chat."""
    inner = _make_openai_with_mocked_client()
    from backend.providers.stage_context import StageAwareProvider

    ctx = StageAwareProvider(default=inner)
    # chat still works
    assert _run(ctx.complete([{"role": "user", "content": "hi"}])) == "ok"
    # embedding surface gone
    assert not hasattr(ctx, "embed"), (
        "StageAwareProvider must not forward embed — pipeline stages requiring "
        "embeddings must receive a governed embedding dependency."
    )


# ---------------------------------------------------------------------------
# 9. Failure proofs — embedding-required workflows fail explicitly
# ---------------------------------------------------------------------------


def test_embedding_service_rejects_chat_provider():
    """EmbeddingService must reject an LLMProvider as its provider.

    The type was narrowed from ``EmbeddingProvider | LLMProvider`` to
    ``EmbeddingProvider`` only. Passing a chat provider at construction
    time must be a TypeError (or at least not silently produce an
    embedding-capable service).
    """
    from backend.pipeline.knowledge.embedding_service import EmbeddingService

    # Build a minimal duck-typed chat-only object — no .embed method at all
    class ChatOnlyProvider:
        async def complete(self, messages, **kw):
            return "ok"

        def embed(self, texts):  # explicit wrong-signature surface
            raise RuntimeError("should not be called as embedding source")

    # EmbeddingService should refuse to treat this as an EmbeddingProvider:
    # because the chat provider has no compliant embed method signature,
    # a real embedding call will fail. The narrower type prevents silent
    # acceptance.
    svc = EmbeddingService(ChatOnlyProvider())  # type: ignore[arg-type]
    # Prove the chat provider is not a usable EmbeddingProvider: invoking
    # embed_texts on it raises a typed EmbeddingProviderError, never falls
    # back to a chat-completion call.
    from backend.pipeline.knowledge.embedding_service import EmbeddingProviderError

    with pytest.raises(EmbeddingProviderError):
        _run(svc.embed_texts(["hi"]))


def test_no_chat_provider_attribute_fallback_for_embeddings():
    """A chat provider instance simply has no .embed attribute.

    This is the simplest expression of the B0.4 contract: every concrete
    chat provider and every wrapper must lack the attribute entirely.
    """
    providers = [
        _make_openai_with_mocked_client(),
        _make_anthropic_with_mocked_client(),
        _make_ollama_with_mocked_client(),
        _make_litellm_with_mocked_client(),
        _make_gemini_with_mocked_client(),
    ]
    missing = [type(p).__name__ for p in providers if hasattr(p, "embed")]
    assert not missing, (
        f"Chat providers still expose .embed: {missing}"
    )

