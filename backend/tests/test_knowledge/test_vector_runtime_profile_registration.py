"""Commissioning remediation: governed vector runtime must be constructible.

``build_governed_vector_runtime_from_settings`` returned None whenever the
EmbeddingProfile row was missing — and no deployment path registered one,
so governed novelty retrieval failed on every run ("could not construct
from settings") and the stage was absorbed. The builder now auto-registers
the settings-derived profile via the same replay-safe registration the
governed indexer uses.
"""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.db.database as db_database
from backend.config import get_settings
from backend.db.models import Base, EmbeddingProfile
from backend.pipeline.knowledge.embedding_configuration import (
    EmbeddingConfigurationError,
)


@pytest.fixture
def session_factory(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    import contextlib

    @contextlib.contextmanager
    def _fake_get_session():
        yield factory()

    monkeypatch.setattr(db_database, "get_session", _fake_get_session)
    return factory


@pytest.fixture
def lmstudio_settings(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "embedding_provider", "lmstudio", raising=False)
    monkeypatch.setattr(
        s, "embedding_model", "text-embedding-qwen3-embedding-0.6b", raising=False
    )
    monkeypatch.setattr(s, "embedding_dimension", 1024, raising=False)
    monkeypatch.setattr(s, "embedding_base_url", "", raising=False)
    monkeypatch.setattr(
        s, "lmstudio_base_url", "http://100.64.0.2:1234", raising=False
    )
    return s


def _stop_after_registration(monkeypatch):
    """Cut the builder right after profile resolution/registration."""
    from backend.pipeline.knowledge import embedding_configuration

    def _raise(**kwargs):
        raise EmbeddingConfigurationError("test stop: registration reached")

    monkeypatch.setattr(
        embedding_configuration, "resolve_effective_embedding_configuration", _raise
    )


def test_missing_profile_is_auto_registered(session_factory, lmstudio_settings, monkeypatch):
    _stop_after_registration(monkeypatch)
    from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

    with session_factory() as session:
        before = session.query(EmbeddingProfile).count()
    assert before == 0

    # Returns None at the injected stop point, but ONLY after registering.
    build_governed_vector_runtime_from_settings(db_engine=None)

    with session_factory() as session:
        rows = session.query(EmbeddingProfile).all()
    assert len(rows) == 1
    assert rows[0].provider == "lmstudio"
    assert rows[0].model_identifier == "text-embedding-qwen3-embedding-0.6b"
    assert rows[0].dimension == 1024
    assert rows[0].verification_status == "unverified"


def test_registration_is_replay_safe(session_factory, lmstudio_settings, monkeypatch):
    _stop_after_registration(monkeypatch)
    from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

    build_governed_vector_runtime_from_settings(db_engine=None)
    build_governed_vector_runtime_from_settings(db_engine=None)

    with session_factory() as session:
        assert session.query(EmbeddingProfile).count() == 1


def test_existing_profile_is_reused_not_duplicated(session_factory, lmstudio_settings, monkeypatch):
    _stop_after_registration(monkeypatch)
    from backend.pipeline.vector_access_policy import resolve_profile_id
    from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

    profile_id = resolve_profile_id(
        embedding_provider="lmstudio",
        model_identifier="text-embedding-qwen3-embedding-0.6b",
        dimension=1024,
        normalization_policy="none",
        chunking_schema_version="chunk_v1",
    )
    with session_factory() as session:
        session.add(
            EmbeddingProfile(
                profile_id=profile_id,
                profile_schema_version="embedding_profile_v1",
                provider="lmstudio",
                model_identifier="text-embedding-qwen3-embedding-0.6b",
                dimension=1024,
                normalization_policy="none",
                chunking_schema_version="chunk_v1",
                collection_name="existing",
                verification_status="unverified",
            )
        )
        session.commit()

    build_governed_vector_runtime_from_settings(db_engine=None)

    with session_factory() as session:
        rows = session.execute(select(EmbeddingProfile)).scalars().all()
    assert len(rows) == 1
    assert rows[0].collection_name == "existing"
