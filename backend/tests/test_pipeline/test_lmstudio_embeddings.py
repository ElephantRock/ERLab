"""Tests for LM Studio embedding provider."""

import asyncio
import pytest

from backend.pipeline.knowledge.embedding_providers import (
    LMStudioEmbeddingProvider,
    create_embedding_provider,
)


# ── Unit Tests (no network) ───────────────────────────────────────────

def test_lmstudio_provider_model_dimensions():
    """LMStudioEmbeddingProvider knows dimensions for known models."""
    assert LMStudioEmbeddingProvider.MODEL_DIMENSIONS["text-embedding-bge-m3"] == 1024
    assert LMStudioEmbeddingProvider.MODEL_DIMENSIONS["text-embedding-nomic-embed-text-v2-moe"] == 768
    assert LMStudioEmbeddingProvider.MODEL_DIMENSIONS["sfr-embedding-mistral"] == 1024
    assert LMStudioEmbeddingProvider.MODEL_DIMENSIONS["nomic-embed-code"] == 1024


def test_lmstudio_provider_default_dimension():
    """LMStudioEmbeddingProvider defaults to bge-m3 (1024d)."""
    provider = LMStudioEmbeddingProvider()
    assert provider.dimension == 1024
    assert "lmstudio" in provider.provider_name


def test_lmstudio_provider_custom_dimension():
    """LMStudioEmbeddingProvider accepts dimension override."""
    provider = LMStudioEmbeddingProvider(dimension_override=512)
    assert provider.dimension == 512


def test_lmstudio_provider_nomic_v2():
    """LMStudioEmbeddingProvider resolves nomic v2 dimension."""
    provider = LMStudioEmbeddingProvider(model="text-embedding-nomic-embed-text-v2-moe")
    assert provider.dimension == 768


def test_create_provider_lmstudio():
    """create_embedding_provider('lmstudio') returns cached LMStudio provider."""
    provider = create_embedding_provider("lmstudio")
    assert "lmstudio" in provider.provider_name


def test_create_provider_lmstudio_custom_model():
    """create_embedding_provider with custom model."""
    provider = create_embedding_provider("lmstudio", model="sfr-embedding-mistral")
    assert "sfr-embedding-mistral" in provider.provider_name


# ── Live Tests (require LM Studio at 100.64.0.1:1234) ────────────────

@pytest.mark.skipif(
    True,  # Disabled by default — set False to test against live LM Studio
    reason="Requires LM Studio running at 100.64.0.1:1234"
)
def test_lmstudio_live_bge_m3():
    """Live test: embed text via bge-m3."""
    provider = LMStudioEmbeddingProvider(model="text-embedding-bge-m3")
    embeddings = asyncio.run(provider.embed(["Hello world", "Test embedding"]))
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 1024
    assert len(embeddings[1]) == 1024


@pytest.mark.skipif(
    True,
    reason="Requires LM Studio running at 100.64.0.1:1234"
)
def test_lmstudio_live_nomic_v2():
    """Live test: embed text via nomic-embed-text-v2-moe."""
    provider = LMStudioEmbeddingProvider(model="text-embedding-nomic-embed-text-v2-moe")
    embeddings = asyncio.run(provider.embed(["Research paper about transformers"]))
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 768


@pytest.mark.skipif(
    True,
    reason="Requires LM Studio running at 100.64.0.1:1234"
)
def test_lmstudio_live_sfr_mistral():
    """Live test: embed text via SFR-Embedding-Mistral."""
    provider = LMStudioEmbeddingProvider(model="sfr-embedding-mistral")
    embeddings = asyncio.run(provider.embed(["What is attention?"]))
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 1024


@pytest.mark.skipif(
    True,
    reason="Requires LM Studio running at 100.64.0.1:1234"
)
def test_lmstudio_live_batch():
    """Live test: batch embedding."""
    provider = LMStudioEmbeddingProvider(model="text-embedding-bge-m3", batch_size=3)
    texts = [f"Document number {i}" for i in range(7)]
    embeddings = asyncio.run(provider.embed(texts))
    assert len(embeddings) == 7
    assert all(len(e) == 1024 for e in embeddings)
