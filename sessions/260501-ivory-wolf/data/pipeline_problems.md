# Pipeline Problems — Found by Running the Code

Every finding below is from live execution, not code reading.

---

## PROBLEM 1: Vector Store Embedding Dimension Mismatch

**Severity: CRITICAL — breaks novelty checking permanently**

```
chromadb.errors.InvalidArgumentError: Collection expecting embedding 
with dimension of 1536, got 384
```

The ChromaDB collection `research_papers` was created with 1536-dimension embeddings (OpenAI `text-embedding-ada-002`). But the orchestrator's `EmbeddingService` is configured to use whatever the current provider offers — which is a local 384-dimension model (`all-MiniLM-L6-v2`).

**Result**: The vector store has 323 records that cannot be queried. When the novelty checker calls `store.query()`, it crashes. This is why **0 out of 79 ideas have closest_matches**. The novelty checker falls through to the "No similar papers found" path and returns a default 0.8 score with an empty matches list.

**Every novelty score in the database is a default value, not a real measurement.**

---

## PROBLEM 2: Proposal Synthesizer Produces Stubs

**Severity: CRITICAL — 100% of proposals are broken**

All 37 proposals in the database:
- Introduction says "Synthesis failed. Manual writing required."
- 0/37 have related_work, evaluation_plan, references, or risk_mitigation sections
- Average word count: ~170 (should be 2,000+)
- Average sections: 4 out of 10

**Root cause**: The old synthesizer used `structured_output()` with a JSON schema that only required 4 fields. The LLM filled those 4 minimally and skipped the rest. The quality gate minimums (50 words for abstract, 100 for intro) were too low to catch the stubs.

**Status**: Fix committed today (switched to free-text generation with 10 required sections and minimum word counts). But the fix has **never been tested on a real pipeline run**.

---

## PROBLEM 3: Knowledge Graph Only Has 1 Relationship Type

**Severity: HIGH — graph is a flat list, not a graph**

884 entities, 694 relationships. Every single relationship is `PROPOSES_METHOD`. The code defines 5 relationship types:

```python
class RelationType(str, Enum):
    CITES = "cites"           # never used
    USES_METHOD = "uses_method" # never used
    EXTENDS = "extends"         # never used
    CONTRADICTS = "contradicts" # never used
    PROPOSES_METHOD = "proposes_method"  # 694 uses
```

**Root cause**: In `stages.py`, both `IdeaGenerationStage` and `GapAnalysisStage` only create `PROPOSES_METHOD` relationships (gap→idea). No code ever creates CITES, USES_METHOD, EXTENDS, or CONTRADICTS relationships. Papers don't cite each other. Methods don't extend prior work. Nothing contradicts anything.

The graph is a two-column table: `[gap] → PROPOSES_METHOD → [idea]`. That's not a knowledge graph.

---

## PROBLEM 4: Truth Values Are Cosmetic

**Severity: HIGH — claimed OpenNARS integration is fake**

All 80 research gaps have:
- `truth_confidence = 0.50` (every single one)
- `truth_evidence_count = 1` (every single one)
- `truth_frequency = gap.confidence` (just copied)

The knowledge graph entities have varying truth values because they're computed with `TruthValue.from_observation()` which does apply the OpenNARS formula. But gap truth values in the database are set directly in `gap_analyzer.py` — they're just `TruthValue(frequency=gap.confidence, confidence=0.6)` with no evidence accumulation.

**No truth value was ever revised. No evidence was ever merged.** The `TruthValue.revise()` method exists but is never called anywhere in the pipeline.

---

## PROBLEM 5: Tree Search Has Never Run

**Severity: HIGH — headline feature never activated**

```
Runs with tree_data: 0
Ideas with parent_idea_ids: 0
```

Tree search is gated behind `tree_of_thought_enabled` config flag, which defaults to `False`. No pipeline run ever set it to `True`. The `TreeSearchStage` code exists but has never executed on real data.

---

## PROBLEM 6: Mechanical Metrics Have Never Been Computed

**Severity: HIGH — headline feature never activated**

```
Ideas with mechanical_metrics: 0/79
```

The `MechanicalMetricsStage` is registered in the pipeline but the metrics are stored inside `novelty_report.mechanical_metrics`. The stage runs but the novelty report is populated *before* mechanical metrics are computed, and the metrics result never gets written back into the already-persisted idea.

---

## PROBLEM 7: Self-Improvement Has Never Triggered

**Severity: HIGH — headline feature never activated**

```
Self-improve dir exists: False
```

The `EvolutionEngine` requires a `self_improve_persist_dir` directory to exist. It has never been created. No parameter evolution has occurred. No Pareto frontier has been built. No fitness scores have been computed. The "quality ratchet" is code that has never run.

---

## PROBLEM 8: Pipeline Success Rate Is 10%

**Severity: CRITICAL — 90% of runs fail or produce nothing**

49 runs:
- 15 failed at `initializing` (likely LLM provider setup failures)
- 6 failed at `ingestion`
- 5 failed at `feasibility_scoring` (LLM timeout/format errors)
- 2 failed at `proposal_synthesis`
- 7 stuck in `running` forever (background task died, status never updated)
- 6 "completed" with 0 ideas, 0 gaps (empty runs)

Only 5 runs produced ideas. And all 5 produced only stub proposals.

---

## PROBLEM 9: 7 Runs Stuck in "Running" Forever

**Severity: HIGH — runs marked running that will never complete**

Runs 43-49 have status="running" but the background tasks have died. The status is never set to "failed" because the error handling doesn't update the DB when the background task crashes silently.

---

## PROBLEM 10: Semantic Scholar Rate Limited

**Severity: MEDIUM — one of three literature sources often fails**

```
Semantic Scholar rate-limited (429), retry 1/5 in 2.2s
Semantic Scholar rate-limited (429), retry 2/5 in 4.0s  
Semantic Scholar rate-limited (429), retry 3/5 in 8.2s
```

Without an API key, Semantic Scholar returns 429 after a few requests. The retry logic works but adds 15+ seconds per query. In the live test, only 5 papers came from S2 (the other 5 from OpenAlex). ArXiv failed entirely with an empty error.

---

## PROBLEM 11: 24 Duplicate Papers in the Database

**Severity: MEDIUM — deduplication is incomplete**

717 papers in DB, but only 693 unique titles. 24 duplicates exist because the dedup logic uses `paper.id` but different sources assign different IDs to the same paper. A paper indexed as `semantic_scholar:1234` and `openalex:W5678` won't be deduplicated despite having the same title.

---

## PROBLEM 12: 5 API Endpoints Broken

**Severity: MEDIUM — user-visible failures**

| Endpoint | Error |
|----------|-------|
| `GET /costs/summary` | `NoneType has no attribute 'summary'` — cost tracker not initialized |
| `GET /traces/summary` | 503 — trace service not configured |
| `GET /governance/pending` | 503 — governance not configured |
| `GET /pipeline/sessions` | 404 — session route mismatch |
| `GET /literature/search` | 422 — parameter name wrong (`query` vs `q`) |

---

## PROBLEM 13: Tests Don't Test the Pipeline

**Severity: HIGH — test reports are misleading**

1,944 tests pass. But:
- Every LLM call is mocked — no test ever sends a real prompt to a real LLM
- Every database call is mocked — no test ever queries real data
- No test runs the pipeline end-to-end with real services
- Tests prove code compiles and mock contracts hold
- Tests prove nothing about whether the pipeline works

The test suite is structured to pass, not to find problems.
