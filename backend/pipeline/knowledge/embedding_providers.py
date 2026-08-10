"""Embedding provider abstraction — pluggable embedding backends.

Separates embedding generation from LLM completion, allowing different
models and providers for each task.

Reference: mem0 EmbedderFactory (11 providers), letta EmbeddingConfig (16 endpoint types).
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import Any

from backend.pipeline.knowledge.embedding_provider_identity import (
    EVIDENCE_SOURCE_CONFIGURED_ONLY,
    EVIDENCE_SOURCE_GEMINI_CONFIGURED_MODEL,
    EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL,
    EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST,
    EVIDENCE_SOURCE_OLLAMA_RESPONSE,
    EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL,
    ProviderEmbeddingBatch,
    ProviderModelIdentityEvidence,
)

logger = logging.getLogger(__name__)


# P0.4B0.1c follow-up (concurrency seal): the google.generativeai SDK exposes
# only ``configure(api_key=...)`` for setup — no per-client configuration —
# so all GeminiEmbeddingProvider instances share one process-wide
# configuration slot. Without serialization, instance B can ``configure``
# between instance A's ``configure`` and A's ``embed_content`` invocation,
# causing A's request to execute under B's identity.
#
# Process-wide serialization: a single ``threading.Lock`` serializes the
# complete synchronous critical section {configure, embed_content, evidence
# capture} across all event loops and threads. This is necessary because:
#   1. ``embed_content`` is synchronous and runs via ``asyncio.to_thread``
#   2. An ``asyncio.Lock`` only serializes at the coroutine level within one
#      event loop — two threads from different loops can interleave
#   3. A lock keyed by ``id(loop)`` does not coordinate across threads
#
# The lock is acquired inside a dedicated synchronous function called via
# ``asyncio.to_thread``, so it is never held across an ``await`` on the
# event-loop thread. A cancelled caller releases the lock because
# ``to_thread`` propagates ``CancelledError`` and the ``with`` block exits.
import threading

_gemini_sdk_lock = threading.Lock()


def _get_default_lmstudio_url() -> str:
    """Read LM Studio base URL from config, falling back to localhost."""
    try:
        from backend.config import get_settings
        return get_settings().lmstudio_base_url
    except Exception:
        return "http://localhost:1234/v1"


class EmbeddingProvider(ABC):
    """Abstract embedding provider."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    async def embed_with_evidence(self, texts: list[str]) -> ProviderEmbeddingBatch:
        """Embed and return vectors together with identity evidence.

        Default implementation delegates to ``embed()`` with
        ``evidence_source='configured_only'`` and no observed identity.
        Concrete providers that can capture stronger evidence (OpenAI
        response model, Ollama digest, LM Studio echo) override this.
        """
        from backend.pipeline.knowledge.embedding_provider_identity import (
            EVIDENCE_SOURCE_CONFIGURED_ONLY,
            ProviderEmbeddingBatch,
            ProviderModelIdentityEvidence,
        )

        embeddings = await self.embed(texts)
        evidence = ProviderModelIdentityEvidence(
            provider_kind=self.provider_name.split(":")[0] if ":" in self.provider_name else self.provider_name,
            requested_model=getattr(self, "_model", ""),
            evidence_source=EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )
        return ProviderEmbeddingBatch(
            embeddings=tuple(tuple(v) for v in embeddings),
            identity_evidence=evidence,
        )

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension for this provider."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging."""
        ...


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embeddings via the openai SDK."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        dimension_override: int | None = None,
    ):
        import openai

        self._client = openai.AsyncOpenAI(api_key=api_key) if api_key else openai.AsyncOpenAI()
        self._model = model
        self._dimension = dimension_override or self._default_dimension(model)
        # P0.4B0.1b: cached identity evidence from the most recent response.
        # None until the first successful embed call. This is observational
        # evidence only — B0.2 interprets it; this provider does NOT
        # classify posture.
        self._last_identity_evidence: ProviderModelIdentityEvidence | None = None

    @staticmethod
    def _default_dimension(model: str) -> int:
        dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dims.get(model, 1536)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        response = await self._client.embeddings.create(model=self._model, input=texts)
        # P0.4B0.1b: capture the response.model field. OpenAI's embeddings
        # API echoes the served model identifier on every response. We
        # retain it as evidence; B0.2's classifier decides whether the echo
        # is strong enough for stable_deployment or merely confirms
        # alias_only. We do NOT promote the echo to a stable identity here.
        reported_model = self._safe_reported_model(response)
        self._last_identity_evidence = ProviderModelIdentityEvidence(
            provider_kind="openai",
            requested_model=self._model,
            reported_model=reported_model,
            deployment_id=None,
            provider_revision=None,
            evidence_source=EVIDENCE_SOURCE_OPENAI_RESPONSE_MODEL
            if reported_model is not None
            else EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )
        return [item.embedding for item in response.data]

    async def embed_with_evidence(
        self, texts: list[str]
    ) -> ProviderEmbeddingBatch:
        """Embed and return vectors together with the captured identity evidence.

        New in P0.4B0.1b. ``embed`` keeps the legacy list-of-lists contract
        for backward compatibility; new governed paths should call this
        method so evidence is bound to the result rather than cached on
        the instance.
        """
        embeddings = await self.embed(texts)
        assert self._last_identity_evidence is not None  # set by embed()
        return ProviderEmbeddingBatch(
            embeddings=tuple(tuple(v) for v in embeddings),
            identity_evidence=self._last_identity_evidence,
        )

    @staticmethod
    def _safe_reported_model(response: Any) -> str | None:
        """Extract response.model defensively. Returns None if missing or malformed.

        The OpenAI SDK exposes ``response.model`` as a string. Some edge
        cases (proxies, future SDK revisions) may not populate it; in that
        case we return None rather than guess. None is honest — it tells
        B0.2 we have no evidence beyond the configured request.
        """
        try:
            reported = getattr(response, "model", None)
        except Exception:
            return None
        if isinstance(reported, str) and reported:
            return reported
        return None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return f"openai:{self._model}"

    @property
    def last_identity_evidence(self) -> ProviderModelIdentityEvidence | None:
        """Most recently captured identity evidence, or None if no embed call yet."""
        return self._last_identity_evidence


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embeddings via the generativeai SDK."""

    def __init__(
        self,
        model: str = "models/embedding-001",
        api_key: str | None = None,
    ):
        # P0.4B0.1c: capture the api_key on the instance rather than calling
        # genai.configure(api_key=...) once at construction and leaving global
        # state mutated forever. The genai SDK exposes only ``configure`` (no
        # per-client config), so we cannot fully avoid global mutation — but
        # we can bound it: ``_reconfigure_if_needed`` runs immediately before
        # each ``embed_content`` call, ensuring the per-instance intended
        # configuration is authoritative at the moment of use. Constructing
        # or using one GeminiEmbeddingProvider no longer silently redefines
        # the effective identity for an unrelated instance on its next call.
        #
        # P0.4B0.1c follow-up (concurrency seal): the SDK's process-global
        # configuration is not safe under overlapping calls — instance B can
        # mutate global state between A's configure and A's embed_content
        # invocation. ``_gemini_sdk_lock`` is a process-wide async lock held
        # across the entire {configure, embed_content, evidence-capture}
        # critical section so concurrent GeminiEmbeddingProvider instances
        # cannot observe each other's configuration mid-request.
        import google.generativeai as genai

        self._model = model
        self._api_key = api_key
        self._genai = genai
        # Apply the configuration once at construction so the very first
        # embed() call is correct even if no reconfigure runs first (defensive).
        # Construction-time configure is not under the lock because it runs
        # synchronously at instance creation; concurrent embed() calls acquire
        # the lock and re-establish their own configuration before use.
        self._reconfigure_if_needed()
        # P0.4B0.1c: identity evidence — Gemini's embed_content API returns
        # only {"embedding": [...]} and exposes no served-model identity.
        # We honestly report only the configured model; B0.2 will classify
        # this as alias_only unless stronger evidence appears elsewhere.
        self._last_identity_evidence: ProviderModelIdentityEvidence | None = None

    def _reconfigure_if_needed(self) -> None:
        """Bound the genai global configuration mutation.

        Called at construction and immediately before every embed_content
        invocation (under ``_gemini_sdk_lock``). Each GeminiEmbeddingProvider
        instance re-establishes its own api_key before use, so two instances
        with different keys cannot silently poison each other's effective
        configuration.
        """
        if self._api_key is not None:
            self._genai.configure(api_key=self._api_key)

    def _embed_under_global_lock(self, texts: list[str]) -> list[list[float]]:
        """Synchronous critical section: configure, embed, capture evidence.

        Called via ``asyncio.to_thread`` so the process-wide ``threading.Lock``
        is never held on the event-loop thread. The lock serializes the
        complete SDK critical section across all loops and threads.
        """
        with _gemini_sdk_lock:
            self._reconfigure_if_needed()
            result = self._genai.embed_content(
                model=self._model,
                content=texts,
                task_type="retrieval_document",
            )
            self._last_identity_evidence = ProviderModelIdentityEvidence(
                provider_kind="gemini",
                requested_model=self._model,
                reported_model=None,
                deployment_id=None,
                provider_revision=None,
                evidence_source=EVIDENCE_SOURCE_GEMINI_CONFIGURED_MODEL,
            )
            return result["embedding"]

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # P0.4B0.1c follow-up: the complete {configure, embed_content,
        # evidence-capture} critical section runs under a process-wide
        # threading.Lock inside a synchronous helper, invoked via
        # asyncio.to_thread so the lock is never held on the event-loop
        # thread across an await.
        return await asyncio.to_thread(self._embed_under_global_lock, texts)

    async def embed_with_evidence(
        self, texts: list[str]
    ) -> ProviderEmbeddingBatch:
        """Embed and return vectors together with the captured identity evidence.

        New in P0.4B0.1c. Mirrors OpenAIEmbeddingProvider.embed_with_evidence.
        """
        embeddings = await self.embed(texts)
        assert self._last_identity_evidence is not None
        return ProviderEmbeddingBatch(
            embeddings=tuple(tuple(v) for v in embeddings),
            identity_evidence=self._last_identity_evidence,
        )

    @property
    def dimension(self) -> int:
        dims = {
            "models/embedding-001": 768,
            "models/text-embedding-004": 768,
        }
        return dims.get(self._model, 768)

    @property
    def provider_name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def last_identity_evidence(self) -> ProviderModelIdentityEvidence | None:
        """Most recently captured identity evidence, or None if no embed call yet."""
        return self._last_identity_evidence


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama embeddings via local HTTP API."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str | None = None,
    ):
        import httpx

        if base_url is None:
            try:
                from backend.config import get_settings
                base_url = get_settings().ollama_base_url
            except Exception:
                base_url = "http://localhost:11434"
        self._client = httpx.AsyncClient(timeout=60.0)
        self._model = model
        self._base_url = base_url
        self._dim: int | None = None
        # P0.4B0.1d: lazy-captured identity evidence. Ollama's /api/embeddings
        # response carries only {"embedding": [...]}; the served-model identity
        # (digest, family) is only available via /api/show. We probe /api/show
        # once on the first embed() call and cache the evidence; if the probe
        # fails (Ollama down, model not loaded), evidence stays NULL honestly
        # rather than fabricating an alias.
        self._identity_evidence: ProviderModelIdentityEvidence | None = None
        self._identity_probe_attempted = False

    async def _probe_identity_evidence(self) -> None:
        """Probe Ollama /api/show for the loaded model's immutable digest.

        Idempotent — runs at most once per instance. On any failure (network,
        HTTP error, missing digest field), leaves evidence NULL.
        """
        if self._identity_probe_attempted:
            return
        self._identity_probe_attempted = True

        try:
            response = await self._client.post(
                f"{self._base_url}/api/show",
                json={"name": self._model},
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            # Cannot reach Ollama or model not loaded. Leave evidence NULL;
            # the first embed() call will still report requested_model honestly
            # via evidence_source = ollama_response (the embedding endpoint
            # itself succeeded).
            return

        digest = data.get("digest") if isinstance(data, dict) else None
        if not isinstance(digest, str) or not digest:
            return

        # digest is Ollama's immutable artifact identity (e.g.
        # "sha256:abc123..."). B0.2 may classify this as exact_revision.
        # We do NOT classify here — only capture.
        self._identity_evidence = ProviderModelIdentityEvidence(
            provider_kind="ollama",
            requested_model=self._model,
            reported_model=self._model,
            deployment_id=None,
            provider_revision=digest,
            evidence_source=EVIDENCE_SOURCE_OLLAMA_API_SHOW_DIGEST,
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # P0.4B0.1d: probe /api/show once for immutable digest evidence.
        # The probe is best-effort; failure leaves evidence NULL honestly.
        await self._probe_identity_evidence()

        embeddings = []
        for text in texts:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            response.raise_for_status()
            emb = response.json()["embedding"]
            embeddings.append(emb)
            if self._dim is None:
                self._dim = len(emb)

        # If /api/show did not yield evidence, fall back to recording the
        # requested model + the embedding-endpoint as the evidence source.
        # This is honest: 'ollama_response' means 'we got vectors from the
        # embedding endpoint but no served-model identity'.
        if self._identity_evidence is None:
            self._identity_evidence = ProviderModelIdentityEvidence(
                provider_kind="ollama",
                requested_model=self._model,
                reported_model=self._model,
                deployment_id=None,
                provider_revision=None,
                evidence_source=EVIDENCE_SOURCE_OLLAMA_RESPONSE,
            )

        return embeddings

    async def embed_with_evidence(
        self, texts: list[str]
    ) -> ProviderEmbeddingBatch:
        """Embed and return vectors together with the captured identity evidence."""
        embeddings = await self.embed(texts)
        assert self._identity_evidence is not None
        return ProviderEmbeddingBatch(
            embeddings=tuple(tuple(v) for v in embeddings),
            identity_evidence=self._identity_evidence,
        )

    @property
    def dimension(self) -> int:
        return self._dim or 768

    @property
    def provider_name(self) -> str:
        return f"ollama:{self._model}"

    @property
    def last_identity_evidence(self) -> ProviderModelIdentityEvidence | None:
        """Most recently captured identity evidence, or None if no embed call yet."""
        return self._identity_evidence


class LMStudioEmbeddingOutputError(RuntimeError):
    """Raised when LM Studio returns a malformed response.

    Per directive B0.1e: malformed output is an explicit failure, not a
    silent skip. Distinct from network/HTTP exceptions (which propagate
    as their own types) so callers can distinguish output-contract
    failures from connectivity failures.
    """


class LMStudioEmbeddingProvider(EmbeddingProvider):
    """Embeddings via LM Studio's OpenAI-compatible /v1/embeddings endpoint.

    Supports all embedding models loaded in LM Studio on the GPU machine.
    Uses the standard OpenAI embeddings API format.

    Available models on the configured LM Studio instance.
      - text-embedding-nomic-embed-text-v2-moe  (768d, general text)
      - text-embedding-bge-m3                  (1024d, multilingual)
      - sfr-embedding-mistral                   (1024d, high-quality English)
      - nomic-embed-code                        (1024d, code/technical)
      - text-embedding-ms-marco-minilm-l6-v2    (384d, fast search)
      - text-embedding-nomic-embed-text-v1.5    (768d, legacy nomic)
    """

    # Known model dimensions
    MODEL_DIMENSIONS: dict[str, int] = {
        "text-embedding-nomic-embed-text-v2-moe": 768,
        "text-embedding-bge-m3": 1024,
        "sfr-embedding-mistral": 1024,
        "nomic-embed-code": 1024,
        "text-embedding-ms-marco-minilm-l6-v2": 384,
        "text-embedding-nomic-embed-text-v1.5": 768,
    }

    def __init__(
        self,
        model: str = "text-embedding-bge-m3-embeddings",
        base_url: str = "",
        dimension_override: int | None = None,
        batch_size: int = 32,
    ):
        import httpx

        # Normalize model name: LM Studio may report 'text-embedding-bge-m3-embeddings'
        # while older configs use 'text-embedding-bge-m3'. Map both to the loaded model.
        # P0.4B0.1e: the configured (post-rewrite) model is recorded as
        # deployment_id evidence — it's the model LM Studio reported as loaded
        # via /v1/models at orchestrator init (see service_registry.py:63-77).
        # This is *evidence* only; B0.2's classifier decides whether the
        # endpoint/deployment configuration justifies stable_deployment or
        # only alias_only.
        if model == "text-embedding-bge-m3":
            model = "text-embedding-bge-m3-embeddings"
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._client = httpx.AsyncClient(timeout=120.0)
        self._dimension = dimension_override or self.MODEL_DIMENSIONS.get(model, 1024)
        # P0.4B0.1e: cached identity evidence from the most recent response.
        # None until the first successful embed call.
        self._last_identity_evidence: ProviderModelIdentityEvidence | None = None

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using LM Studio's /v1/embeddings endpoint.

        P0.4B0.1e fail-closed repair: provider failures now propagate as
        explicit exceptions. Pre-B0 this method silently caught every
        exception and substituted ``[0.0] * dimension`` placeholder
        vectors, which (a) defeated downstream EmbeddingService zero-vector
        rejection in subtle ways and (b) fabricated evidence of a
        successful embedding when none occurred. The directive requires:

          successful request -> embeddings + resolved model evidence
          provider failure    -> explicit exception, zero fabricated vectors
          malformed output    -> explicit output-contract failure
        """
        all_embeddings: list[list[float]] = []
        last_reported_model: str | None = None

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            # No try/except: let exceptions propagate. The caller (EmbeddingService
            # or the GovernedEmbeddingAdapter) wraps them in fail-closed errors.
            response = await self._client.post(
                f"{self._base_url}/embeddings",
                json={
                    "model": self._model,
                    "input": batch,
                },
            )
            if response.status_code != 200:
                # Diagnostic: capture the exact 400 response body
                import hashlib as _diag_hash
                import json as _diag_json
                import os as _diag_os
                input_summaries = [
                    {"len": len(t), "sha256": _diag_hash.sha256(t.encode()).hexdigest()[:16], "first_80": t[:80]}
                    for t in batch
                ]
                diag = {
                    "url": f"{self._base_url}/embeddings",
                    "model": self._model,
                    "batch_index": i // self._batch_size,
                    "batch_size": len(batch),
                    "input_count": len(batch),
                    "input_summaries": input_summaries[:5],
                    "response_status": response.status_code,
                    "response_body": response.text[:1000],
                }
                _diag_path = _diag_os.path.join("evidence", "ingestion_400_diagnostic.json")
                _diag_os.makedirs("evidence", exist_ok=True)
                with open(_diag_path, "w", encoding="utf-8") as _df:
                    _diag_json.dump(diag, _df, indent=2, ensure_ascii=False)
                logger.error(
                    "LM Studio embedding 400: model=%s batch=%d inputs=%d status=%d body=%s "
                    "(diagnostic saved to %s)",
                    self._model, i // self._batch_size, len(batch),
                    response.status_code, response.text[:500], _diag_path,
                )
            response.raise_for_status()
            data = response.json()

            # Malformed output is an explicit failure, not a silent skip.
            if not isinstance(data, dict) or "data" not in data:
                raise LMStudioEmbeddingOutputError(
                    f"LM Studio /v1/embeddings returned malformed response: "
                    f"missing 'data' field (got {type(data).__name__})"
                )

            items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend(item["embedding"] for item in items)

            # P0.4B0.1e: capture the echoed 'model' field as evidence.
            # LM Studio's OpenAI-compatible endpoint populates data.model
            # with the actually-loaded model id. We retain it as
            # reported_model evidence; we do NOT promote the echo to a
            # stable identity here.
            reported = data.get("model")
            if isinstance(reported, str) and reported:
                last_reported_model = reported

        # Build the evidence record after all batches complete so it
        # reflects the most recent reported_model observed.
        self._last_identity_evidence = ProviderModelIdentityEvidence(
            provider_kind="lmstudio",
            requested_model=self._model,
            reported_model=last_reported_model,
            # The configured model id is the closest thing LM Studio
            # exposes to a deployment identity (the model is loaded at
            # a specific endpoint). B0.2 decides whether this rises to
            # stable_deployment or remains alias_only.
            deployment_id=self._model,
            provider_revision=None,
            evidence_source=EVIDENCE_SOURCE_LMSTUDIO_RESPONSE_MODEL
            if last_reported_model is not None
            else EVIDENCE_SOURCE_CONFIGURED_ONLY,
        )

        return all_embeddings

    async def embed_with_evidence(
        self, texts: list[str]
    ) -> ProviderEmbeddingBatch:
        """Embed and return vectors together with the captured identity evidence."""
        embeddings = await self.embed(texts)
        assert self._last_identity_evidence is not None
        return ProviderEmbeddingBatch(
            embeddings=tuple(tuple(v) for v in embeddings),
            identity_evidence=self._last_identity_evidence,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return f"lmstudio:{self._model}"

    @property
    def last_identity_evidence(self) -> ProviderModelIdentityEvidence | None:
        """Most recently captured identity evidence, or None if no embed call yet."""
        return self._last_identity_evidence


class FallbackEmbeddingProvider(EmbeddingProvider):
    """Provider that tries primary, then falls back to secondary on failure."""

    def __init__(self, primary: EmbeddingProvider, fallback: EmbeddingProvider):
        self._primary = primary
        self._fallback = fallback

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            return await self._primary.embed(texts)
        except Exception as e:
            logger.warning(
                "Primary embedding provider %s failed: %s, using fallback",
                self._primary.provider_name,
                e,
            )
            return await self._fallback.embed(texts)

    @property
    def dimension(self) -> int:
        return self._primary.dimension

    @property
    def provider_name(self) -> str:
        return f"fallback({self._primary.provider_name}+{self._fallback.provider_name})"


class DummyEmbeddingProvider(EmbeddingProvider):
    """No-op embedding provider for testing / environments without API access.

    Returns deterministic zero vectors of the configured dimension.
    Useful when the LLM provider (e.g. z.ai) does not offer an embedding endpoint.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dimension for _ in texts]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return f"dummy:{self._dimension}d"


class CachedEmbeddingProvider(EmbeddingProvider):
    """Caching wrapper — stores text_hash → embedding in memory.

    Avoids re-embedding identical text across pipeline stages.
    """

    def __init__(self, wrapped: EmbeddingProvider, max_size: int = 10000):
        self._wrapped = wrapped
        self._cache: dict[str, list[float]] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            key = hashlib.sha256(text.encode()).hexdigest()
            if key in self._cache:
                results[i] = self._cache[key]
                self._hits += 1
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
                self._misses += 1

        if uncached_texts:
            embeddings = await self._wrapped.embed(uncached_texts)
            for idx, emb in zip(uncached_indices, embeddings):
                results[idx] = emb
                key = hashlib.sha256(texts[idx].encode()).hexdigest()
                if len(self._cache) < self._max_size:
                    self._cache[key] = emb

        total = self._hits + self._misses
        if total > 0 and total % 100 == 0:
            logger.info(
                "Embedding cache: %d hits / %d total (%.1f%%)",
                self._hits, total, 100 * self._hits / total,
            )

        return results  # type: ignore[return-value]

    @property
    def dimension(self) -> int:
        return self._wrapped.dimension

    @property
    def provider_name(self) -> str:
        return f"cached({self._wrapped.provider_name})"


def create_embedding_provider(
    provider_name: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    dimension: int | None = None,
) -> EmbeddingProvider:
    """Factory: create an EmbeddingProvider by name.

    Args:
        provider_name: "openai", "gemini", "ollama"
        model: Model name (provider-specific default if omitted)
        api_key: API key for cloud providers
        base_url: Base URL for Ollama
        dimension: Override embedding dimension
    """
    name = provider_name.lower().strip()

    if name in ("dummy", "noop", "test"):
        return DummyEmbeddingProvider(dimension=dimension or 1536)
    elif name == "openai":
        provider = OpenAIEmbeddingProvider(
            model=model or "text-embedding-3-small",
            api_key=api_key,
            dimension_override=dimension,
        )
    elif name in ("gemini", "google"):
        provider = GeminiEmbeddingProvider(
            model=model or "models/embedding-001",
            api_key=api_key,
        )
    elif name == "ollama":
        return OllamaEmbeddingProvider(
            model=model or "nomic-embed-text",
            base_url=base_url,
        )
    elif name == "lmstudio":
        provider = LMStudioEmbeddingProvider(
            model=model or "text-embedding-bge-m3",
            base_url=base_url or _get_default_lmstudio_url(),
            dimension_override=dimension,
        )
        return CachedEmbeddingProvider(provider)
    elif name in ("openai-compatible", "lm-studio"):
        # Aliases for lmstudio
        return create_embedding_provider(
            provider_name="lmstudio",
            model=model,
            base_url=base_url,
            dimension=dimension,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider_name}")

    # Wrap cloud providers with cache (local Ollama doesn't benefit)
    return CachedEmbeddingProvider(provider)
