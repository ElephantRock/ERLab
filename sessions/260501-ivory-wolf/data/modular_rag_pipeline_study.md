# Modular RAG Research Pipeline Study
## Elephant Rock Gap Analysis & Adoption Plan

**Date**: 2026-05-12
**Source**: User-provided architecture brief — 4 modular pipeline concepts
**Scope**: Compare each concept against Elephant Rock's actual codebase, identify honest gaps, propose native adoptions

---

## Executive Summary

The brief describes a **retrieval-augmented generation (RAG) research pipeline** with 4 pillars: modular architecture, auto-evaluation, context optimization, and synthetic benchmarks. Elephant Rock is **not a RAG pipeline** — it is a research automation platform that discovers gaps, generates ideas, and synthesizes proposals. However, 3 of the 4 concepts have direct applicability with significant gaps to close.

**Honest verdict:**

| Concept | Elephant Rock Status | Gap Severity | Adoption Priority |
|:--------|:---------------------|:-------------|:------------------|
| 1. Modular Plug-and-Play | **85% exists** — ABCs, Protocol classes, strategy presets, model routing | LOW | P2 — Polish, not build |
| 2. Auto-Evaluation Tracker | **30% exists** — PipelineEvaluator + gold standards, but NO retrieval metrics, NO LLM-as-judge loop | **HIGH** | **P0** |
| 3. Context Window Optimization | **40% exists** — BudgetTracker + per-stage timeouts, but NO dynamic chunk trimming | **HIGH** | **P1** |
| 4. Synthetic Evaluation Dataset | **15% exists** — ExperimentGenerator generates code, but NOT ground-truth retrieval benchmarks | **CRITICAL** | **P0** |

---

## Concept 1: The Modular "Plug-and-Play" Architecture

### What the brief says
- Abstract Python classes (Protocols / ABCs) for every component
- Unified `config.yaml` controlling pipeline state
- Switch between retrieval strategies by changing one string
- Enables ablation studies for paper methodology sections

### What Elephant Rock already has

**Abstract base classes (strong):**
```
backend/pipeline/stages.py          → PipelineStage(ABC) with execute()
backend/pipeline/knowledge/embedding_providers.py → EmbeddingProvider(ABC)
backend/pipeline/knowledge/reranker.py            → Reranker(ABC) with LLMReranker, CrossEncoderReranker
backend/pipeline/literature/base.py               → AcademicSearchSource(ABC)
backend/pipeline/governance/guardrails.py         → Guardrail(ABC)
backend/pipeline/knowledge/query_transform.py     → QueryTransformer(ABC)
backend/pipeline/evaluation/scorer.py             → Scorer(ABC)
backend/pipeline/sandboxing/protocol.py           → SandboxBackend(Protocol), SandboxSession(ABC)
```

**Structural subtyping (Protocol) — already used:**
```python
# mechanical_metrics.py — 5 Protocol classes for structural typing
class _HasProposedMethod(Protocol):
    proposed_method: str
class _HasSupportingPapers(Protocol):
    supporting_paper_count: int
# ... etc.

# tree_search.py — Protocol for scoring and ideation
class IdeaScorer(Protocol):
    async def score(self, idea, papers): ...
class Ideator(Protocol):
    async def generate(self, ctx, gaps): ...
```

**Strategy presets — config-driven switching:**
```python
# strategies/presets.py — 4 presets controlling all 16 stages
# Switch from fast_scan to deep_research by changing strategy string
PipelineStrategy.FAST_SCAN     → 7 stages enabled, 9 skipped
PipelineStrategy.DEEP_RESEARCH → all 16 stages enabled
PipelineStrategy.ACADEMIC_PROPOSAL → all 16 + paper_synthesis
PipelineStrategy.LITERATURE_REVIEW → 6 stages only
```

**Model routing — per-stage provider override:**
```python
# StageContext.provider_override — swaps LLM provider per stage
# Per-stage model selector UI — Local/Cloud/Auto buttons for each stage
# Gap analysis → local LM Studio; Proposal synthesis → cloud glm-5.1
```

### What's missing

| Gap | Severity | Details |
|:----|:---------|:--------|
| No `config.yaml` file | LOW | Config is env-var driven (`EROCK_*` prefix) + strategy presets. Works but not declarative file-based |
| No ablation study runner | MEDIUM | No way to run "with vs without reranker" automatically and compare results side-by-side |
| No component versioning | LOW | Can't pin "use reranker v1 vs v2" for experiments |

### Adoption Recommendations

**A-01: Ablation Study Runner** (P2, ~4 hours)
- New module: `backend/pipeline/experiment/ablation.py`
- Accepts a baseline strategy + list of component exclusions
- Runs pipeline N times, each time disabling one component
- Produces comparison report: "Without reranker: -12% gap recall"
- Uses existing `StageConfig(enabled=False)` pattern

