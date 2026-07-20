"""P1B.2d/g: Generate the governed real-provider embedding snapshot.

This script is the P1B.2 generation harness. It runs ONCE, after the operator
has loaded the configured embedding model (voyage-4-nano on LM Studio), to
produce the frozen snapshot that every P1B.3 policy comparison runs against.

Flow (all governed, fail-closed):

  1. preflight: confirm the provider endpoint is reachable and the model
     answers a trivial embedding request (fail loudly if not loaded)
  2. register the embedding profile (provider/model/dimension/normalization)
     into embedding_profiles if not already present
  3. run the governed dual_probe via run_capability_check — this creates a
     capability check row and, on pass, resolves a binding
  4. build VerifiedEmbeddingRuntime from the passed check (fail-closed:
     raises CapabilityAuthorizationError if the probe did not pass)
  5. embed every benchmark query + candidate canonical text through
     embed_query_authorized / embed_documents_authorized, capturing the
     binding evidence from the receipts
  6. write the immutable snapshot via write_snapshot(), recording the exact
     binding/check/runtime-fingerprint evidence on every vector

Canonical text convention: a query is embedded as its query_text verbatim;
a candidate is embedded as "{title}\n\n{abstract}" — the same canonical form
the benchmark's content_hash covers, so the snapshot's text_hash matches the
benchmark's content_hash exactly.

Run:  python -m backend.ranking.generate_embedding_snapshot
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure repo root is importable when run as a script.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.ranking.benchmark_v2_registry import (
    ALL_V2_CASES,
    BENCHMARK_V2,
    compute_benchmark_v2_fingerprint,
    frozen_v2_cases,
)
from backend.ranking.embedding_snapshot import (
    SNAPSHOT_SCHEMA_VERSION,
    SnapshotBindingEvidence,
    SnapshotItem,
    canonical_text_hash,
    vector_fingerprint,
    write_snapshot,
)


SNAPSHOT_DIR = _REPO_ROOT / "docs" / "p1b_snapshot"


def _candidate_canonical_text(case, cand) -> str:
    """Canonical candidate text — matches the benchmark content_hash scheme."""
    return f"{cand.title}\n\n{cand.abstract}"


def _query_canonical_text(case) -> str:
    return case.query_text


def preflight_provider():
    """Confirm the configured provider endpoint answers an embedding request.

    Fails loudly with a clear message if the model is not loaded.
    """
    import httpx
    from backend.config import get_settings

    s = get_settings()
    base = s.embedding_base_url or s.lmstudio_base_url
    print(f"[preflight] provider={s.embedding_provider} model={s.embedding_model}")
    print(f"[preflight] endpoint={base}")
    try:
        with httpx.Client(timeout=20) as c:
            r = c.get(f"{base}/v1/models")
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
            if s.embedding_model not in ids:
                raise RuntimeError(
                    f"model {s.embedding_model!r} not in served models {ids}"
                )
            # Trivial embedding probe to confirm the model is LOADED (not just
            # registered — LM Studio lists models that aren't loaded yet).
            er = c.post(
                f"{base}/v1/embeddings",
                json={"model": s.embedding_model, "input": "preflight"},
                timeout=60,
            )
            if er.status_code != 200:
                raise RuntimeError(
                    f"embedding probe failed: HTTP {er.status_code} {er.text[:200]}. "
                    f"The model is likely listed but NOT LOADED. Run "
                    f"'lms load {s.embedding_model}' on the provider host."
                )
            dim = len(er.json()["data"][0]["embedding"])
            print(f"[preflight] model loaded; responded with dimension {dim}")
            return dim
    except Exception as e:
        raise RuntimeError(f"[preflight] provider not usable: {e}") from e


def register_profile_and_run_probe():
    """Register the embedding profile and run the governed dual_probe.

    Returns (governed_adapter, effective_config, session_factory, publication).
    """
    from sqlalchemy.orm import sessionmaker
    from backend.config import get_settings
    from backend.db.database import _get_engine
    from backend.db import models  # noqa: F401  (ensure models imported)
    from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.knowledge.embedding_configuration import (
        EmbeddingAdapterCapabilitySnapshot,
        EmbeddingProfileSnapshot,
        EmbeddingRuntimeSettingsSnapshot,
        resolve_effective_embedding_configuration,
    )
    from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter
    from backend.pipeline.vector_indexer import register_embedding_profile
    from backend.pipeline.capability.capability_check_service import run_capability_check

    settings = get_settings()
    engine = _get_engine()
    sf = sessionmaker(bind=engine, expire_on_commit=False)

    # Determine dimension from the provider
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.embedding_base_url or settings.lmstudio_base_url,
        dimension=settings.embedding_dimension or None,
    )
    emb_service = EmbeddingService(provider)
    dimension = emb_service.dimension
    print(f"[probe] resolved dimension from provider: {dimension}")

    # Register the profile (replay-safe no-op if already present)
    with sf() as session:
        profile_id = register_embedding_profile(
            session,
            provider=settings.embedding_provider,
            model_identifier=settings.embedding_model,
            dimension=dimension,
            normalization_policy="none",
            chunking_schema_version="chunk_v1",
        )
        session.commit()
    print(f"[probe] profile registered: {profile_id[:16]}...")

    # Load profile snapshot
    from sqlalchemy import select
    from backend.db.models import EmbeddingProfile
    with sf() as session:
        profile_row = session.execute(
            select(EmbeddingProfile).where(EmbeddingProfile.profile_id == profile_id)
        ).scalar_one()
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

    endpoint = settings.embedding_base_url or settings.lmstudio_base_url
    settings_snapshot = EmbeddingRuntimeSettingsSnapshot(
        provider_kind=settings.embedding_provider,
        requested_model=settings.embedding_model,
        expected_dimension=dimension,
        declared_normalization_policy="none",
        document_task=None,
        query_task=None,
        endpoint=endpoint,
        configured_deployment_id=None,
        deployment_is_explicitly_pinned=False,
    )
    adapter_snapshot = EmbeddingAdapterCapabilitySnapshot(
        provider_adapter_contract_version="openai_v1",
        governed_adapter_contract_version="governed_v1",
        implemented_postprocessing_policy="none",
        supports_document_embedding=True,
        supports_query_embedding=True,
    )
    effective_config = resolve_effective_embedding_configuration(
        settings=settings_snapshot,
        profile=profile_snapshot,
        adapter=adapter_snapshot,
    )

    governed_adapter = GovernedEmbeddingAdapter(
        embedding_service=emb_service,
        provider_kind=effective_config.provider_kind,
        requested_model=effective_config.requested_model,
        configured_dimension=effective_config.expected_dimension,
    )

    print("[probe] running governed dual_probe (this may take a few seconds)...")
    pub = asyncio.run(
        run_capability_check(sf, governed_adapter, effective_config, check_ttl_seconds=3600)
    )
    print(f"[probe] check_id={pub.check_id[:16]}... status={pub.status}")
    if pub.binding_id:
        print(f"[probe] binding_id={pub.binding_id[:16]}...")
    if pub.status != "passed":
        raise RuntimeError(
            f"governed dual_probe did not pass (status={pub.status}, "
            f"failure_code={getattr(pub,'failure_code',None)}). "
            f"Snapshot generation aborted — no binding exists."
        )
    if not pub.binding_id:
        raise RuntimeError("probe passed but no binding resolved — aborting")
    return governed_adapter, effective_config, sf, pub


async def _embed_all(runtime, cases):
    """Embed every query + candidate through the authorized runtime.

    Returns (items, binding_receipt) where binding_receipt is evidence
    captured from the authorized receipts (binding_id, check_id, runtime_fp).
    """
    # Deduplicate candidate texts across the whole benchmark so each unique
    # text is embedded once (some candidates may recur, though in this
    # benchmark they don't).
    items: list[SnapshotItem] = []
    binding_evidence = {}

    for case in cases:
        # Query
        q_text = _query_canonical_text(case)
        q_receipt = await runtime.embed_query_authorized(q_text)
        items.append(SnapshotItem(
            item_id=case.case_id,
            item_role="query",
            canonical_text=q_text,
            text_hash=canonical_text_hash(q_text),
            vector=tuple(q_receipt.embedding),
            vector_fingerprint=vector_fingerprint(q_receipt.embedding),
        ))
        binding_evidence["capability_binding_id"] = q_receipt.capability_binding_id
        binding_evidence["capability_check_id"] = q_receipt.capability_check_id
        binding_evidence["generation_runtime_fingerprint"] = q_receipt.runtime_config_fingerprint

        # Candidates — batch per case
        cand_texts = [_candidate_canonical_text(case, c) for c in case.candidates]
        c_receipt = await runtime.embed_documents_authorized(cand_texts)
        for cand, text, vec in zip(case.candidates, cand_texts, c_receipt.embeddings):
            items.append(SnapshotItem(
                item_id=cand.candidate_id,
                item_role="candidate",
                canonical_text=text,
                text_hash=canonical_text_hash(text),
                vector=tuple(vec),
                vector_fingerprint=vector_fingerprint(vec),
            ))
        binding_evidence["capability_binding_id"] = c_receipt.capability_binding_id
        binding_evidence["capability_check_id"] = c_receipt.capability_check_id
        binding_evidence["generation_runtime_fingerprint"] = c_receipt.runtime_config_fingerprint

    return items, binding_evidence


def generate():
    """Full P1B.2 generation: preflight, probe, embed, snapshot."""
    from backend.pipeline.capability.verified_embedding_runtime import build_verified_embedding_runtime
    from backend.ranking.embedding_snapshot import clear_snapshot_dir

    # 1. preflight (fail loudly if model not loaded)
    preflight_provider()

    # 2+3. register profile + run governed dual_probe
    governed_adapter, effective_config, sf, pub = register_profile_and_run_probe()

    # 4. build the verified runtime (fail-closed)
    runtime = build_verified_embedding_runtime(
        embedding_adapter=governed_adapter,
        effective_config=effective_config,
        session_factory=sf,
    )
    print(f"[runtime] verified runtime built: binding={runtime.capability_binding_id[:16]}... "
          f"check={runtime.capability_check_id[:16]}...")

    # 5. embed all queries + candidates through the authorized runtime
    cases = frozen_v2_cases()
    print(f"[embed] embedding {len(cases)} queries + "
          f"{sum(len(c.candidates) for c in cases)} candidates...")
    items, _be = asyncio.run(_embed_all(runtime, cases))
    print(f"[embed] produced {len(items)} items "
          f"({sum(1 for i in items if i.item_role=='query')} queries, "
          f"{sum(1 for i in items if i.item_role=='candidate')} candidates)")

    # 6. build binding evidence and write the immutable snapshot
    benchmark_fp = compute_benchmark_v2_fingerprint()
    binding = SnapshotBindingEvidence(
        capability_binding_id=runtime.capability_binding_id,
        capability_check_id=runtime.capability_check_id,
        generation_runtime_fingerprint=runtime.effective_embedding_config and _runtime_fp(effective_config),
        provider_kind=effective_config.provider_kind,
        provider_model=effective_config.requested_model,
        provider_revision=None,
        endpoint_identity=effective_config.sanitized_endpoint_identity,
        deployment_id=effective_config.configured_deployment_id,
        embedding_contract_version=effective_config.provider_adapter_contract_version,
        dimension=effective_config.expected_dimension,
        normalization_policy=effective_config.declared_normalization_policy,
    )
    if SNAPSHOT_DIR.exists() and (SNAPSHOT_DIR / "snapshot.json").exists():
        print(f"[snapshot] clearing existing snapshot at {SNAPSHOT_DIR}")
        clear_snapshot_dir(SNAPSHOT_DIR)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = write_snapshot(
        SNAPSHOT_DIR,
        benchmark_version=BENCHMARK_V2["version"],
        benchmark_fingerprint=benchmark_fp,
        binding=binding,
        items=items,
    )
    print(f"[snapshot] WROTE {path}")
    print(f"[snapshot] benchmark_fingerprint = {benchmark_fp}")
    return path


def _runtime_fp(effective_config) -> str:
    from backend.pipeline.capability.capability_identity import compute_runtime_config_fingerprint
    return compute_runtime_config_fingerprint(effective_config)


if __name__ == "__main__":
    generate()
