"""Tests for P0.3.1: vector scope contracts and central scope resolver.

Proves:
  - Domain scope key derivation (NFKC/casefold/whitespace normalization)
  - Embedding profile identity (deterministic SHA-256)
  - Scope fingerprint determinism
  - Resolver: current_run_only cross-run isolation
  - Resolver: same_domain_prior_runs domain filtering
  - Resolver: global_library explicit membership
  - Resolver: selected_papers validation
  - Resolver: legacy run rejection
  - Resolver: empty scope (zero papers = valid, not error)
  - Migration 021 preserves legacy + round-trip
"""

from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.db.database import Base
from backend.db.models import (
    GlobalLibraryMembership,
    Paper,
    PipelineRun,
    RunPaper,
    RunSearchReconciliation,
)
from backend.pipeline.vector_contracts import (
    EmbeddingProfileRef,
    VectorRetrievalScope,
    compute_scope_fingerprint,
    derive_domain_scope_key,
)
from backend.pipeline.vector_scope import (
    VectorScopeResolutionError,
    resolve_vector_scope,
)


def _make_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def _fk(c, r):
        cur = c.cursor(); cur.execute("PRAGMA foreign_keys=ON"); cur.close()
    Base.metadata.create_all(engine)
    return engine


_run_counter = [0]


def _make_governed_run(engine, domain="AI/NLP", domain_key=None, reconciled=False):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        if domain_key is None:
            domain_key = derive_domain_scope_key(domain)
        run = PipelineRun(
            run_id_str=f"r_p031_{_run_counter[0]}",
            domain=domain, status="completed",
            config_json="{}", stages_completed="[]",
            provenance_version="provenance_v1",
            domain_scope_key=domain_key,
            domain_scope_version="domain_scope_v1",
        )
        s.add(run); s.flush()

        if reconciled:
            # Provide all required aggregate counts for the reconciled CHECK
            now = datetime.now(UTC)
            rsr = RunSearchReconciliation(
                run_id=run.id,
                reconciliation_schema_version="run_reconciliation_v1",
                status="reconciled",
                execution_posture="healthy",
                reconciliation_attempt_count=1,
                input_fingerprint="test_fp",
                completed_at=now,
                logical_query_count=1,
                expected_execution_count=1,
                actual_execution_count=1,
                terminal_execution_count=1,
                success_execution_count=1,
                partial_execution_count=0,
                failed_execution_count=0,
                timeout_execution_count=0,
                skipped_execution_count=0,
                reconciled_accounting_execution_count=1,
                incomplete_accounting_execution_count=0,
                source_unique_result_count=0,
                linked_discovery_count=0,
                remote_canonical_paper_count=0,
                nonremote_canonical_paper_count=0,
                remote_only_paper_count=0,
                nonremote_only_paper_count=0,
                multi_origin_paper_count=0,
                run_paper_count=0,
                canonicalization_reduction_count=0,
                unexplained_membership_count=0,
                unowned_discovery_paper_count=0,
            )
        else:
            rsr = RunSearchReconciliation(
                run_id=run.id,
                reconciliation_schema_version="run_reconciliation_v1",
                status="pending",
                reconciliation_attempt_count=0,
            )
        s.add(rsr); s.commit()
        return run.id
    finally:
        s.close()


def _make_paper(engine, source_id):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        p = Paper(source_id=source_id, source="arxiv", title=source_id,
                  authors="[]", keywords="[]", ingested=0)
        s.add(p); s.commit()
        return p.id
    finally:
        s.close()


def _add_run_paper(engine, run_id, paper_id):
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        rp = RunPaper(run_id=run_id, paper_id=paper_id, inclusion_origin="remote_search")
        s.add(rp); s.commit()
    finally:
        s.close()


# ── 1. Domain scope key ──────────────────────────────────────────────


def test_domain_key_normalization():
    k1 = derive_domain_scope_key("AI/NLP")
    k2 = derive_domain_scope_key("  ai/nlp  ")
    assert k1 == k2
    assert len(k1) == 64


def test_domain_key_different_domains_differ():
    k1 = derive_domain_scope_key("AI/NLP")
    k2 = derive_domain_scope_key("Computer Vision")
    assert k1 != k2


def test_domain_key_unicode_normalized():
    k1 = derive_domain_scope_key("café résumé")
    k2 = derive_domain_scope_key("cafe resume")  # NFKC + casefold
    assert k1 != k2  # NFKC doesn't strip accents; different strings


# ── 2. Embedding profile ─────────────────────────────────────────────


