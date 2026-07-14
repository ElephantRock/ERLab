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

logger = logging.getLogger(__name__)


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
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return f"openai:{self._model}"


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embeddings via the generativeai SDK."""

    def __init__(
        self,
        model: str = "models/embedding-001",
        api_key: str | None = None,
    ):
        import google.generativeai as genai

        if api_key:
            genai.configure(api_key=api_key)
        self._model = model
        self._genai = genai

    async def embed(self, texts: list[str]) -> list[list[float]]:
        result = await asyncio.to_thread(
            self._genai.embed_content,
            model=self._model,
            content=texts,
            task_type="retrieval_document",
        )
        return result["embedding"]

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

    async def embed(self, texts: list[str]) -> list[list[float]]:
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
        return embeddings

    @property
    def dimension(self) -> int:
        return self._dim or 768

    @property
    def provider_name(self) -> str:
        return f"ollama:{self._model}"


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
        if model == "text-embedding-bge-m3":
            model = "text-embedding-bge-m3-embeddings"
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._batch_size = batch_size
        self._client = httpx.AsyncClient(timeout=120.0)
        self._dimension = dimension_override or self.MODEL_DIMENSIONS.get(model, 1024)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using LM Studio's /v1/embeddings endpoint."""
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            try:
                response = await self._client.post(
                    f"{self._base_url}/embeddings",
                    json={
                        "model": self._model,
                        "input": batch,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Sort by index to maintain order
                items = sorted(data["data"], key=lambda x: x["index"])
                all_embeddings.extend(item["embedding"] for item in items)

            except Exception as e:
                logger.error(
                    "LM Studio embedding batch %d failed: %s",
                    i // self._batch_size,
                    str(e)[:100],
                )
                # Return zero vectors on failure
                all_embeddings.extend(
                    [[0.0] * self._dimension for _ in batch]
                )

        return all_embeddings

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return f"lmstudio:{self._model}"


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
