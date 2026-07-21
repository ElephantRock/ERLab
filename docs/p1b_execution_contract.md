# P1B Execution Contract — Ranking Evaluation, Production Activation, and Evidence

## Entry state
- Commit: `914af0a`
- Alembic head: `030`
- Tests collected: 4559
- Working tree: clean

## Status
- P0: CLOSED (governance foundation complete)
- P1A: CLOSED (audit, benchmark infrastructure, contracts, baseline, RRF, evaluation)
- P1B: CLOSED at Gate 2 — evaluation complete; no candidate policy passed the frozen quality gate; legacy remains authoritative (see docs/p1b_closeout.md)
- P1: OPEN — quality objective unmet
- P2: BLOCKED by P1

P1B.4+ (reranker, production selection, durable evidence, TrimmerStage
replacement, operator commands, production seal) was NEVER STARTED. Any
future ranking work requires a new versioned experiment and new evidence
capable of changing the result; it must not overwrite the frozen benchmark,
judgments, snapshot, or this negative result.

## 1. Production ranking surfaces (from P1.0 audit)

### Primary: TrimmerStage (discovery ranking)
- **File**: `backend/pipeline/dag/trimmer.py:38-132`
- **Current behavior**: keyword-overlap heuristic on domain string → sort → `[:20]`
- **Configured reranker**: NEVER WIRED (`_orchestrator.py:682` — no `reranker=` kwarg)
- **Impact**: Every downstream stage sees only 20 papers in keyword-overlap order
- **P1B target**: Replace with approved ranking policy

### Secondary: SearchService deduplication
- **File**: `backend/pipeline/literature/search_service.py`
- **Current behavior**: Source-priority deduplication (S2 > PubMed > OpenAlex > CrossRef > arXiv)
- **RelevanceFilter**: INACTIVE in production (no embedding provider passed)
- **PubMed/CrossRef**: Emit constant `relevance_score=1.0`
- **P1B target**: Wire relevance-aware ordering

### Secondary: TwoStageRetriever (retrieval ranking)
- **File**: `backend/pipeline/knowledge/retriever.py:42-234`
- **Current behavior**: Parallel BM25 + semantic → RRF fusion → optional reranker → `[:n_results]`
- **Problem**: Scores never persisted. No durable evidence.
- **P1B target**: Persist ranking evidence through ranking contracts

## 2. Current benchmark identity and limitations

- **Version**: `discovery_ranking_v1+retrieval_ranking_v1`
- **Cases**: 9 discovery + 3 retrieval = 12 total
- **Domains**: machine_learning, biomedical, nlp
- **Rubric**: `research_utility_0_to_3_v1` (0=irrelevant, 3=highly useful)
- **Splits**: calibration, development, held_out
- **Judgments**: Single-annotator synthetic
- **Limitation**: Too small for broad quality claims. Must expand before policy selection.

## 3. Benchmark expansion requirements (P1B.1)

Minimum targets:
```
discovery cases     ≥ 30
retrieval cases     ≥ 30
domains             ≥ 3
```

Required adversarial slice types:
```
lexical traps (high overlap, grade 0)
semantic paraphrases (low overlap, high relevance)
method vs application papers
review vs primary study
missing abstracts
near-duplicates
source-rank conflicts
acronym vs expanded term
negated/contradictory findings
exact identifier queries
```

Annotation requirements:
```
annotation provenance recorded
judgment confidence recorded
split assignment frozen after tuning begins
benchmark fingerprint recomputed
```

## 4. Held-out split rules

- Held-out set frozen before candidate-policy tuning begins
- No policy weights tuned on held-out data
- Held-out results reported only once, after policy selection
- Thresholds frozen before viewing held-out results

## 5. Quality acceptance thresholds (freeze before viewing results)

Recommended default gate (may be adjusted before evaluation, not after):
```
macro nDCG@10 improvement       ≥ 0.03 absolute vs legacy
paired bootstrap lower bound    > 0
Recall@20 change                no worse than -0.01
critical benchmark slices       no decline > 0.05
deterministic replay            100%
score-trace completeness        100%
latency                         within configured P1 budget
```

A policy that improves average while harming a critical domain must not be activated without explicit disposition.

## 6. Governed semantic scoring requirements (P1B.2)

All semantic scores must use:
```
EffectiveEmbeddingConfiguration
→ VerifiedEmbeddingRuntime
→ authorized query/document embeddings
→ exact capability binding evidence
```

Invariants:
```
query and candidate binding mismatch    0
unverified semantic scoring             0
cross-binding comparisons               0
silent missing-score substitution       0
```

