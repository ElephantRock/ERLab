# P1D Closeout — TEI Embedding Investigation

## Outcome: B — Reliable operation, mixed ranking improvement

```text
LM Studio embedding investigation   CLOSED as operational failure
TEI replacement experiment          CLOSED — operationally stable
ranking improvement                 MIXED (nDCG improved, MRR regressed)
P1 ranking blocker                 NOT CLOSED
P2                                  BLOCKED
```

## Summary

P1D set out to determine whether a stronger embedding configuration
could produce a defensible ranking improvement over the frozen P1B
negative result, or establish that the available local embedding path
is operationally unsuitable.

Three things were established:

1. **LM Studio is operationally unsuitable for sustained embedding loads**
   (CLOSED in prior P1D.5 falsification — all nomic/bert/gemma
   architectures crash under sustained load).

2. **TEI (Text Embeddings Inference) with gte-large-en-v1.5 is
   operationally stable** on this CPU host — 243/243 preflight pass,
   zero crashes, deterministic output, median latency 343ms.

3. **The TEI embeddings produce a MIXED ranking result** — nDCG@5/10
   and P@5 improved modestly, but MRR@10 regressed. The improvement
   does not uniformly clear the P1B frozen quality gate.

## Detailed results

### Operational gate (P1D.3)

```
TEI version                  1.9.3 (sha 06670157fb6c1523482219bdb2d1660277d38088)
model                        Alibaba-NLP/gte-large-en-v1.5 (434M, BERT/GTE arch)
pooling                      cls
dtype                        float32
dimension                    1024
preflight                    243/243 (81 passages × 3 runs)
HTTP 5xx                     0
timeouts                     0
container restarts           0
worker terminations          0
median latency               343ms
p95 latency                  375ms
max latency                  407ms
repeated-input cosine        1.0000000000 (deterministic)
```

### Ranking comparison (P1D.4)

Same frozen corpus (66 cases, 270 candidates, 270 judgments).
Same ranking policies. Same metrics.

```
                         P1B baseline        P1D TEI           Delta
                         (BGE-M3/qwen3)      (gte-large-v1.5)

semantic_only
  nDCG@5                   0.9321            0.9702           +0.0381 ★
  nDCG@10                  0.9321            0.9702           +0.0381 ★
  MRR@10                   0.9886            0.9672           -0.0214 ✗
  P@5                      0.7591            0.7848           +0.0257 ★
  R@20                     1.0000            1.0000            0.0000 =

hybrid_rrf
  nDCG@5                   0.9561            0.9734           +0.0173 ★
  MRR@10                   1.0000            0.9924           -0.0076 ✗
  P@5                      0.7591            0.7848           +0.0257 ★
  R@20                     1.0000            1.0000            0.0000 =

★ = improved   ✗ = regressed   = = unchanged
```

### Assessment

The TEI embeddings produce **better overall ranking quality** (nDCG@5
improved by +3.8 percentage points for semantic_only) but **slightly
worse top-1 placement** (MRR@10 regressed by -2.1 points for
semantic_only). This means the TEI model distributes relevant results
more effectively across the top-K positions, but is slightly less
likely to place the single most relevant candidate at position 1.

This is not a clear-cut improvement:
- The nDCG gains are real (+0.038) but modest (both baselines are
  already above 0.93).
- The MRR regression means the user's first result is slightly less
  likely to be the best one.
- The P@5 improvement (+0.026) is driven by better distribution, not
  by finding additional relevant items (R@20 is already 1.0 for both).

### Per-query analysis needed

The aggregate metrics mask per-query behavior. Some queries likely
improved significantly while others regressed. A full per-query
comparison (which the frozen P1B contract requires) would reveal
whether the improvement is systematic or driven by a few favorable
cases.

### Frozen P1B quality gate

The P1B gate required a policy to beat the legacy lexical baseline by
a defensible margin across all metrics. The P1D results:

- **hybrid_rrf TEI nDCG@5 = 0.9734** vs **lexical baseline nDCG@5 = 0.9495**
  → delta +0.0239 (improvement, but small)
- **hybrid_rrf TEI MRR@10 = 0.9924** vs **lexical baseline MRR@10 = 1.0000**
  → delta -0.0076 (regression — the hybrid is WORSE than pure lexical
  on top-1 placement)

The MRR regression means hybrid_rrf with TEI embeddings is WORSE than
the legacy lexical baseline at placing the most relevant result first.
This is the same reason the P1B gate failed.

## Decision

**Outcome B**: TEI with gte-large-en-v1.5 runs reliably but does not
produce a uniformly defensible ranking improvement. The P1 ranking
blocker remains open. P2 remains blocked.

The ranking result suggests the frozen P1B benchmark corpus may not
have enough signal to distinguish between embedding models at this
quality level (all policies score above 0.93 nDCG). The bottleneck may
be the benchmark's discriminative power, not the embedding quality.

## TEI operational value

Despite the mixed ranking result, TEI has **operational value** as a
production embedding service:
- It is the only embedding host on this machine that passed sustained
  operational preflight (243/243, zero crashes).
- It provides deterministic, stable embeddings with good latency.
- It is suitable as the production embedding backend regardless of
  whether the ranking improvement justifies a policy change.

## Recommendations

1. **TEI may be adopted as the production embedding runtime** (replacing
   LM Studio for embeddings) based on its operational stability alone,
   independent of the ranking comparison outcome.

2. **The P1 ranking blocker requires either**:
   a. A more discriminative benchmark corpus that can distinguish
      between embedding models at this quality level, or
   b. A fundamentally different retrieval architecture (e.g. reranker,
      multi-stage retrieval) that goes beyond embedding model selection.

3. **P2 remains blocked** until the ranking quality question is
   resolved.
