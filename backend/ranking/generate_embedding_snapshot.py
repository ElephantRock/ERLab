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


# P1C: snapshot dir is configurable so multiple candidate models can each
# produce their own snapshot under docs/p1c_snapshots/<model_tag>/ without
# overwriting the frozen P1B control snapshot at docs/p1b_snapshot/.
import os as _os
_P1C_TAG = _os.environ.get("P1C_SNAPSHOT_TAG", "").strip()
if _P1C_TAG:
    SNAPSHOT_DIR = _REPO_ROOT / "docs" / "p1c_snapshots" / _P1C_TAG
else:
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
    base = (s.embedding_base_url or s.lmstudio_base_url).rstrip("/")
    # Normalize: providers may configure base_url with or without a trailing
    # /v1. The OpenAI-compatible paths are /v1/models and /v1/embeddings, so
    # build the api_root accordingly (avoid /v1/v1/...).
    if base.endswith("/v1"):
        api_root = base
    else:
        api_root = f"{base}/v1"
    print(f"[preflight] provider={s.embedding_provider} model={s.embedding_model}")
    print(f"[preflight] endpoint={base} (api_root={api_root})")
    try:
        with httpx.Client(timeout=20) as c:
            r = c.get(f"{api_root}/models")
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
            if s.embedding_model not in ids:
                raise RuntimeError(
                    f"model {s.embedding_model!r} not in served models {ids}"
                )
            # Trivial embedding probe to confirm the model is LOADED (not just
            # registered — LM Studio lists models that aren't loaded yet).
            er = c.post(
                f"{api_root}/embeddings",
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


def _build_fresh_adapter(effective_config):
    """Construct a fresh GovernedEmbeddingAdapter for the embed phase.

    The probe phase (register_profile_and_run_probe) runs in its own event
    loop and the LMStudioEmbeddingProvider's httpx.AsyncClient is bound to
    that loop. To embed in a new event loop we build a fresh provider+adapter
    with the same effective config; the verified runtime then reads the
    binding/check the probe just published from the DB.
    """
    from backend.config import get_settings
    from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
    from backend.pipeline.knowledge.embedding_service import EmbeddingService
    from backend.pipeline.governed_embedding_adapter import GovernedEmbeddingAdapter

    settings = get_settings()
    provider = create_embedding_provider(
        provider_name=settings.embedding_provider,
        model=settings.embedding_model,
        api_key=settings.openai_api_key,
        base_url=settings.embedding_base_url or settings.lmstudio_base_url,
        dimension=settings.embedding_dimension or None,
    )
    emb_service = EmbeddingService(provider)
    return GovernedEmbeddingAdapter(
        embedding_service=emb_service,
        provider_kind=effective_config.provider_kind,
        requested_model=effective_config.requested_model,
        configured_dimension=effective_config.expected_dimension,
    )


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


class SnapshotGenerationFailure(Exception):
    """Terminal failure of a snapshot generation attempt.

    Carries a bounded failure_code vocabulary so a repeatedly-crashing
    provider cannot appear merely slow: the closeout records exactly which
    terminal condition fired and on which item.
    """

    # Closed failure-code vocabulary
    CODE_AUTHORITY_FAILURE = "authority_failure"            # governance: abort, no retry
    CODE_RETRY_EXHAUSTED = "retry_exhausted"                # transient failures > max_retries
    CODE_NON_TRANSIENT_PROVIDER = "non_transient_provider"  # provider error not classified transient
    CODE_EMPTY_VECTOR = "empty_vector"                      # provider returned no vectors

    def __init__(self, code: str, *, item_id: str, attempts: int, detail: str):
        self.code = code
        self.item_id = item_id
        self.attempts = attempts
        self.detail = detail
        super().__init__(
            f"snapshot generation failed [{code}] on item {item_id!r} "
            f"after {attempts} attempt(s): {detail}"
        )


# Transient provider-failure signatures (substring match on the error
# message from the LM Studio / OpenAI-compatible HTTP layer). These are the
# only failures eligible for bounded retry. Anything else is terminal.
_TRANSIENT_SIGNATURES = (
    "model has crashed",
    "model reloaded",
    "no models loaded",
    "model is unloaded",
    "connection reset",
    "read timeout",
    "remote protocol error",
    "503",  # service unavailable
    "502",  # bad gateway
)


def _is_transient_provider_error(exc: BaseException) -> bool:
    """Classify whether ``exc`` is a transient provider failure eligible for retry.

    Authority/governance failures (CapabilityAuthorizationError) are NEVER
    transient — they abort immediately. Non-transient provider errors
    (e.g. 400 with a real error body that isn't a crash/reload signature,
    401 auth, 404 model-not-found) are also terminal.
    """
    from backend.pipeline.capability.capability_errors import CapabilityAuthorizationError
    if isinstance(exc, CapabilityAuthorizationError):
        return False
    msg = str(exc).lower()
    return any(sig in msg for sig in _TRANSIENT_SIGNATURES)


async def _embed_one_with_retry(runtime, text: str, *, is_query: bool, item_id: str,
                                max_retries: int = 8):
    """Embed a single text through the authorized runtime with bounded retry.

    Retry policy (frozen by the P1C closeout qualification, 2026-07-21):

      authority or binding failure    → fail immediately, no retry
      transient provider failure      → bounded retry (max_retries, exp backoff)
      candidate snapshot failure      → no partial snapshot promoted as valid
      retry exhaustion                → explicit SnapshotGenerationFailure(RETRY_EXHAUSTED)
      control snapshot                → never overwritten (enforced by write_snapshot)
      retry policy                    → experiment-harness only, NOT a production default

    Per-item attempt counts are recorded on the terminal exception so a
    repeatedly-crashing provider cannot appear merely slow.
    """
    import asyncio as _aio
    from backend.pipeline.capability.capability_errors import CapabilityAuthorizationError

    attempts = 0
    last_exc: BaseException | None = None
    for attempt in range(max_retries):
        attempts += 1
        try:
            if is_query:
                return await runtime.embed_query_authorized(text)
            receipt = await runtime.embed_documents_authorized([text])
            if not receipt.embeddings:
                raise SnapshotGenerationFailure(
                    SnapshotGenerationFailure.CODE_EMPTY_VECTOR,
                    item_id=item_id, attempts=attempts,
                    detail="provider returned zero vectors",
                )
            class _Single:
                embedding = receipt.embeddings[0]
                capability_binding_id = receipt.capability_binding_id
                capability_check_id = receipt.capability_check_id
                runtime_config_fingerprint = receipt.runtime_config_fingerprint
                authorized_at = receipt.authorized_at
            return _Single()
        except SnapshotGenerationFailure:
            raise  # already classified terminal
        except CapabilityAuthorizationError as e:
            # Governance failure: abort immediately, no retry, explicit code.
            raise SnapshotGenerationFailure(
                SnapshotGenerationFailure.CODE_AUTHORITY_FAILURE,
                item_id=item_id, attempts=attempts,
                detail=f"{type(e).__name__}: {e}",
            ) from e
        except Exception as e:
            last_exc = e
            if not _is_transient_provider_error(e):
                # Non-transient provider error (e.g. real 400/401/404): terminal.
                raise SnapshotGenerationFailure(
                    SnapshotGenerationFailure.CODE_NON_TRANSIENT_PROVIDER,
                    item_id=item_id, attempts=attempts,
                    detail=f"{type(e).__name__}: {e}",
                ) from e
            # transient: backoff and retry
            await _aio.sleep(min(2.0 ** attempt, 30.0))
    # retry exhausted
    raise SnapshotGenerationFailure(
        SnapshotGenerationFailure.CODE_RETRY_EXHAUSTED,
        item_id=item_id, attempts=attempts,
        detail=f"transient failures persisted across {attempts} attempts; last: "
               f"{type(last_exc).__name__ if last_exc else 'unknown'}: {last_exc}",
    )


async def _embed_all(runtime, cases):
    """Embed every query + candidate through the authorized runtime.

    Uses single-text authorized embeds with bounded retry to tolerate the
    LM Studio host's transient model-crash/reload instability. Every vector
    still carries the full authorized-receipt binding evidence.

    Returns (items, binding_evidence).
    """
    items: list[SnapshotItem] = []
    binding_evidence = {}
    total = sum(1 + len(c.candidates) for c in cases)
    done = 0

    for case in cases:
        # Query
        q_text = _query_canonical_text(case)
        q_receipt = await _embed_one_with_retry(
            runtime, q_text, is_query=True, item_id=case.case_id,
        )
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
        done += 1

        # Candidates — one at a time with retry (batches crash more on this host)
        for cand in case.candidates:
            text = _candidate_canonical_text(case, cand)
            c_receipt = await _embed_one_with_retry(
                runtime, text, is_query=False, item_id=cand.candidate_id,
            )
            items.append(SnapshotItem(
                item_id=cand.candidate_id,
                item_role="candidate",
                canonical_text=text,
                text_hash=canonical_text_hash(text),
                vector=tuple(c_receipt.embedding),
                vector_fingerprint=vector_fingerprint(c_receipt.embedding),
            ))
            binding_evidence["capability_binding_id"] = c_receipt.capability_binding_id
            binding_evidence["capability_check_id"] = c_receipt.capability_check_id
            binding_evidence["generation_runtime_fingerprint"] = c_receipt.runtime_config_fingerprint
            done += 1
            if done % 50 == 0:
                print(f"[embed]   ...{done}/{total}")

    return items, binding_evidence


def generate():
    """Full P1B.2 generation: preflight, probe, embed, snapshot."""
    from backend.pipeline.capability.verified_embedding_runtime import build_verified_embedding_runtime
    from backend.ranking.embedding_snapshot import clear_snapshot_dir

    # 1. preflight (fail loudly if model not loaded)
    preflight_provider()

    # 2+3. register profile + run governed dual_probe (in its own event loop).
    # The probe's adapter binds an httpx.AsyncClient to this loop; the loop
    # closes when register_profile_and_run_probe returns. We then build a
    # FRESH adapter + runtime for the embed phase below, reusing the same
    # binding/check the probe just wrote to the DB.
    _governed_adapter_probe, effective_config, sf, pub = register_profile_and_run_probe()

    # 4. build a fresh verified runtime for the embed phase (fail-closed).
    # The runtime reads the binding/check the probe just published, so this
    # succeeds iff the governed dual_probe genuinely passed.
    fresh_adapter = _build_fresh_adapter(effective_config)
    runtime = build_verified_embedding_runtime(
        embedding_adapter=fresh_adapter,
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
