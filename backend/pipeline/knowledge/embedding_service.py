"""Embedding generation service.

Wraps an EmbeddingProvider with batching and error handling.

Fail-closed behavior (Phase 5):
- Provider failures raise EmbeddingProviderError, not zero-vector fallback.
- Zero vectors returned by the provider raise EmbeddingProviderError.
- The only path to a zero vector is the explicit empty-input case.

Accepts only the dedicated ``EmbeddingProvider`` — never an ``LLMProvider``.
Chat providers cannot produce embeddings directly or indirectly.
"""

from __future__ import annotations

import logging

from backend.pipeline.knowledge.embedding_providers import EmbeddingProvider

logger = logging.getLogger(__name__)


class EmbeddingProviderError(Exception):
    """Typed error for embedding provider failures.

    Raised when:
    - The embedding provider raises an exception
    - The provider returns zero vectors (offline or misconfigured)
    """


def _is_zero_vector(vec: list[float]) -> bool:
    """Check if an embedding vector is all zeros."""
    if not vec:
        return True
    return all(v == 0.0 for v in vec)


class EmbeddingService:
    """Generate embeddings using a pluggable provider."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        batch_size: int = 100,
        expected_dimension: int | None = None,
    ):
        self._provider = provider
        self._batch_size = batch_size
        if expected_dimension is not None:
            self.validate_dimension(expected_dimension)

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, batching for efficiency.

        Fail-closed behavior (Phase 5):
        - Provider failures raise EmbeddingProviderError.
        - Zero vectors from the provider raise EmbeddingProviderError.
        - No silent fallback to zero vectors.
        """
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            try:
                embeddings = await self._provider.embed(batch)
            except Exception as e:
                raise EmbeddingProviderError(
                    f"Embedding provider failed on batch {i // self._batch_size}: {e}"
                ) from e

            # Check for zero vectors — provider is offline or misconfigured
            zero_count = sum(1 for e in embeddings if _is_zero_vector(e))
            if zero_count > 0:
                raise EmbeddingProviderError(
                    f"Embedding provider returned {zero_count}/{len(batch)} zero vectors "
                    f"in batch {i // self._batch_size}. Provider may be offline or misconfigured."
                )
            all_embeddings.extend(embeddings)

        return all_embeddings

    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Raises EmbeddingProviderError if the provider fails.
        """
        results = await self.embed_texts([text])
        return results[0]

    async def embed_with_evidence(self, texts: list[str]):
        """Generate embeddings with identity evidence.

        Delegates to the provider's ``embed_with_evidence`` method,
        applying the same fail-closed error handling and zero-vector
        rejection as ``embed_texts``.

        Returns a ``ProviderEmbeddingBatch`` (vectors + identity evidence).
        """
        if not texts:
            from backend.pipeline.knowledge.embedding_provider_identity import (
                ProviderEmbeddingBatch,
            )
            return ProviderEmbeddingBatch(
                embeddings=(),
                identity_evidence=None,  # type: ignore[arg-type]
            )

        try:
            batch = await self._provider.embed_with_evidence(texts)  # type: ignore[attr-defined]
        except AttributeError:
            # Provider doesn't implement embed_with_evidence — fall back
            # to the ABC's default implementation
            batch = await self._provider.embed_with_evidence(texts)
        except EmbeddingProviderError:
            raise
        except Exception as e:
            raise EmbeddingProviderError(
                f"Embedding provider failed during evidence embed: {e}"
            ) from e

        # Check for zero vectors (same fail-closed rule as embed_texts)
        zero_count = sum(1 for e in batch.embeddings if not e or all(v == 0.0 for v in e))
        if zero_count > 0:
            raise EmbeddingProviderError(
                f"Embedding provider returned {zero_count}/{len(batch.embeddings)} "
                f"zero vectors. Provider may be offline or misconfigured."
            )

        return batch

    @property
    def dimension(self) -> int:
        """Return embedding dimension from provider, or default 1536."""
        if hasattr(self._provider, "dimension"):
            return self._provider.dimension
        return 1536

    async def validate_startup(self) -> bool:
        """Test-embed a string to confirm the provider returns non-zero vectors.

        Returns True if the embedding is real.
        Returns False if the provider fails or returns zero vectors.
        Call this once after constructing EmbeddingService. If it returns
        False, novelty checking will produce garbage and should be skipped.
        """
        try:
            test = await self.embed_single("test")
        except EmbeddingProviderError as e:
            logger.error(
                "Embedding provider failed during startup validation: %s. "
                "Novelty checking will produce meaningless scores.",
                e,
            )
            return False
        if not test:
            logger.error("Embedding provider returned empty vector — novelty will be fake")
            return False
        if all(v == 0.0 for v in test):
            logger.error(
                "Embedding provider returned all-zero vector (%d-dim). "
                "Novelty checking will produce meaningless scores. "
                "Switch to a real embedding provider (openai, gemini, ollama) "
                "or accept that novelty scores are unreliable.",
                len(test),
            )
            return False
        logger.info("Embedding provider validated: %d-dim, non-zero vectors", len(test))
        return True

    def validate_dimension(self, expected: int) -> bool:
        """Warn if embedding dimension doesn't match expected. Returns True if match."""
        actual = self.dimension
        if actual != expected:
            logger.warning(
                "Embedding dimension mismatch: provider=%d, expected=%d. "
                "Existing vectors may be incompatible.",
                actual, expected,
            )
            return False
        return True