def test_profile_id_deterministic():
    p1 = EmbeddingProfileRef(
        provider="lmstudio", model_identifier="qwen3",
        dimension=1024, normalization_policy="l2",
        chunking_schema_version="chunk_v1",
    )
    p2 = EmbeddingProfileRef(
        provider="lmstudio", model_identifier="qwen3",
        dimension=1024, normalization_policy="l2",
        chunking_schema_version="chunk_v1",
    )
    assert p1.profile_id == p2.profile_id


def test_profile_id_differs_on_dimension():
    p1 = EmbeddingProfileRef(
        provider="x", model_identifier="m", dimension=1024,
        normalization_policy="l2", chunking_schema_version="v1",
    )
    p2 = EmbeddingProfileRef(
        provider="x", model_identifier="m", dimension=768,
        normalization_policy="l2", chunking_schema_version="v1",
    )
    assert p1.profile_id != p2.profile_id


# ── 3. Scope fingerprint ─────────────────────────────────────────────


def test_scope_fingerprint_deterministic():
    fp1 = compute_scope_fingerprint(1, "current_run_only", "profile_a", [1, 2, 3], [1, 2])
    fp2 = compute_scope_fingerprint(1, "current_run_only", "profile_a", [3, 2, 1], [2, 1])
    assert fp1 == fp2  # sorted internally


def test_scope_fingerprint_differs_on_mode():
    fp1 = compute_scope_fingerprint(1, "current_run_only", "p", [1], [1])
    fp2 = compute_scope_fingerprint(1, "global_library", "p", [1], [1])
    assert fp1 != fp2


# ── 4. Resolver: current_run_only cross-run isolation ────────────────


def test_current_run_only_isolation():
    """Run B can only see its own papers, not Run A's."""
    engine = _make_engine()
    run_a = _make_governed_run(engine)
    run_b = _make_governed_run(engine)

    p_a1 = _make_paper(engine, "a1")
    p_a2 = _make_paper(engine, "a2")
    p_b1 = _make_paper(engine, "b1")
    p_b2 = _make_paper(engine, "b2")

    _add_run_paper(engine, run_a, p_a1)
    _add_run_paper(engine, run_a, p_a2)
    _add_run_paper(engine, run_b, p_b1)
    _add_run_paper(engine, run_b, p_b2)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="current_run_only",
            run_id=run_b,
            embedding_profile_id="test_profile",
        )
        resolved = resolve_vector_scope(s, scope)
        assert resolved.allowed_paper_count == 2
        assert set(resolved.allowed_paper_ids) == {p_b1, p_b2}
        assert p_a1 not in resolved.allowed_paper_ids
        assert p_a2 not in resolved.allowed_paper_ids
    finally:
        s.close()


# ── 5. Resolver: empty scope ─────────────────────────────────────────


def test_empty_scope_is_valid():
    """A run with zero papers resolves to an empty (but valid) scope."""
    engine = _make_engine()
    run_id = _make_governed_run(engine)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="current_run_only",
            run_id=run_id,
            embedding_profile_id="test_profile",
        )
        resolved = resolve_vector_scope(s, scope)
        assert resolved.allowed_paper_count == 0
        assert resolved.allowed_paper_ids == ()
        assert resolved.scope_fingerprint is not None
    finally:
        s.close()


# ── 6. Resolver: selected_papers ─────────────────────────────────────


def test_selected_papers_validated():
    engine = _make_engine()
    run_id = _make_governed_run(engine)
    p1 = _make_paper(engine, "p1")
    p2 = _make_paper(engine, "p2")

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="selected_papers",
            run_id=run_id,
            embedding_profile_id="test_profile",
            selected_paper_ids=(p1, p2),
        )
        resolved = resolve_vector_scope(s, scope)
        assert resolved.allowed_paper_count == 2
    finally:
        s.close()


def test_selected_papers_unknown_rejected():
    engine = _make_engine()
    run_id = _make_governed_run(engine)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="selected_papers",
            run_id=run_id,
            embedding_profile_id="test_profile",
            selected_paper_ids=(99999,),  # doesn't exist
        )
        with pytest.raises(VectorScopeResolutionError, match="unknown paper"):
            resolve_vector_scope(s, scope)
    finally:
        s.close()


# ── 7. Resolver: global_library ──────────────────────────────────────