**A-02: Experiment Manifest** (P3, ~2 hours)
- YAML/JSON file that declares: strategy, excluded stages, model overrides, domain
- `POST /api/v1/experiments/ablation` endpoint
- Stores results in `experiments` table with variant labels

---

## Concept 2: Auto-Evaluation Tracker (The "Judge" Loop)

### What the brief says
- Automated evaluation engine running parallel to generation
- Tracking database logging: Hit Rate, MRR, nDCG@K
- LLM-as-judge for Faithfulness and Answer Relevance
- Auto-generates precision-recall curves

### What Elephant Rock already has

**PipelineEvaluator** — structural quality metrics:
```python
# verification/pipeline_evaluator.py
PipelineEvaluationReport:
  - gap_precision: float    # novel / detected
  - gap_recall: float       # detected_known / total_known
  - idea_novelty_rate: float
  - inter_annotator: InterAnnotatorAgreement  # Cohen's Kappa
```

**Gold-standard gap lists** — for recall computation:
```python
# verification/gold_standards.py
GOLD_STANDARD_GAPS = {
    "AI/NLP": [8 known gaps],
    "AI/Reasoning": [8 known gaps],
    "Biomedical": [8 known gaps],
    "Computer Science": [8 known gaps],
}
```

**FeedbackCollector** — sliding window for trend detection:
```python
# adaptation/feedback.py
RunFeedback: avg_idea_score, avg_novelty_score, token_usage, elapsed_seconds
FeedbackCollector.detect_plateau() — checks if metric stopped improving
```

**CostTracker** — per-stage token and cost tracking:
```python
# monitoring/cost_tracker.py
TokenUsage → model, input_tokens, output_tokens, stage
CostReport → total_cost_usd, by_stage, by_model
```

### What's missing (CRITICAL GAPS)

| Gap | Severity | Details |
|:----|:---------|:--------|
| **NO retrieval metrics** | **CRITICAL** | No Hit Rate, MRR, nDCG@K for literature search quality. We search 36 papers but never measure if the RIGHT papers were found |
| **NO LLM-as-judge loop** | **HIGH** | No automated faithfulness or relevance scoring after proposal synthesis. Quality assessment is manual |
| **NO metrics persistence** | **HIGH** | PipelineEvaluator computes metrics but they're not stored in DB. Lost after each run |
| **NO precision-recall curves** | **MEDIUM** | No visualization of retrieval quality over time |
| **NO per-stage metrics dashboard** | **MEDIUM** | Can't see "literature_search achieved 72% hit rate, gap_analysis found 4/8 gold gaps" |

### Adoption Recommendations

**B-01: Retrieval Metrics Module** (P0, ~6 hours)
- New: `backend/pipeline/evaluation/retrieval_metrics.py`
- Computes after literature_search + ingestion stages:
  - **Hit Rate**: Fraction of queries returning ≥1 relevant result
  - **MRR** (Mean Reciprocal Rank): Average position of first relevant result
  - **nDCG@K**: Normalized Discounted Cumulative Gain at K=10
- Gold-standard paper lists per domain (like gold_standards.py but for papers)
- Stored in new `retrieval_metrics` column on pipeline_runs table

**B-02: LLM-as-Judge Faithfulness Scorer** (P0, ~4 hours)
- New: `backend/pipeline/evaluation/faithfulness_scorer.py`
- After proposal_synthesis: LLM rates each claim against source papers
- Scores: `faithfulness` (0-1), `relevance` (0-1), `grounding` (0-1)
- Uses local LM Studio (qwen3-4b) for cost-free judging
- Results stored in `evaluation_metrics` JSON column

**B-03: Metrics Persistence + API** (P1, ~3 hours)
- New DB table: `pipeline_metrics` (run_id, stage, metric_name, metric_value, timestamp)
- API: `GET /api/v1/pipeline/runs/{id}/metrics`
- Frontend: Metrics tab on run-detail page

**B-04: Metrics Dashboard** (P2, ~4 hours)
- Frontend page showing retrieval quality trends across runs
- Charts: hit rate over time, MRR by strategy, nDCG comparison

---

## Concept 3: Context Window Optimization Engine

### What the brief says
- Token-budgeting layer between Reranker and LLM generation
- Automated trimmer using tiktoken
- Dynamic chunk dropping when exceeding VRAM budget (e.g., 4000 tokens)
- Guarantees stability during massive multi-hour evaluation loops

### What Elephant Rock already has

