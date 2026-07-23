# P1D Closeout — TEI Embedding Investigation (Exact-Parity Corrected)

## Outcome: B — Reliable operation, no significant ranking improvement

```text
LM Studio embedding investigation   CLOSED as operational failure
TEI replacement experiment          CLOSED — operationally stable
evaluator parity                    EXACT (1e-12) against frozen P1B
ranking improvement                 NONE (not statistically significant)
P1 ranking blocker                 NOT CLOSED
P2                                  BLOCKED
```

## Frozen identity (P1D.3c)

```
TEI image               ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
TEI image digest        sha256:ad950d30878eceb72aaf32024d26fa2b1d04a75304fa0b4776b49aa1941fea07
TEI version             1.9.3 (sha 06670157fb6c1523482219bdb2d1660277d38088)
model                   Alibaba-NLP/gte-large-en-v1.5
model revision          104333d6af6f97649377c2afbde10a7704870c7b
pooling                 cls
dtype                   float32
dimension               1024
configured token limit  512 (max input observed: 49 tokens — zero truncation)
query protocol          'query: {text}' prefix on queries; documents unprefixed
max-client-batch-size   1 (frozen — single-input experimental profile)
max-concurrent-requests 2
```

### Supported request shape (truthful)

```
validated request shape         one input per HTTP request
batched production use          NOT validated (429 at batch=8)
production migration            NOT authorized
```

## Operational gate (P1D.3c) — PASSED

```
single-input preflight         243/243 (81 passages × 3)
query preflight                198/198 (66 queries × 3)
HTTP 5xx                       0
timeouts                       0
container restarts             0
dimension changes              0
non-finite vectors             0
median latency                 375ms
p95 latency                    484ms
max latency                    547ms
zero truncation proven         yes (max 49 tokens, ceiling 512)
```

## Evaluator parity (P1D.4c) — EXACT MATCH

Both snapshots run through the **original P1B.3 evaluator** functions
(`_build_request`, `_run_policy`, `rank_semantic_only`, `rank_hybrid_rrf`,
`rank_legacy_lexical`, `evaluate_v2`, `macro_average`, `_grade_for`).
Only the embedding-snapshot adapter changes — no parallel reimplementation.

Split discipline honored: **44 calibration+development cases** (22 held_out
excluded, matching the P1B.3 frozen protocol).

```
                         P1B baseline       Our eval (same code)     Match
lexical
  nDCG@5                   0.9495             0.9495                EXACT
  MRR@10                   1.0000             1.0000                EXACT
  P@5                      0.7591             0.7591                EXACT
  R@20                     1.0000             1.0000                EXACT

semantic_only
  nDCG@5                   0.9321             0.9321                EXACT
  MRR@10                   0.9886             0.9886                EXACT
  P@5                      0.7591             0.7591                EXACT
  R@20                     1.0000             1.0000                EXACT

hybrid_rrf
  nDCG@5                   0.9561             0.9561                EXACT
  MRR@10                   1.0000             1.0000                EXACT
  P@5                      0.7591             0.7591                EXACT
  R@20                     1.0000             1.0000                EXACT
```

Root cause of prior drift: missing split discipline (66 cases instead of
44 cal+dev). Fixed by filtering to `split != "held_out"`.

## TEI comparison (exact-parity evaluator, cal+dev, 44 cases)

### Macro metrics

```
                         P1B baseline        P1D TEI           Delta      Bootstrap CI
                         (qwen3-0.6b)        (gte-large-v1.5)              (95%)

semantic_only
  nDCG@5                   0.9321            0.9480           +0.0159    [-0.001, +0.034]
  MRR@10                   0.9886            1.0000           +0.0114    (not tested)
  P@5                      0.7591            0.7591            0.0000    —
  R@20                     1.0000            1.0000            0.0000    —

hybrid_rrf
  nDCG@5                   0.9561            0.9517           -0.0044    [-0.015, +0.004]
  MRR@10                   1.0000            1.0000            0.0000    —
  P@5                      0.7591            0.7591            0.0000    —
  R@20                     1.0000            1.0000            0.0000    —
```

### Per-query analysis

```
semantic_only:
  identical ranking       25/44
  different ranking       19/44
  bootstrap CI includes 0 yes (not significant)

  largest improvement     bio_disc_ei_001: +0.2167
  largest regression      ml_ret_mv_001:   -0.1498

hybrid_rrf:
  identical ranking       30/44
  different ranking       14/44
  bootstrap CI includes 0 yes (not significant)

  largest improvement     bio_disc_ei_001: +0.0508
  largest regression      bio_ret_ac_001:  -0.1420
```

### Paired bootstrap CI (10000 iterations, seed=42, 95%)

```
semantic_only nDCG@5:
  mean delta     +0.0159
  95% CI         [-0.0013, +0.0343]
  significant    NO (CI includes 0)

hybrid_rrf nDCG@5:
  mean delta     -0.0044
  95% CI         [-0.0147, +0.0043]
  significant    NO (CI includes 0)
```

## Query preprocessing (frozen)

```
query transformation      'query: {query_text}' prefix (GTE model card)
document transformation   '{title}\n\n{abstract}' (no prefix)
whitespace normalization  none (verbatim from benchmark)
title/abstract join       '\n\n' separator
empty-field handling      not applicable (no empty fields in frozen corpus)
token truncation          none (max 49 tokens, ceiling 512)
cosine normalization      TEI outputs L2-normalized vectors; cosine = dot product
```

## Assessment

gte-large-en-v1.5 produces a **small, non-significant** improvement on
semantic_only nDCG@5 (+0.0159) but a **small regression** on hybrid_rrf
nDCG@5 (-0.0044). Neither clears statistical significance. The
benchmark corpus lacks discriminative power: all policies score above
0.93 nDCG, all Recall metrics are 1.0.

The differences between the two embedding models are within the noise
floor of the benchmark. The P1 ranking blocker is not an embedding-model
problem — it is a benchmark-discriminative-power problem.

## Final gate

```
final declared request shape passes preflight            proven (single-input)
unsupported batching claimed as validated                0
P1B aggregate metrics reproduced within 1e-12            proven
P1B per-query rankings reproduced exactly                proven
tie outcomes reproduced exactly                          proven
TEI comparison uses the same evaluator                   proven
paired confidence intervals regenerated                  proven
silent fallback or truncation                            0
production migration authorized                          no
```

## Decision

**Outcome B**: TEI with gte-large-en-v1.5 runs reliably (single-input
profile) but does not produce a statistically significant ranking
improvement. The P1 ranking blocker remains open. P2 remains blocked.

Production migration is NOT authorized: the governed ERLab embedding
path is not integrated with TEI, and batched production use is not
validated.

## Recommendations

1. The P1 ranking blocker requires a **more discriminative benchmark
   corpus** (more candidates, harder negatives, larger judgment scale).

2. Alternatively, a **fundamentally different retrieval architecture**
   (reranker, multi-stage retrieval) may produce larger gains.

3. TEI is a viable candidate for **production embedding hosting** when
   the governed integration is built and batched use is validated.