For benchmark reproducibility: persist or deterministically regenerate semantic-score inputs under an exact binding and check posture.

## 7. Reranker integration contract (P1B.4)

```
hybrid top-M candidates
→ configured reranker
→ exact candidate-aligned scores
→ final ranking
```

Reranker must never:
- introduce candidates
- drop IDs silently
- return duplicate IDs
- change eligibility

Failure policy (closed vocabulary):
```
fail_ranking
use_hybrid_fallback
return_partial_failure
```

Must be configured, benchmarked, and persisted.

## 8. Durable ranking evidence requirements (P1B.5)

Use next actual Alembic revision (verify head first — likely 031).

Create:
```
ranking_executions
ranking_execution_candidates
```

Fields per spec §10. Link exactly to:
```
PaperDiscovery or governed dedup candidate record (discovery)
VectorRetrievalEvent + eligible snapshot (retrieval)
P0.5 configuration snapshot
```

Records must be immutable after completion. No secret values persisted.

## 9. TrimmerStage replacement requirements (P1B.6)

Production flow after replacement:
```
full governed candidate population
→ configured candidate_limit
→ lexical and semantic feature extraction
→ approved ranking policy
→ optional reranker (configured top-M)
→ final configured limit
```

The legacy policy remains available as explicit rollback but must not be implicit fallback.

For excluded candidates:
```
PaperDiscovery provenance remains intact
ranking disposition recorded
corpus exclusion auditable
```

## 10. Production and adversarial zero-count gates

```
hidden lexical top-20 truncation before approved ranking     0
production candidates outside upstream set                    0
retrieval results outside eligible snapshot                   0
cross-binding semantic scoring                                0
accepted reranker setting without production effect           0
silent ranking fallback                                       0
ranking execution without configuration snapshot              0
selected result without component-score evidence              0
nonfinite persisted scores                                    0
nondeterministic replay mismatches                            0
unresolved adversarial defects                                0
```

## 11. Stop conditions

1. Current lexical truncation occurs before candidate population can be durably identified
2. Reliable benchmark judgments cannot be produced
3. Candidate text insufficient for reproducible relevance assessment
4. Discovery and retrieval ranking require incompatible meanings for same setting
5. Semantic ranking cannot use one verified capability binding
6. Reranker cannot return exact candidate-aligned evidence
7. No candidate policy meets frozen quality gate
8. Material improvement requires generating new queries (→ P2)
9. Material improvement requires additional search rounds (→ P3)
10. A ranking feature requires unsupported/misleading quality proxies

If stop condition 7 fires: legacy policy remains explicitly active, P1 stays open, thresholds not weakened.

## 12. Five-run closeout requirements

After production seal:
```
independent adversarial review
repair all confirmed defects
five consecutive full backend gates
skip accounting
clean-tree verification
P1 closeout update (docs/p1_closeout.md + .json)
```

## Fresh-session execution order

```
P1B.0  Freeze execution contract (this document)
P1B.1  Expand and adjudicate benchmark
P1B.2  Generate governed semantic scores
P1B.3  Evaluate candidate policies (legacy vs semantic-only vs hybrid RRF vs reranked)
P1B.4  Integrate and evaluate bounded reranker
P1B.5  Select or reject production policy
P1B.6  Add durable ranking evidence (migration + DB tables)
P1B.7  Replace TrimmerStage and wire retrieval ranking
P1B.8  Add operator inspection commands
P1B.9  Production seal, adversarial review, five-run closeout
```

## 13. Authorization (recorded before implementation)

### Scope authorized

```
P1B.1  benchmark expansion + blind adjudication   AUTHORIZED
P1B.2  governed real-embedding snapshot             AUTHORIZED after judgment/split freeze (Gate 1)
P1B.3  frozen policy evaluation                     AUTHORIZED after snapshot verification
P1B.4+                                                  NOT YET AUTHORIZED
```

P2 remains BLOCKED. P1 stays OPEN. No production policy is selected in this scope.

### Decision 1 — Embeddings: C. Cached real embeddings

The official quality benchmark must use real-provider embeddings generated once through
`EffectiveEmbeddingConfiguration → VerifiedEmbeddingRuntime → authorized embeddings → immutable snapshot`.
Every policy comparison runs against the frozen snapshot.

Frozen definition of "deterministic replay":

> Given the same benchmark definition, relevance judgments, configuration, ranking policy,
> and embedding-snapshot fingerprint, ranking outputs and evaluation metrics must be exactly
> reproducible. It does NOT mean repeated external-provider calls return byte-identical vectors.

