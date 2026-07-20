# P1B Execution Contract — Ranking Evaluation, Production Activation, and Evidence

## Entry state
- Commit: `914af0a`
- Alembic head: `030`
- Tests collected: 4559
- Working tree: clean

## Status
- P0: CLOSED (governance foundation complete)
- P1A: CLOSED (audit, benchmark infrastructure, contracts, baseline, RRF, evaluation)
- P1B: READY (semantic evaluation, reranking, production activation)
- P1: OPEN
- P2: BLOCKED by P1 closure

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
