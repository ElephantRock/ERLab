# P1C Closeout — Stronger Semantic Representation Experiment (Branch D)

> P1C could not be completed. No materially stronger embedding model on the
> available host can complete governed snapshot generation. The experiment
> terminates at Branch D: no practical model candidate is available.

## 1. Status

```
P0          CLOSED
P1A         CLOSED
P1B         CLOSED — genuine negative result
P1C         CLOSED — Branch D (no available stronger model can be evaluated)
P1          OPEN and paused
P2          BLOCKED
Frontend    OPEN and independently actionable
```

P1C is **not** a negative result on the hypothesis (would a stronger
embedding pass the gate?). It is a **host-availability** result: the
hypothesis could not be tested because no candidate model could complete
the governed snapshot generation on the LM Studio host.

## 2. What P1C established (process integrity)

- The experiment was **predeclared and frozen** before any scoring
  (`docs/p1c_experiment_contract.md`): same benchmark, same judgments, same
  frozen quality gate, same ranking policies, new versioned snapshots.
- The candidate set was **frozen before scoring** (§9 of the contract):
  only models that could pass the governed dual_probe were eligible.
- P1B assets were **preserved untouched**: the control snapshot
  (`2d8b26f7…`), the frozen benchmark, the closeout, and the Gate 2
  diagnostic were not modified.
- The generation harness was **generalized** to support multiple tagged
  snapshots (`P1C_SNAPSHOT_TAG` env var) and given **bounded-retry**
  single-text embedding to tolerate transient provider crashes — this is
  tooling robustness, not policy/gate weakening (authority errors still
  abort; only transient provider errors retry).

## 3. Why P1C could not complete

### Candidate availability

The LM Studio host at `http://100.64.0.2:1234` registered 12 embedding
models. A 3-shot stability probe on real benchmark text found **only 2
stable**:

```
text-embedding-qwen3-embedding-0.6b     3/3 stable   1024d   (P1B control)
text-embedding-all-minilm-l12-v2        3/3 stable    384d   (only alternative)
all BGE-M3 / nomic / jina / voyage      0/3 stable          (crash under load)
```

Every "materially stronger" candidate the directive's §5 hoped for
(larger Qwen3, BGE-M3, nomic-v2-moe, jina-v5, voyage-4-nano) **crashes
under sustained load** with segfault exit codes.

### Snapshot generation failure

`text-embedding-all-minilm-l12-v2` (the only non-control stable model)
was registered as the single frozen candidate. Snapshot generation:

- ✅ passed preflight (model loaded, dimension 384)
- ✅ passed the governed dual_probe (`check 3c14eae0…`, `binding 4fb4af72…`)
- ✅ built the `VerifiedEmbeddingRuntime`
- ❌ **crashed during the 336-item embed** — the model returns
  `400: The model has crashed` on real benchmark text after a few items,
  even with bounded retry (8 retries, exponential backoff to ~4 min per
  text). Single short-text probes succeed (8/8), but the actual workload
  triggers crashes.

### Root cause

This is a **host/GGUF stability problem**, not a configuration issue
fixable from the evaluation side. The host's LM Studio exhibits
model-crash/reload loops: models answer a few probes, then segfault under
the real embed workload, then recover, then crash again. Only
`qwen3-embedding-0.6b` (the P1B control) reliably sustains the full
workload.

A bake-off run on this host would produce results that depend on **when**
the run executed, not on model quality — which would invalidate any
pass/fail conclusion. The honest action is to not run it.

## 4. Branch D evidence

Per the P1C decision tree:

```
Branch A — stronger embedding passes          not testable (no snapshot)
Branch B — semantic improves, RRF fails       not testable (no snapshot)
Branch C — stronger embeddings still fail     not testable (no snapshot)
Branch D — no practical model candidate       FIRES
```

Branch D fires: no practical model candidate is available **on this host**.
This is narrower than "no stronger model exists anywhere" — it is "no
stronger model can be evaluated under governance in the current
environment."

## 5. What was NOT done (integrity accounting)

```
benchmark changes                 0  (P1B frozen benchmark untouched)
judgment changes                  0  (P1B frozen judgments untouched)
threshold changes                 0  (P1B frozen gate unchanged)
P1B snapshot overwrites           0  (control snapshot 2d8b26f7… untouched)
production changes                0  (no policy activated, TrimmerStage unchanged)
reranker built                    0
successful new snapshots          0  (all-minilm generation crashed)
gate verdicts on new candidates   0  (no snapshot -> no evaluation)
```