**BudgetTracker** — token counting with thresholds:
```python
# autonomy/budget.py
BudgetTracker(max_tokens=500000)
  .record(stage, tokens, cost, elapsed)
  .check() → CONTINUE / REPLAN / STOP
  # Replan at 80% budget, STOP at 100%
```

**Per-stage timeouts** — prevents infinite hangs:
```python
# config.py
stage_default_timeout: float = 1800.0  # 30 minutes
stage_timeouts: dict = {}              # per-stage overrides
```

**Reranker** — already sorts by relevance:
```python
# knowledge/reranker.py
class Reranker(ABC):
    async def rerank(query, documents, top_k) → list[ScoredDocument]
```

### What's missing (SIGNIFICANT GAPS)

| Gap | Severity | Details |
|:----|:---------|:--------|
| **NO token counting before LLM calls** | **CRITICAL** | BudgetTracker counts AFTER calls. No pre-flight check to prevent OOM |
| **NO dynamic chunk trimming** | **HIGH** | Reranker returns top-K but doesn't check total token count. 10 chunks × 800 chars = could exceed 4K token budget |
| **NO tokenizer integration** | **HIGH** | No tiktoken or model-native tokenizer. Token counts are estimated, not precise |
| **NO context window awareness** | **MEDIUM** | Provider doesn't know model's max context. Could send 8K tokens to a 4K model |

### Adoption Recommendations

**C-01: Token Budget Guard** (P1, ~4 hours)
- New: `backend/pipeline/knowledge/token_budget.py`
- Uses `tiktoken` for precise token counting
- Sits between reranker and LLM consumer stages
- Algorithm:
  1. Reranker returns N scored chunks
  2. TokenBudget counts total tokens
  3. If exceeds budget: drop lowest-scoring chunks until within limit
  4. Log: "Trimmed 10→7 chunks (5200→3800 tokens) for gap_analysis stage"
- Config: `token_budget_per_stage: {"gap_analysis": 4000, "idea_generation": 6000, ...}`

**C-02: Context Window Registry** (P1, ~2 hours)
- Extend `config.py` with model context sizes (we have `MODEL_CONTEXT_SIZES` reference data)
- Provider wrapper checks: `if token_count > model.max_context: trigger trimming`
- Prevents all OOM errors on RTX 3080 Ti

**C-03: Pre-flight Token Check** (P2, ~2 hours)
- Before each LLM call: count tokens in messages
- If approaching limit: warn and auto-trim
- Log token usage patterns for optimization

---

## Concept 4: Synthetic Evaluation Dataset Generator

### What the brief says
- Ground-truth dataset: Queries + Context Chunks + Expected Answers
- LLM generates research questions from corpus paragraphs
- "Act as a world-class scientist. Generate 3 highly specific research questions explicitly answered by this text."
- Provides zero-cost benchmarking for retrieval metrics

### What Elephant Rock already has

**ExperimentGenerator** — generates experiment code:
```python
# experiment/experiment_generator.py
# Generates Python scripts with synthetic test datasets
# But NOT retrieval evaluation benchmarks
```

**ClaimExtractor** — extracts claims from papers:
```python
# claims/extractor.py
# Extracts: claim_text, claim_type, supporting_evidence, baseline_method
# Could be adapted for question generation
```

**DocumentParser** — parses PDF/TXT/CSV/MD/DOCX:
```python
# ingestion/document_parser.py
parse_and_chunk() → list[DocumentChunk]
```

### What's missing (CRITICAL GAP)

| Gap | Severity | Details |
|:----|:---------|:--------|
| **NO question generation from corpus** | **CRITICAL** | Can't auto-generate "what questions does this paper answer?" |
| **NO ground-truth dataset format** | **CRITICAL** | No schema for (query, relevant_doc_ids, expected_answer) triples |
| **NO retrieval benchmark runner** | **HIGH** | No way to evaluate "did literature search find the papers that answer these questions?" |
| **NO automated benchmark loop** | **HIGH** | Can't run "generate questions → search → measure MRR" automatically |

### Adoption Recommendations

**D-01: Synthetic Benchmark Generator** (P0, ~6 hours)
- New: `backend/pipeline/evaluation/benchmark_generator.py`
- Input: list of papers (from any pipeline run)
- Process: For each paper abstract, use LM Studio LLM to generate:
  - 3 specific research questions answerable by the paper
  - Expected answer summary (1-2 sentences)
- Output: `BenchmarkDataset` — list of `(question, paper_id, answer)` triples
- Store in new `benchmarks` table

**D-02: Retrieval Benchmark Runner** (P0, ~4 hours)
- New: `backend/pipeline/evaluation/retrieval_benchmark.py`
- Takes a `BenchmarkDataset` and runs literature search
- Measures: Did search find the correct paper? At what rank?
- Computes: Hit Rate, MRR@10, nDCG@10
- Compares across strategies: "fast_scan achieves 62% hit rate, deep_research achieves 84%"