Required snapshot contents:

```
snapshot schema version
benchmark version and fingerprint
capability binding ID
generation capability-check ID
provider/model/deployment evidence
embedding contract version
dimension and numeric representation
normalization posture
query IDs and canonical text hashes
candidate IDs and canonical text hashes
exact query vectors
exact candidate vectors
per-vector fingerprints
complete snapshot fingerprint
created timestamp
```

Replay must FAIL (not silently regenerate) when any of:

```
candidate text hash differs
query text hash differs
binding evidence differs
dimension differs
normalization contract differs
vector artifact fingerprint differs
benchmark fingerprint differs
```

A deterministic governed stub embedder is retained ONLY for infrastructure tests
(integration, binding-equality, snapshot writer/reader, failure injection, architecture).
It is marked: `benchmark infrastructure fixture`, `not eligible for ranking-quality approval`,
`not production-selectable`.

A separate optional command may regenerate a candidate snapshot under a new real binding;
it creates a new snapshot version and new evaluation and must not overwrite the approved snapshot.

### Decision 2 — Reranker: C. Defer conditionally

Evaluate first, in order:

```
legacy_lexical_top20_v1
semantic_only_v1
hybrid_rrf_v1
hybrid_weighted_v1   (only if weights frozen without held-out tuning)
```

- If `hybrid_rrf_v1` passes the frozen gate: production candidate policy = `hybrid_rrf_v1`,
  `reranker_policy = none`, `reranker_enabled = false`. The disabled reranker control must be
  truthfully dispositioned (reranker construction calls 0, reranker requests 0, persisted records
  record `reranker_policy = none`). Disabling has an observable, tested effect: no reranker execution.
- If `hybrid_rrf_v1` fails: STOP after P1B.3 for design review. Do NOT auto-build a learned MLP
  (≈60 cases is too small to train/validate without overfitting). The follow-on decision would
  evaluate an existing production cross-encoder, an existing ERLab scoring model, an external
  reranker provider, an LLM reranker, or revised non-learned feature fusion. Any reranker receives
  its own frozen quality/latency/cost/failure-policy/reproducibility contract.

The P1 threshold must not be weakened merely to avoid implementing a reranker.

### Decision 3 — Judgments: A, with blinded adjudication

Sequence:

```
author benchmark cases
→ author provisional judgments
→ freeze candidate pools
→ freeze provisional split assignment
→ produce unlabeled adjudication package
→ independent second-pass annotation
→ compare judgments
→ adjudicate disagreements
→ freeze final judgments and splits
→ compute final benchmark fingerprint
→ begin semantic evaluation
```

The blind adjudication pass receives candidate cases WITHOUT exposing:
`original relevance grade`, `original confidence`, `policy scores`, `policy ranks`,
`baseline ranks where avoidable`.

Each judgment artifact preserves:

```
case ID
candidate ID
primary relevance grade 0–3
annotation confidence
brief criterion-based rationale
annotation provenance
initial annotation
second-pass annotation
adjudicated annotation
disagreement status
```

Quality floor for the expanded benchmark:

```
discovery cases                 ≥ 30
retrieval cases                 ≥ 30
domains                         ≥ 3
adversarial slice types         all required slices represented
double-annotated cases          preferably 100% for this expansion
unresolved judgment conflicts   0
```

Closeout must describe the benchmark honestly as
`controlled expert-reviewed benchmark`, NOT `population-level human relevance ground truth`.
Where neither annotation can justify a grade reliably, mark the case for exclusion or external
review rather than forcing a judgment.

### Decision 4 — Scope: B. P1B.1–P1B.3 only, with mandatory gates

Will execute: P1B.1, P1B.2, P1B.3.
Will NOT execute until reviewed: reranker implementation, production policy selection,
DB ranking evidence, TrimmerStage replacement, operator commands, production activation.

**Gate 1 — after P1B.1.** Pause with: expanded benchmark cases, candidate-pool fingerprints,
provisional judgments, blind-adjudication package, split assignments, slice coverage report.
Judgments and held-out split must be approved before generating official benchmark scores.

**Gate 2 — after P1B.3.** Pause with: legacy baseline metrics, semantic-only metrics, hybrid RRF
metrics, weighted-policy metrics (where applicable), paired confidence intervals, domain and intent
slices, adversarial-slice results, latency, snapshot and replay evidence, quality-gate verdict.
No production policy is selected merely because it has the highest point estimate.
