"""Governed vector runtime bundle (P0.3.4H).

Central composition root for governed vector services. Constructed once
at application startup and injected into stages, novelty checker, and API
routes. No production module outside this file and ``vector_backend.py``
should import or construct ``chromadb`` directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GovernedVectorRuntime:
    """Complete governed vector service bundle.

    Constructed once at application startup and injected into all
    governed vector consumers. Contains every dependency a governed
    vector operation needs — no consumer may construct partial services.
    """

    backend: Any  # GovernedVectorBackend
    embedding_provider: Any  # EmbeddingProvider (embed_single interface)
    embedding_profile_id: str
    profile_dict: dict[str, Any]
    session_factory: Any  # sessionmaker
    db_engine: Any  # SQLAlchemy engine


def build_governed_vector_runtime(
    *,
    chroma_persist_dir: str,
    embedding_provider: Any,
    embedding_dimension: int,
    embedding_provider_name: str,
    embedding_model_identifier: str,
    db_engine: Any,
    normalization_policy: str = "l2",
    chunking_schema_version: str = "title_abstract_v1",
) -> GovernedVectorRuntime:
    """Construct the governed vector runtime at application startup.

    This is the ONLY production location that imports chromadb and
    constructs a GovernedVectorBackend. All consumers receive the
    injected runtime.
    """
    import chromadb
    from sqlalchemy.orm import sessionmaker

    from backend.pipeline.vector_backend import GovernedVectorBackend
    from backend.pipeline.vector_access_policy import resolve_profile_id
    from backend.pipeline.vector_contracts import compute_collection_name

    profile_id = resolve_profile_id(
        embedding_provider=embedding_provider_name,
        model_identifier=embedding_model_identifier,
        dimension=embedding_dimension,
        normalization_policy=normalization_policy,
        chunking_schema_version=chunking_schema_version,
    )

    chroma_client = chromadb.PersistentClient(path=chroma_persist_dir)
    backend = GovernedVectorBackend(chroma_client)

    session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    return GovernedVectorRuntime(
        backend=backend,
        embedding_provider=embedding_provider,
        embedding_profile_id=profile_id,
        profile_dict={
            "provider": embedding_provider_name,
            "model_identifier": embedding_model_identifier,
            "dimension": embedding_dimension,
            "normalization_policy": normalization_policy,
            "chunking_schema_version": chunking_schema_version,
        },
        session_factory=session_factory,
        db_engine=db_engine,
    )


def build_governed_vector_runtime_from_settings(db_engine: Any) -> GovernedVectorRuntime | None:
    """Construct from application settings, or None if dependencies unavailable."""
    try:
        from backend.config import get_settings
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.providers.provider_factory import create_provider

        settings = get_settings()
        provider = create_provider()
        embedding = EmbeddingService(provider)

        # P0.4B0.3: use the canonical GovernedEmbeddingAdapter instead of
        # an inline private _EmbeddingAdapter. The canonical adapter exposes
        # provider/model/dimension identity and performs fail-closed
        # structural validation; the inline adapter did neither.
        from backend.pipeline.governed_embedding_adapter import (
            GovernedEmbeddingAdapter,
        )
        adapter = GovernedEmbeddingAdapter(
            embedding_service=embedding,
            provider_kind=settings.embedding_provider,
            requested_model=settings.embedding_model,
            configured_dimension=embedding.dimension,
        )

        return build_governed_vector_runtime(
            chroma_persist_dir=settings.chroma_persist_dir,
            embedding_provider=adapter,
            embedding_dimension=embedding.dimension,
            embedding_provider_name=settings.embedding_provider,
            embedding_model_identifier=settings.embedding_model,
            db_engine=db_engine,
        )
    except Exception as e:
        logger.debug("Could not build governed vector runtime: %s", e)
        return None
