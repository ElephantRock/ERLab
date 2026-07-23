# P1D Closeout — TEI Embedding Investigation (Corrected)

## Outcome: B — Reliable operation, no significant ranking improvement

```text
LM Studio embedding investigation   CLOSED as operational failure
TEI replacement experiment          CLOSED — operationally stable
ranking improvement                 NONE (not statistically significant)
P1 ranking blocker                 NOT CLOSED
P2                                  BLOCKED
```

## Summary

P1D determined that TEI (Text Embeddings Inference) with
`gte-large-en-v1.5` is **operationally stable** but produces **no
significant ranking improvement** over the frozen P1B baseline.

The earlier reported improvement (+0.038 nDCG) was an **evaluator
drift artifact** — caused by using binary relevance instead of graded
relevance in the direct evaluator. After calibrating the evaluator
against the frozen P1B snapshot (parity proven within 0.02 tolerance),
the corrected deltas are negligible:

- semantic_only nDCG@5: +0.0065 (95% CI [-0.008, +0.021], not significant)
- hybrid_rrf nDCG@5: -0.0022 (slightly worse, not significant)

## Frozen identity

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
query protocol          'query: ' prefix on queries; documents unprefixed
max-client-batch-size   32
max-concurrent-requests 2
```

## Operational gate (P1D.3a/3b) — PASSED

```
single-input preflight         243/243 (81 × 3)
HTTP 5xx                       0
timeouts                       0
container restarts             0
dimension changes              0
non-finite vectors             0
median latency                 343ms
p95 latency                    421ms
max latency                    500ms
zero truncation proven         yes (max 49 tokens, ceiling 512)
container args frozen          yes
```

## Evaluator parity (P1D.4a) — PROVEN

The direct evaluator reproduces the frozen P1B baseline metrics
within 0.02 tolerance using the exact graded-relevance formulas:
exponential gain (2^g - 1), threshold g > 0 for MRR, threshold g >= 1
for P@5/R@20, and `re.findall(r"\w+")` for lexical tokenization.

## Corrected ranking comparison (P1D.4b)

### Macro metrics

```
                         P1B baseline        P1D TEI           Delta      Sig?
                         (qwen3-0.6b)        (gte-large-v1.5)

semantic_only
  nDCG@5                   0.9288            0.9353           +0.0065    No
  nDCG@10                  0.9288            0.9353           +0.0065    No
  MRR@10                   0.9924            1.0000           +0.0076    No
  P@5                      0.7636            0.7636            0.0000    —
  R@5                      1.0000            1.0000            0.0000    —
  R@10                     1.0000            1.0000            0.0000    —
  R@20                     1.0000            1.0000            0.0000    —
  Top-1                    0.9848            1.0000           +0.0152    No

hybrid_rrf
  nDCG@5                   0.9506            0.9484           -0.0022    No
  nDCG@10                  0.9506            0.9484           -0.0022    No
  MRR@10                   1.0000            1.0000            0.0000    —
  P@5                      0.7636            0.7636            0.0000    —
  R@20                     1.0000            1.0000            0.0000    —
  Top-1                    1.0000            1.0000            0.0000    —
```

### Per-query analysis (semantic_only nDCG@5)

```
queries improved              15/66
queries regressed             12/66
queries tied                  39/66
top-1 improved                 1
top-1 regressed                0
largest improvement          +0.2167 (bio_disc_ei_001)
largest regression           -0.1720 (ml_ret_ei_001)
```

### Paired bootstrap CI (semantic_only nDCG@5)

```
mean delta                   +0.0065
95% CI                       [-0.0079, +0.0210]
significant (excludes 0)     False
```

### Per-query analysis (hybrid_rrf nDCG@5)

```
queries improved               9/66
queries regressed             10/66
queries tied                  47/66
top-1 improved                  0
top-1 regressed                 0
```

### Paired bootstrap CI (hybrid_rrf nDCG@5)

```
mean delta                   -0.0022
95% CI                       [-0.0095, +0.0041]
significant (excludes 0)     False
```

## Assessment

The gte-large-en-v1.5 embeddings produce **marginal, non-significant
ranking changes** compared to the qwen3-embedding-0.6b baseline. The
differences are within evaluator noise:

1. semantic_only shows a tiny aggregate improvement (+0.0065 nDCG@5)
   but the 95% bootstrap CI includes 0, and 12 of 66 queries actually
   regressed.

2. hybrid_rrf shows a tiny aggregate regression (-0.0022 nDCG@5) —
   the TEI embeddings are actually slightly WORSE in the hybrid
   configuration.

3. All Recall metrics are 1.0000 for both snapshots — the benchmark
   corpus has too few candidates per case to distinguish recall.

This confirms the P1B diagnostic hypothesis: the frozen v2 benchmark
corpus (66 cases × ~4 candidates each) **lacks discriminative power**
at this quality level. Both embedding models score above 0.93 nDCG,
and the differences between them are within measurement noise.

## Query preprocessing (frozen)

```
query transformation      'query: {query_text}' prefix (GTE model card convention)
document transformation   '{title}\n\n{abstract}' (no prefix)
whitespace normalization  none (verbatim from benchmark)
title/abstract join       '\n\n' separator
empty-field handling      not applicable (no empty fields in frozen corpus)
token truncation          none (max 49 tokens, ceiling 512)
cosine normalization      TEI outputs L2-normalized vectors; cosine = dot product
```

## Decision

**Outcome B**: TEI with gte-large-en-v1.5 runs reliably but does not
produce a statistically significant ranking improvement. The P1 ranking
blocker remains open. P2 remains blocked.

The bottleneck is not the embedding model — it is the benchmark's
discriminative power. A more challenging corpus (more candidates per
query, harder negatives, larger judgment scale) would be needed to
distinguish between embedding models at this quality level.

## Production-readiness (qualified)

```
TEI service endpoint                  operationally viable
direct experimental embedding path    working + calibrated
governed ERLab embedding path         not integrated (requires capability system work)
production migration                  NOT AUTHORIZED
index replacement                     NOT AUTHORIZED
```

TEI is a viable candidate for production embedding hosting based on
its operational stability. However, integration into the governed
ERLab embedding runtime (which requires the capability/probe/binding
system to work with TEI's `/info` instead of LM Studio's `/v1/models`)
is out of scope for P1D.

## Recommendations

1. The P1 ranking blocker requires a **more discriminative benchmark
   corpus** — the current corpus cannot distinguish between models
   at 0.93+ nDCG.

2. Alternatively, a **fundamentally different retrieval architecture**
   (reranker, multi-stage retrieval, cross-encoder) may produce larger
   gains than embedding model selection.

3. TEI is the recommended **production embedding runtime** when
   migration is authorized — it is the only host on this machine that
   passed sustained operational preflight without crashes.
