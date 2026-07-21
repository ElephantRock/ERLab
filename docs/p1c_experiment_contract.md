# P1C Experiment Contract — Stronger Semantic Representation Experiment

> A materially stronger governed embedding model may create enough relevance
> separation for semantic or hybrid ranking to pass the existing frozen gate.

P1C is a **bounded evaluation wave**, not a full production macro-wave. It
reuses the P1B infrastructure (frozen benchmark, blind-adjudicated
judgments, immutable candidate pools, governed snapshot format, semantic
evaluation harness, bootstrap CIs, slice diagnostics) and tests the single
hypothesis that representation quality was the P1B bottleneck.

## 1. Entry state

```
HEAD                       540de0c  (P1B closeout)
P0                         CLOSED
P1A                        CLOSED
P1B                        CLOSED — genuine negative result
P1                         OPEN and paused
P2                         BLOCKED
Frontend                   OPEN and independently actionable
```

## 2. Preservation rules (P1B is immutable)

P1C MUST NOT modify:

```
benchmark cases                       (discovery_ranking_v2+retrieval_ranking_v2)
judgments                             (frozen, blind-adjudicated)
splits                                (calibration / development / held_out)
acceptance thresholds                 (the frozen P1B gate)
P1B embedding snapshot                (fingerprint 2d8b26f7…)
P1B evaluation results                (docs/p1b_gate2/*)
Gate 2 diagnostic                     (docs/p1b_gate2/diagnostic_analysis.*)
P1B negative-result closeout          (docs/p1b_closeout.*)
```

P1C is a **new experiment** layered on the same benchmark:

```
benchmark version        unchanged
judgments                unchanged
experiment version       new (p1c_v1)
embedding snapshots      new (one per frozen candidate model)
policy evaluations       new (re-runs against each new snapshot)
```

The P1B qwen3-embedding-0.6b snapshot remains the **control**. New
candidates are compared against it on the same frozen benchmark.

## 3. Frozen quality gate (UNCHANGED from P1B)

```
macro nDCG@10 improvement       ≥ 0.03 absolute vs legacy
paired bootstrap lower bound    > 0
Recall@20 degradation           no worse than -0.01
critical-slice degradation      no worse than -0.05
deterministic snapshot replay   100%
score-trace completeness        100%
```

No threshold changes after results are visible. The gate that P1B failed
is the gate P1C must pass.

## 4. Frozen ranking policies (UNCHANGED from P1B)

Initially evaluate only:

```
legacy_lexical_top20_v1    (fixed baseline; identical across all snapshots
                            because it does not consume embeddings)
semantic_only_v1           (cosine similarity from each snapshot)
hybrid_rrf_v1              (RRF fusion, rrf_k=60 — frozen)
```

RRF k is NOT tuned. Weights are NOT introduced. This isolates the causal
question: **did the stronger embedding representation improve ranking?**

## 5. Candidate embedding models (frozen BEFORE scoring)

The candidate set is predeclared and frozen before any snapshot is
generated. Recommended categories (per the P1C directive):

```
current baseline model            qwen3-embedding-0.6b (1024d) — CONTROL
larger model from same family     (e.g. a larger Qwen3-embedding)
one independent high-quality      (e.g. BGE-M3 stable variant, nomic-v2,
embedding architecture             jina-v5, or voyage-4-nano if loadable)
```

The actual frozen set is recorded in §9 after P1C.1 probes availability.
Do **not** test an open-ended sequence of models until one happens to
pass — that is multiple-testing and invalidates the gate.

Each candidate must pass the existing P0.4 governed path:

```
EffectiveEmbeddingConfiguration
→ run_capability_check (governed dual_probe, PASSED)
→ embedding_capability_binding (immutable)
→ build_verified_embedding_runtime (fail-closed)
→ embed_*_authorized (receipts with binding evidence)
→ immutable benchmark snapshot (self-fingerprinting)
```

A model that cannot pass the governed dual_probe (crashes, wrong
dimension, no binding) is **excluded** — it is not a valid candidate.

## 6. Representation diagnostics (per snapshot)

For each embedding snapshot, report (extending the P1B Section 5 analysis):

```
grade-3 vs grade-2 mean cosine separation     (the P1B bottleneck: was 0.05)
grade-3 vs grade-0 mean cosine separation     (trap separation)
overall similarity ↔ grade rank correlation   (P1B was 0.514)
lexical-trap rejection rate                   (P1B was 4/4)
semantic-paraphrase recovery rate             (P1B was 3/4)
exact-identifier behavior                     (where semantic hurt P1B)
missing-abstract degradation                  (title-only reliability)
domain-specific rank correlation              (ml / biomedical / nlp)
discovery vs retrieval performance            (per-surface)
```

