# Run #69 → #74 — Complete Pipeline Improvement Results

**Date:** 2026-05-07  
**Same domain, same queries, same strategy (deep_research) across all runs**

---

## Six-Run Evolution

| Metric | #69 (Original) | #70 (Detection) | #71 (Closed-Book) | #74 (Full Fix) |
|:-------|:---------------|:----------------|:------------------|:---------------|
| **Duration** | 38 min | 44 min | 51 min | **35 min** |
| **Quality score** | N/A | 0.75 | 0.80 | **0.80** |
| **Gap recall** | N/A | 37.5% | 50% | **50%** |
| **Gap precision** | N/A | 100% | 100% | **100%** |
| **Idea novelty** | N/A | 100% | 100% | **100%** |
| **Source papers** | 10 | 10 | 10 | **30** (3×) |
| **Abstract density** | 200 chars | 200 chars | 800 chars | **800 chars** |
| **Fabricated citations** | 12 (undetected) | 12 (detected) | 0 | **0** |
| **Sanitized citations** | N/A | 0 | 5 | **6** (2+4) |
| **[SOURCE-X] refs** | 0 | 0 | 49 | **33** (15+18) |
| **Internal reasoning** | 0 | 1 | 5 | **9** (4+5) |
| **Deepening mode** | N/A | Template | Template | **LLM** |
| **Architecture section** | ❌ | Template only | Template only | **✅ LLM-generated** |
| **Toy example** | ❌ | Template only | Template only | **✅ LLM-generated** |
| **Failure modes** | ❌ | Template only | Template only | **✅ LLM-generated** |
| **Success criteria** | ❌ | Template only | Template only | **✅ LLM-generated** |
| **Proposal size** | 74K chars | 74K chars | 76K chars | **92K chars** (+24%) |
| **Cohen's Kappa** | N/A | N/A | N/A | **Computed** |

---

## Four Improvements Applied

### 1. Source Material: 10 → 30 papers (+200%)
- `ctx.all_papers[:10]` → `ctx.all_papers[:30]` in stages.py
- `_format_literature` cap: 15 → 30
- Context cost: ~2K → ~7K tokens (fits in 32K window with room to spare)

### 2. Proposal Depth: Template → LLM-based Deepening
- Wire `PipelineOrchestrator._provider` into `ProposalDeepener`
- Prompt enforces closed-book, no fabrication, concrete examples with real numbers
- Deepened sections (architecture, toy example, failure modes, criteria) merged into proposal.sections
- Result: proposals grow from ~37K → ~46K chars per proposal (+24%)

### 3. Inter-Annotator Agreement
- `InterAnnotatorAgreement` dataclass with Cohen's Kappa
- `GapMatchDetail` per known gap showing match/no-match with scores
- Computed automatically in `_evaluate_pipeline()`

### 4. End-to-End Example
- Deepened content now appears as actual proposal sections in exports
- Full markdown output includes architecture, working example, failure modes, criteria
- 47K + 44K = 91K chars of complete research proposals

---

## Citation Quality Trajectory

| Run | Fabricated | Sanitized | [SOURCE-X] | Internal Reasoning |
|:----|:----------|:----------|:-----------|:-------------------|
| #69 | 12 (hidden) | 0 | 0 | 0 |
| #70 | 12 (detected) | 0 | 0 | 1 |
| #71 | 0 | 5 | 49 | 5 |
| #74 | 0 | 6 | 33 | 9 |

The sanitization gate caught 6 remaining non-corpus citations even with the closed-book prompt — the model still occasionally tries to cite from training data. The layered defense (prompt + sanitization + verification) is working as intended.