**D-03: Domain-Specific Gold Datasets** (P1, ~3 hours)
- Generate benchmark datasets for our 4 gold-standard domains
- Store as JSON files in `backend/pipeline/evaluation/benchmarks/`
- Auto-loaded when running evaluation on matching domain
- Provides instant, reproducible retrieval quality baseline

---

## Consolidated Adoption Roadmap

### Tier 1 — Critical (P0, ~20 hours)

| ID | Task | New Modules | Hours |
|:---|:-----|:------------|:------|
| D-01 | Synthetic Benchmark Generator | `evaluation/benchmark_generator.py` | 6h |
| D-02 | Retrieval Benchmark Runner | `evaluation/retrieval_benchmark.py` | 4h |
| B-01 | Retrieval Metrics (MRR/nDCG) | `evaluation/retrieval_metrics.py` | 6h |
| B-02 | LLM-as-Judge Faithfulness | `evaluation/faithfulness_scorer.py` | 4h |

### Tier 2 — Important (P1, ~15 hours)

| ID | Task | New Modules | Hours |
|:---|:-----|:------------|:------|
| C-01 | Token Budget Guard | `knowledge/token_budget.py` | 4h |
| C-02 | Context Window Registry | config extension | 2h |
| B-03 | Metrics Persistence + API | DB table + API route | 3h |
| D-03 | Domain Gold Datasets | benchmark JSON files | 3h |
| A-01 | Ablation Study Runner | `experiment/ablation.py` | 3h |

### Tier 3 — Polish (P2, ~10 hours)

| ID | Task | New Modules | Hours |
|:---|:-----|:------------|:------|
| B-04 | Metrics Dashboard | Frontend page | 4h |
| C-03 | Pre-flight Token Check | provider wrapper | 2h |
| A-02 | Experiment Manifest | YAML config | 2h |
| — | Integration tests | ~20 new tests | 2h |

---

## Architecture Comparison

```
THE BRIEF'S PIPELINE:                    ELEPHANT ROCK:
─────────────────────                    ──────────────
Ingestion → Stage 1                     Literature Search (multi-source)
Retrieval  → Stage 1                    Ingestion + Embedding + VectorStore
Reranking  → Stage 2                    Reranker(ABC) — LLMReranker / CrossEncoder
Generation → Stage 3                    Gap Analysis → Idea Gen → Proposal Synthesis

MISSING IN ELEPHANT ROCK:
  ✗ Token budget between reranker and generation
  ✗ Retrieval metrics (MRR, nDCG, Hit Rate)
  ✗ LLM-as-judge automated quality scoring
  ✗ Synthetic benchmark generation
  ✗ Ablation study automation

ALREADY STRONG IN ELEPHANT ROCK:
  ✓ ABC/Protocol-based modularity (12+ abstract classes)
  ✓ Strategy presets (4 strategies, single-string switching)
  ✓ Per-stage model routing (local/cloud/auto per stage)
  ✓ Budget tracking with CONTINUE/REPLAN/STOP
  ✓ Gold-standard gap lists with Cohen's Kappa
  ✓ Feedback loop with plateau detection
  ✓ Cost tracking per stage and model
```

---

## Key Insight

The brief describes a **RAG evaluation infrastructure** that Elephant Rock has never built. Our pipeline discovers gaps and generates proposals — the "research" part — but we never rigorously evaluate the **retrieval quality** of our literature search or the **faithfulness** of our generated proposals.

This is the single biggest architectural gap in the platform. We have 124 pipeline runs, 1,683 papers, 131 ideas — but we **cannot answer**:
- "Are we finding the RIGHT papers?" (No retrieval metrics)
- "Are our proposals grounded in the papers we found?" (No faithfulness scoring)
- "How does fast_scan compare to deep_research on retrieval quality?" (No benchmark dataset)

The 4 concepts in this brief would transform Elephant Rock from "generates research output" to "generates research output with quantified quality guarantees."

---

## Recommended Next Step

Execute **Tier 1 (D-01 → D-02 → B-01 → B-02)** as a 4-batch AIV v5.3 sequence:

- **BATCH-RAG-01**: Synthetic Benchmark Generator + Benchmark Runner
- **BATCH-RAG-02**: Retrieval Metrics Module (MRR/nDCG/Hit Rate)
- **BATCH-RAG-03**: LLM-as-Judge Faithfulness Scorer
- **BATCH-RAG-04**: Metrics Persistence + Integration Test + Run Evaluation

This produces a **quantified quality baseline** for the platform. After these 4 batches, every future pipeline run will automatically log retrieval quality, proposal faithfulness, and benchmark scores.