## 6. Re-evaluation conditions for P1C

P1C (testing the stronger-embedding hypothesis) should be retried only when
**a candidate model can reliably complete the governed snapshot generation**.
Concretely:

```
the host's LM Studio stability is repaired (models stop crashing under
    sustained load), OR
a different governed embedding endpoint is configured (a real OpenAI key
    with text-embedding-3-large, a stable Ollama serving bge-m3, a hosted
    Voyage/Cohere endpoint, etc.), OR
the operator loads a specific stronger model and confirms it sustains the
    full 336-item embed workload before P1C is reopened
```

The generalized harness (`P1C_SNAPSHOT_TAG`) and bounded-retry logic make
re-running cheap once a stable candidate exists. The frozen experiment
contract means re-running does not require re-freezing the gate,
benchmark, or policies.

## 7. Resulting posture

```
legacy_lexical_top20_v1     remains production-authoritative (unchanged since P1B)
hybrid_rrf_v1               not activated (P1B verdict stands)
P1B                         CLOSED (genuine negative result; preserved)
P1C                         CLOSED (Branch D; host availability)
P1                          OPEN and paused
P2                          BLOCKED
Frontend                    OPEN and independently actionable
```

## 8. Recommended next move

Per the P1C directive's Branch D: **keep P1 paused and redirect engineering
effort to the independent frontend track** (TS baseline, 101 errors) rather
than beginning P2 or building a reranker. The ranking roadmap is not
blocked on engineering effort — it is blocked on (a) the host providing a
stable stronger embedding model, or (b) a decision to procure/configure a
different governed embedding endpoint.

When either precondition is met, P1C can be reopened as a new versioned
experiment without re-doing P1B's work.

## 9. Artifacts added by P1C

```
docs/p1c_experiment_contract.md     frozen experiment contract (P1C.0)
docs/p1c_closeout.md                this file
docs/p1c_closeout.json              machine-readable closeout
backend/ranking/generate_embedding_snapshot.py
    + P1C_SNAPSHOT_TAG env (multiple tagged snapshots)
    + SnapshotGenerationFailure (closed failure-code vocabulary)
    + _embed_one_with_retry (bounded single-text retry for host instability)
backend/tests/test_ranking/test_snapshot_retry_boundaries.py
    16 tests pinning the six retry boundaries
```

No new benchmark, snapshot, evaluation, or production code beyond the
contract and the generation-harness robustness improvements.

## 10. Retry-tooling boundary preservation (qualification 2026-07-21)

The generalized snapshot harness and its retry logic are qualified by
16 tests in `test_snapshot_retry_boundaries.py`. The six frozen boundaries:

```
authority or binding failure    → fail immediately, no retry
                                  (CODE_AUTHORITY_FAILURE; CapabilityAuthorizationError
                                   detected by TYPE, not message string)
transient provider failure      → bounded retry (max 8, exp backoff to 30s)
                                  (signatures: 'model has crashed', 'model reloaded',
                                   'no models loaded', 'connection reset', 502/503)
candidate snapshot failure      → no partial snapshot promoted as valid
                                  (write_snapshot writes both files together after
                                   all items succeed; a mid-flight failure leaves
                                   no snapshot.json in the output dir)
retry exhaustion                → explicit SnapshotGenerationFailure(RETRY_EXHAUSTED)
                                  with per-item attempt count and terminal code
control snapshot                → never overwritten
                                  (write_snapshot refuses overwrite;
                                   P1C_SNAPSHOT_TAG routes candidates to
                                   docs/p1c_snapshots/<tag>/, never docs/p1b_snapshot/)
retry policy                    → experiment-harness ONLY
                                  (lives in generate_embedding_snapshot.py;
                                   production VerifiedEmbeddingRuntime and
                                   GovernedEmbeddingAdapter do NOT import or call it)
```

Per-item attempt counts and terminal failure codes are recorded on every
`SnapshotGenerationFailure` so a repeatedly-crashing provider cannot appear
merely slow. The closed failure-code vocabulary is:

```
authority_failure         governance abort (no retry)
retry_exhausted           transient failures persisted > max_retries
non_transient_provider    provider error not classified transient (401/404/...)
empty_vector              provider returned zero vectors
```

Non-transient provider errors (401 unauthorized, 404 not found, invalid
api key, real 400 with a non-crash body) are terminal — they do not retry.
This prevents the harness from silently retrying past a real configuration
or auth problem.
