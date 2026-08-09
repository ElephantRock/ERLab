"""Governed vector runtime bundle (P0.4B0.6).

Central composition root for governed vector services. Constructed once
at application startup and injected into stages, novelty checker, and API
routes. No production module outside this file and ``vector_backend.py``
should import or construct ``chromadb`` directly.

B0.6 breaking change: the runtime now exposes only:
  - backend (GovernedVectorBackend)
  - session_factory (sessionmaker)
  - effective_embedding_config (EffectiveEmbeddingConfiguration)
  - embedding_adapter (GovernedEmbeddingAdapter)

Removed: embedding_provider, embedding_profile_id, profile_dict, db_engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GovernedVectorRuntime:
    """B0.6 governed vector service bundle.

    Exactly four public fields. No raw provider, no untyped profile dict,
    no duplicate profile ID, no dead engine field.
    """
    backend: Any  # GovernedVectorBackend
    session_factory: Any  # sessionmaker
    effective_embedding_config: Any  # EffectiveEmbeddingConfiguration
    embedding_adapter: Any  # GovernedEmbeddingAdapter


class GovernedVectorRuntimeError(Exception):
    """Bounded composition error with sanitized detail."""
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail[:500]
        super().__init__(f"[{code}] {self.detail}")


def build_governed_vector_runtime_from_settings(db_engine: Any) -> GovernedVectorRuntime | None:
    """Construct from application settings, or None if dependencies unavailable.

    Sequence (load-bearing ordering):
      1. Snapshot runtime embedding settings
      2. Load EmbeddingProfileSnapshot from DB
      3. Obtain adapter capability snapshot
      4. Resolve EffectiveEmbeddingConfiguration (B0.7 reconciliation)
      5. Construct embedding provider
      6. Wrap provider in GovernedEmbeddingAdapter
      7. Construct GovernedVectorBackend
      8. Return GovernedVectorRuntime

    Steps 1-4 must complete before step 5 (provider construction).
    """
    try:
        from backend.config import get_settings
        from backend.db.database import get_session
        from backend.db.models import EmbeddingProfile
        from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
        from backend.pipeline.knowledge.embedding_configuration import (
            EmbeddingAdapterCapabilitySnapshot,
            EmbeddingProfileSnapshot,
            EmbeddingRuntimeSettingsSnapshot,
            resolve_effective_embedding_configuration,
            EmbeddingConfigurationError,
        )
        from backend.pipeline.vector_access_policy import resolve_profile_id
        from backend.pipeline.vector_contracts import compute_collection_name
        from backend.pipeline.vector_backend import GovernedVectorBackend
        from backend.pipeline.knowledge.embedding_service import EmbeddingService
        from backend.providers.provider_factory import create_provider
        from sqlalchemy import select
        from sqlalchemy.orm import sessionmaker

        app_settings = get_settings()

        # Use the configured embedding dimension directly rather than probing
        # a possibly-unreachable provider. When the embedding endpoint is down
        # (the acceptance run's ingestion failure), create_provider() returns
        # the LLM provider which cannot produce embeddings; its dimension probe
        # fails and defaults to 1536, causing a profile_id mismatch against
        # the registered profile's actual dimension.
        configured_dimension = (
            app_settings.embedding_dimension
            if app_settings.embedding_dimension
            else 1536  # safe default only when unset
        )

        # ── Step 1: Snapshot runtime settings (no credentials) ──
        settings_snapshot = EmbeddingRuntimeSettingsSnapshot(
            provider_kind=app_settings.embedding_provider,
            requested_model=app_settings.embedding_model,
            expected_dimension=configured_dimension,
            declared_normalization_policy="none",
            document_task=None,
            query_task=None,
            endpoint=getattr(app_settings, "embedding_base_url", None),
            configured_deployment_id=None,
            deployment_is_explicitly_pinned=False,
        )

        # ── Step 2: Load EmbeddingProfileSnapshot from DB ──
        profile_id = resolve_profile_id(
            embedding_provider=app_settings.embedding_provider,
            model_identifier=app_settings.embedding_model,
            dimension=configured_dimension,
            normalization_policy="none",
            chunking_schema_version="chunk_v1",
        )

        with get_session() as session:
            profile_row = session.execute(
                select(EmbeddingProfile).where(
                    EmbeddingProfile.profile_id == profile_id
                )
            ).scalar_one_or_none()

        if profile_row is None:
            logger.debug("Embedding profile %s... not registered", profile_id[:12])
            return None

        profile_snapshot = EmbeddingProfileSnapshot(
            embedding_profile_id=profile_row.profile_id,
            profile_schema_version=profile_row.profile_schema_version,
            provider_kind=profile_row.provider,
            model_identifier=profile_row.model_identifier,
            dimension=profile_row.dimension,
            normalization_policy=profile_row.normalization_policy,
            document_task=None,
            query_task=None,
            verification_status=profile_row.verification_status,
        )

        # ── Step 3: Adapter capability snapshot ──
        adapter_snapshot = EmbeddingAdapterCapabilitySnapshot(
            provider_adapter_contract_version="provider_adapter_v1",
            governed_adapter_contract_version="governed_adapter_v1",
            implemented_postprocessing_policy="none",
            supports_document_embedding=True,
            supports_query_embedding=True,
        )

        # ── Step 4: Resolve effective configuration (may fail) ──
        try:
            effective_config = resolve_effective_embedding_configuration(
                settings=settings_snapshot,
                profile=profile_snapshot,
                adapter=adapter_snapshot,
            )
        except EmbeddingConfigurationError as e:
            logger.warning("Embedding configuration reconciliation failed: %s", e)
            return None

        # ── Step 5: Construct embedding provider (after reconciliation) ──
        # Use the EMBEDDING provider, not the LLM provider. create_provider()
        # returns the LLM provider (glm-5.2 via ResilientProvider) which has
        # complete() but not embed(). The governed adapter needs embed().
        from backend.pipeline.knowledge.embedding_providers import (
            create_embedding_provider,
        )
        _emb_base = app_settings.embedding_base_url
        if _emb_base:
            _emb_base = _emb_base.rstrip('/')
            if not _emb_base.endswith('/v1'):
                _emb_base += '/v1'
        elif app_settings.embedding_provider == "lmstudio":
            _emb_base = app_settings.lmstudio_base_url.rstrip('/') + '/v1'
        else:
            _emb_base = app_settings.ollama_base_url

        embedding_provider = create_embedding_provider(
            provider_name=app_settings.embedding_provider,
            model=app_settings.embedding_model,
            api_key=app_settings.openai_api_key,
            base_url=_emb_base,
            dimension=app_settings.embedding_dimension or None,
        )
        embedding_service = EmbeddingService(embedding_provider)

        # ── Step 6: Wrap in GovernedEmbeddingAdapter ──
        adapter = GovernedEmbeddingAdapter(
            embedding_service=embedding_service,
            provider_kind=effective_config.provider_kind,
            requested_model=effective_config.requested_model,
            configured_dimension=effective_config.expected_dimension,
        )

        # ── Step 7: Construct GovernedVectorBackend ──
        import chromadb
        chroma_client = chromadb.PersistentClient(path=app_settings.chroma_persist_dir)
        backend = GovernedVectorBackend(chroma_client)

        session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)

        # ── Step 8: Return runtime ──
        return GovernedVectorRuntime(
            backend=backend,
            session_factory=session_factory,
            effective_embedding_config=effective_config,
            embedding_adapter=adapter,
        )

    except Exception as e:
        logger.debug("Could not build governed vector runtime: %s", e)
        return None
