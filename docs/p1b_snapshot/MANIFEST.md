# P1B.2 Embedding Snapshot — Generation Manifest

## Status

```
P1B.2      GENERATED — governed real-provider snapshot produced
P1B.3      AUTHORIZED — policy evaluation may proceed against this snapshot
P1B.4+     NOT YET AUTHORIZED
```

## Snapshot identity

| Field | Value |
|---|---|
| snapshot schema version | `ranking_embedding_snapshot_v1` |
| benchmark version | `discovery_ranking_v2+retrieval_ranking_v2` |
| benchmark fingerprint | `0ffbfdb164053ad19c869cbba44678c0aa76aa140557320383a82efcebcb96e4` |
| **snapshot fingerprint** | `2d8b26f709c03b6bbc7d5c4ab7ca65259a87e8f06ef80b3da0e9e50df69b38d2` |
| snapshot fingerprint (sidecar) | committed at `docs/p1b_snapshot/snapshot.fingerprint` |
| capability binding id | `6058e7d9960c5ff7e7225ee421c818fc0dfb61798990e2fafa7725ceb9486374` |
| capability check id | `7168201318544ea8a6cf77aeb69d182a` |
| generation runtime fingerprint | `3ba1e8acc81467d5b53d3ae1b0a4030b...` |
| provider kind | `lmstudio` |
| provider model | `text-embedding-qwen3-embedding-0.6b` |
| endpoint identity | `http://100.64.0.2:1234/v1` |
| embedding contract version | `openai_v1` |
| dimension | `1024` |
| normalization policy | `none` |
| items | `336` (66 queries + 270 candidates) |
| created at | `2026-07-20T23:05:51.270078+00:00` |

## Provenance

Generated through the **governed path** per Decision 1C:

```
EffectiveEmbeddingConfiguration
→ run_capability_check (governed dual_probe, PASSED)
→ embedding_capability_binding resolved (6058e7d9...)
→ build_verified_embedding_runtime (fail-closed)
→ VerifiedEmbeddingRuntime.embed_query_authorized  (66 queries)
→ VerifiedEmbeddingRuntime.embed_documents_authorized (270 candidates)
→ write_snapshot (immutable, self-fingerprinting)
```

Every vector carries binding evidence from the authorized receipt
(`capability_binding_id`, `capability_check_id`, `runtime_config_fingerprint`).
No silent fallback, no stub embedder, no cross-binding scoring.

## Provider selection rationale

`voyage-4-nano` (the originally requested model) was **not loaded** on the
LM Studio host. A stability probe across all loaded models on real benchmark
text (3 retries each) found:

```
text-embedding-qwen3-embedding-0.6b:    3/3 stable  (1024d)  ← selected
text-embedding-all-minilm-l12-v2:       3/3 stable  (384d)
bortunac/text-embedding-bge-m3-embeddings: 0/3 stable (crashes)
forrint/text-embedding-bge-m3-embeddings:  0/3 stable (crashes)
text-embedding-nomic-embed-text-v2-moe: 0/3 stable (crashes)
jina-embeddings-v5-text-small-retrieval: 0/3 stable (crashes)
```

`qwen3-embedding-0.6b` was selected because it was the only stable model
matching the configured 1024-dimension profile. `all-minilm-l12-v2` is stable
but 384d (would require a different profile/dimension and is a smaller,
English-only model).

The host's LM Studio is exhibiting model-crash instability (segfault exit
codes wrapped as large unsigned numbers) under load on the BGE-M3 / nomic /
jina variants. This is an environmental issue on the provider host, not in
the governed path.

## Canonical text convention

- queries: embedded as `case.query_text` verbatim
- candidates: embedded as `"{title}\n\n{abstract}"` — the same canonical form
  the benchmark's `content_hash` covers

Verified: all 270 candidate `text_hash` values in the snapshot exactly equal
the benchmark's `content_hash` values (0 mismatches). This makes text drift
detectable on both the benchmark side and the snapshot side.

## Storage policy

`snapshot.json` is **~10.8 MB** (336 vectors × 1024 dims). It is gitignored
(see `.gitignore`) and **regenerated** rather than committed, because:

1. it is bit-reproducible from the frozen benchmark + the generation harness
   (the snapshot fingerprint makes any regeneration self-verifying)
2. committing 10MB of floats would dominate the repo history
3. the frozen benchmark fingerprint (`0ffbfdb1...`) is the load-bearing
   invariant; the snapshot fingerprint (`2d8b26f7...`) is bound to it

Committed provenance:
- `docs/p1b_snapshot/snapshot.fingerprint` — the canonical sidecar
- `docs/p1b_snapshot/MANIFEST.md` — this file
- `backend/ranking/generate_embedding_snapshot.py` — the generation harness
- `backend/ranking/embedding_snapshot.py` — the snapshot format + integrity

## Regeneration

```bash
# Precondition: LM Studio host serving text-embedding-qwen3-embedding-0.6b
# at http://100.64.0.2:1234, model loaded and stable.
export EROCK_EMBEDDING_MODEL=text-embedding-qwen3-embedding-0.6b
export EROCK_EMBEDDING_BASE_URL=http://100.64.0.2:1234/v1
export EROCK_EMBEDDING_DIMENSION=1024
python -m backend.ranking.generate_embedding_snapshot
```

The regenerated `snapshot.json` MUST produce the same snapshot fingerprint
`2d8b26f709c03b6bbc7d5c4ab7ca65259a87e8f06ef80b3da0e9e50df69b38d2`
(provider model nondeterminism notwithstanding — see "deterministic replay"
definition in `docs/p1b_execution_contract.md` §13). If the fingerprint
differs, the regeneration used a different binding, benchmark, or provider
and must NOT be used for P1B.3 without re-verification.

## Verification

```bash
python -c "
from pathlib import Path
from backend.ranking.embedding_snapshot import load_snapshot
from backend.ranking.benchmark_v2_registry import compute_benchmark_v2_fingerprint, BENCHMARK_V2
snap = load_snapshot(
    Path('docs/p1b_snapshot'),
    expected_benchmark_fingerprint=compute_benchmark_v2_fingerprint(),
    expected_benchmark_version=BENCHMARK_V2['version'],
)
print('snapshot fingerprint:', snap.snapshot_fingerprint)
print('items:', len(snap.items))
"
```

This runs every Decision 1C replay-must-fail check (benchmark fingerprint,
binding evidence, dimension, normalization, vector fingerprints, sidecar).