def test_global_library_explicit_only():
    engine = _make_engine()
    run_id = _make_governed_run(engine)
    p1 = _make_paper(engine, "g1")
    p2 = _make_paper(engine, "g2")
    p3 = _make_paper(engine, "non-member")

    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        # Only p1 is an active global member
        s.add(GlobalLibraryMembership(
            paper_id=p1, membership_schema_version="global_library_v1",
            status="active", membership_origin="user_curated",
        ))
        s.commit()
    finally:
        s.close()

    s2 = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="global_library",
            run_id=run_id,
            embedding_profile_id="test_profile",
        )
        resolved = resolve_vector_scope(s2, scope)
        assert resolved.allowed_paper_count == 1
        assert p1 in resolved.allowed_paper_ids
        assert p3 not in resolved.allowed_paper_ids
    finally:
        s2.close()


# ── 8. Resolver: legacy run rejection ────────────────────────────────


def test_legacy_run_rejected():
    engine = _make_engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        _run_counter[0] += 1
        run = PipelineRun(
            run_id_str=f"r_legacy_{_run_counter[0]}",
            domain="AI", status="completed",
            config_json="{}", stages_completed="[]",
            provenance_version="pre_provenance",
            legacy_provenance_reason="explicit_legacy_mode",
        )
        s.add(run); s.commit()
        run_id = run.id
    finally:
        s.close()

    s2 = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="current_run_only",
            run_id=run_id,
            embedding_profile_id="test_profile",
        )
        with pytest.raises(VectorScopeResolutionError, match="legacy run"):
            resolve_vector_scope(s2, scope)
    finally:
        s2.close()


# ── 9. Resolver: same_domain_prior_runs ──────────────────────────────


def test_same_domain_prior_runs():
    engine = _make_engine()
    domain = "Quantum Computing"
    dkey = derive_domain_scope_key(domain)

    # Run A: earlier, reconciled, same domain
    run_a = _make_governed_run(engine, domain=domain, domain_key=dkey, reconciled=True)
    p_a = _make_paper(engine, "qa1")
    _add_run_paper(engine, run_a, p_a)

    # Run B: current, same domain
    run_b = _make_governed_run(engine, domain=domain, domain_key=dkey)
    p_b = _make_paper(engine, "qb1")
    _add_run_paper(engine, run_b, p_b)

    # Run C: different domain
    run_c = _make_governed_run(engine, domain="Other Domain")
    p_c = _make_paper(engine, "oc1")
    _add_run_paper(engine, run_c, p_c)

    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        scope = VectorRetrievalScope(
            schema_version="vector_scope_v1",
            mode="same_domain_prior_runs",
            run_id=run_b,
            embedding_profile_id="test_profile",
        )
        resolved = resolve_vector_scope(s, scope)
        # Should include Run A's paper (same domain, prior, reconciled)
        # Should NOT include Run C's paper (different domain)
        assert p_a in resolved.allowed_paper_ids
        assert p_c not in resolved.allowed_paper_ids
    finally:
        s.close()


# ── 10. Migration tests ──────────────────────────────────────────────


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _alembic_cfg(db_url):
    from alembic.config import Config
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _patched_settings(db_url):
    mock = MagicMock()
    mock.database_url = db_url
    mock.debug = False
    return patch("backend.config.get_settings", return_value=mock)


def test_migration_021_preserves_legacy():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'p031.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "020")
        engine = create_engine(db_url)
        with engine.connect() as c:
            c.execute(text(
                "INSERT INTO pipeline_runs "
                "(run_id_str,domain,status,config_json,stages_completed,created_at,provenance_version,legacy_provenance_reason) "
                "VALUES ('r1','AI','completed','{}','[]',CURRENT_TIMESTAMP,'pre_provenance','pre_gating_run')"))
            c.commit()

        command.upgrade(cfg, "021")
        engine = create_engine(db_url)
        with engine.connect() as c:
            cols = [r[1] for r in c.execute(text("PRAGMA table_info(pipeline_runs)")).fetchall()]
            assert "domain_scope_key" in cols
            # Legacy run: domain_scope_key is NULL (not backfilled)
            row = c.execute(text("SELECT domain_scope_key FROM pipeline_runs WHERE id=1")).one()
            assert row[0] is None

            tables = [r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()]
            assert "global_library_memberships" in tables


def test_migration_021_round_trip():
    from alembic import command

    tmpdir = tempfile.mkdtemp()
    db_url = f"sqlite:///{Path(tmpdir) / 'rt.db'}"
    cfg = _alembic_cfg(db_url)

    with _patched_settings(db_url):
        command.upgrade(cfg, "020")
        command.upgrade(cfg, "021")
        command.downgrade(cfg, "020")
        command.upgrade(cfg, "021")
        insp = inspect(create_engine(db_url))
        assert insp.has_table("global_library_memberships")