The central result identifies whether a stronger model improves the
**relevance geometry**, not merely the final aggregate metric.

## 7. Decision tree (P1C.5)

```
Branch A — A stronger embedding passes the frozen gate
    → authorize P1D-Production Ranking Activation
      (durable DB evidence, TrimmerStage replacement, retrieval wiring,
       operator commands, production seal, five-run gate). No reranker.

Branch B — Semantic-only improves materially but RRF still fails
    → authorize P1D-Deterministic Fusion Design
      (calibrated weighted / intent-aware / exact-identifier protection /
       semantic override for traps). Weights frozen before held-out.

Branch C — Stronger embeddings still fail
    → authorize P1D-Candidate-Aligned Reranker Contract
      (cross-encoder or query–candidate interaction model with its own
       frozen quality / latency / cost / failure-policy / reproducibility
       contract).

Branch D — No practical model candidate is available
    → keep P1 paused; redirect engineering to the frontend track.
```

## 8. Sequence

```
P1C.0  Freeze experiment contract (this document)
P1C.1  Probe candidate model availability + stability; freeze candidate set
P1C.2  Generate immutable embedding snapshots (one per frozen candidate)
P1C.3  Run unchanged semantic_only_v1 + hybrid_rrf_v1 + legacy baseline
P1C.4  Compare quality, CIs, and representation diagnostics
P1C.5  Select Branch A / B / C / D
```

## 9. Frozen candidate set

Probed at P1C.1 by requesting 3 real-benchmark-text embeddings from every
model registered on the LM Studio host (`http://100.64.0.2:1234`):

```
model                                       stability   dim    role
text-embedding-qwen3-embedding-0.6b         3/3         1024   CONTROL (P1B)
text-embedding-all-minilm-l12-v2            3/3         384    candidate
bortunac/text-embedding-bge-m3-embeddings   0/3         —      EXCLUDED (crashes)
forrint/text-embedding-bge-m3-embeddings    0/3         —      EXCLUDED (crashes)
text-embedding-nomic-embed-text-v2-moe      0/3         —      EXCLUDED (crashes)
jina-embeddings-v5-text-small-retrieval     0/3         —      EXCLUDED (crashes)
text-embedding-nomic-embed-text-v1.5        0/3         —      EXCLUDED (crashes)
voyage-4-nano                               0/3         —      EXCLUDED (crashes)
```

The host's LM Studio can currently serve only **two** embedding models
reliably. The "materially stronger" candidates the directive's §5 hoped
for (larger Qwen3, BGE-M3, nomic-v2, jina-v5, voyage-4-nano) **cannot
pass the governed dual_probe** — they crash under sustained load with
segfault exit codes. This is a host/GGUF stability problem, not a
configuration issue fixable from the evaluation side.

Frozen candidate set (1 candidate + 1 control):

```
CONTROL     text-embedding-qwen3-embedding-0.6b   1024d   (P1B snapshot 2d8b26f7…)
CANDIDATE   text-embedding-all-minilm-l12-v2      384d    (independent architecture)
```

Honest pre-registration: `all-minilm-l12-v2` is **smaller** than the
control (384d vs 1024d) and predates it by years. It is registered as a
candidate only because (a) it is the only other stable model on the host
and (b) it is an *independent architecture* (one of the directive's three
categories). The expectation is that it will likely **not** beat the
control — but testing it provides a clean data point and preserves the
experimental discipline (test the hypothesis with what is actually
available rather than weakening the gate or skipping the experiment).

If `all-minilm-l12-v2` also fails (expected), P1C reaches **Branch D**:
no materially stronger practical model candidate is available, P1 stays
paused, and the next move is either to wait for the host's stronger
models to be repaired or redirect engineering to the frontend track.

## 10. Stop conditions (inherited from P1B §11)

P1C stops if:
- no candidate model can pass the governed dual_probe
- the benchmark cannot distinguish candidates (all produce identical
  rankings — would indicate the benchmark is degenerate, not just hard)
- a candidate requires unrecorded fallback or non-governed embedding

## 11. Parallel work

The frontend track (TS baseline, 101 errors) is independent of P1/P2 and
may proceed in parallel. P1C does not block it and is not blocked by it.
