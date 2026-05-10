# Phase 10 Master Roadmap — Master Adoption Catalog (55 Features)

**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-11  
**Framework:** AIV v5.3  
**Scope:** 41 remaining features from Master Adoption Catalog (14 already built)  
**Source:** `master_adoption_catalog.md` — 55 features from 20+ competitive studies  
**Test Baseline:** 2,480 (as of BATCH-150)

---

## Batch Sequence Overview

```
BATCH-151 ─── Docker Deployment & Production Hardening
BATCH-152 ─── Cross-Model Adversarial Review
BATCH-153 ─── Full Paper Synthesis (LaTeX Output)
BATCH-154 ─── Citation & Claim Audit (3-Axis)
BATCH-155 ─── Search Engine Expansion (Semantic Scholar + PubMed)
BATCH-156 ─── Multi-Dimensional Proposal Evaluation
BATCH-157 ─── Iterative Reflection Loop
BATCH-158 ─── Knowledge Library Persistence (Cross-Run Memory)
BATCH-159 ─── 5-State Verification + Staged Confidence Deepening
BATCH-160 ─── Local Document Ingestion
BATCH-161 ─── Recursive Deep Research (Tree Exploration)
BATCH-162 ─── Research Journal & AI Honesty Labeling
BATCH-163 ─── Semantic Scholar Novelty Verification
BATCH-164 ─── Planning Agent & Adaptive Pipeline
BATCH-165 ─── Self-Improving Prompts (TextGrad)
BATCH-166 ─── Idea Recombination Engine
BATCH-167 ─── Error Analysis, Guard Commands & Plateau Detection
BATCH-168 ─── MCP Server Completion & External Integration
BATCH-169 ─── Domain-Specific Prompts & Budget/Time Controls
BATCH-170 ─── Citation Graph Visualization & Frontend Polish
BATCH-171 ─── Internal Alpha — Full E2E Verification
```

---

## Batch Goals & Strategic Bets

### BATCH-151: Docker Deployment & Production Hardening
**Cycle:** STANDARD  
**Goal:** One-command `docker compose up` starts backend + frontend + SQLite. Production-ready.  
**Strategic Bet:** If we can't ship a one-command install, nothing else matters. This unblocks sharing.  
**Features:** #6 (Docker deploy), #45 (AI honesty labeling)  
**Tasks:** 4 · **Tests:** +16 · **Effort:** ~7h

### BATCH-152: Cross-Model Adversarial Review
**Cycle:** STANDARD  
**Goal:** Completed proposals are routed through a different model family for adversarial scoring with revision loop.  
**Strategic Bet:** ARIS's #1 innovation. If this works, proposal quality jumps measurably.  
**Features:** #1 (Adversarial review), #35 (Judge-ML dual agent)  
**Tasks:** 3 · **Tests:** +14 · **Effort:** ~8h

### BATCH-153: Full Paper Synthesis (LaTeX Output)
**Cycle:** STANDARD  
**Goal:** Convert proposals into publication-ready LaTeX papers with BibTeX, figures, tables.  
**Strategic Bet:** Academic researchers need LaTeX, not Markdown. This makes proposals publishable.  
**Features:** #2 (LaTeX paper), #37 (venue templates)  
**Tasks:** 4 · **Tests:** +18 · **Effort:** ~14h

### BATCH-154: Citation & Claim Audit (3-Axis)
**Cycle:** STANDARD  
**Goal:** Post-processing stage verifies every citation (existence + metadata + context) and every quantitative claim against source papers.  
**Strategic Bet:** Goes beyond [SOURCE-X] indexing to actual correctness verification.  
**Features:** #3 (citation audit), #4 (claim audit)  
**Tasks:** 3 · **Tests:** +14 · **Effort:** ~8h

### BATCH-155: Search Engine Expansion
**Cycle:** STANDARD  
**Goal:** Add Semantic Scholar, PubMed, CrossRef as search sources. Parallel fan-out.  
**Strategic Bet:** 2 engines → 5+ engines. Coverage directly impacts gap quality.  
**Features:** #16 (more engines), #17 (relevance filter)  
**Tasks:** 4 · **Tests:** +16 · **Effort:** ~10h

### BATCH-156: Multi-Dimensional Proposal Evaluation
**Cycle:** STANDARD  
**Goal:** Score proposals on 5 dimensions (Novelty, Feasibility, Completeness, Rigor, Clarity) with radar chart frontend.  
**Strategic Bet:** A single score tells user nothing. 5 dimensions = actionable feedback.  
**Features:** #10 (multi-dim eval)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~6h

### BATCH-157: Iterative Reflection Loop
**Cycle:** STANDARD  
**Goal:** After gap analysis and ideation, LLM evaluates its own output. If score < threshold, regenerate with feedback. Max 2 retries.  
**Strategic Bet:** Every competitor iterates. Single-pass produces mediocre results.  
**Features:** #9 (reflection loop)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~7h

### BATCH-158: Knowledge Library Persistence
**Cycle:** STANDARD  
**Goal:** Every paper, gap, idea from every run is indexed persistently. Future runs query library first.  
**Strategic Bet:** Currently each run starts from scratch. Run #2 doesn't know Run #1 existed. This is insane for a research tool.  
**Features:** #15 (knowledge library)  
**Tasks:** 3 · **Tests:** +14 · **Effort:** ~8h

### BATCH-159: 5-State Verification + Staged Confidence Deepening
**Cycle:** STANDARD  
**Goal:** Replace binary supported/unsupported with 5 states. Add progressive trust tiers with downstream gates.  
**Strategic Bet:** Nuanced verification + trust gates prevent low-trust claims from poisoning downstream.  
**Features:** #11 (5-state verification), #12 (staged confidence), #31 (temporal decay)  
**Tasks:** 3 · **Tests:** +14 · **Effort:** ~7h

### BATCH-160: Local Document Ingestion
**Cycle:** STANDARD  
**Goal:** Users upload PDFs/Word/CSV. Parsed content feeds into ingestion stage as supplementary sources.  
**Strategic Bet:** GPT Researcher's unique capability. Researchers want to include their own papers.  
**Features:** #7 (local docs)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~7h

### BATCH-161: Recursive Deep Research
**Cycle:** STANDARD  
**Goal:** Start with broad query, recursively search citing/cited papers via OpenAlex API. Configurable breadth × depth.  
**Strategic Bet:** Flat keyword search misses foundational papers. Recursive citation traversal finds them.  
**Features:** #8 (recursive search)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~8h

### BATCH-162: Research Journal & AI Honesty Labeling
**Cycle:** STANDARD  
**Goal:** Every pipeline run produces a narrative `notes.md` + clean `README.md` summary. AI-generated badge on all exports.  
**Strategic Bet:** simonw's methodology: question → investigate → note → report → archive. Pipeline runs should be research investigations.  
**Features:** #14 (research journal), #45 (honesty labeling — if not done in B151)  
**Tasks:** 3 · **Tests:** +10 · **Effort:** ~5h

### BATCH-163: Semantic Scholar Novelty Verification
**Cycle:** STANDARD  
**Goal:** For each idea, iteratively search Semantic Scholar up to 10 rounds. LLM decides if prior art invalidates the idea.  
**Strategic Bet:** Current novelty check is vector-store only. S2 adds web-verified novelty.  
**Features:** #36 (S2 novelty)  
**Tasks:** 2 · **Tests:** +10 · **Effort:** ~5h

### BATCH-164: Planning Agent & Adaptive Pipeline
**Cycle:** STANDARD  
**Goal:** Planning agent decides which stages to run based on research question complexity. Re-plans mid-run.  
**Strategic Bet:** Makes pipeline adaptive. Simple questions get 3 stages, complex get all 10.  
**Features:** #20 (planning agent)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~8h

### BATCH-165: Self-Improving Prompts (TextGrad)
**Cycle:** STANDARD  
**Goal:** After each run, evaluate prompt quality. Generate prompt improvements via textual gradient descent. A/B test.  
**Strategic Bet:** SkyworkAI's core innovation. Self-improving pipeline. Unique differentiator.  
**Features:** #21 (TextGrad)  
**Tasks:** 3 · **Tests:** +14 · **Effort:** ~10h

### BATCH-166: Idea Recombination Engine
**Cycle:** STANDARD  
**Goal:** Systematically take top idea pairs and generate recombinations. Score each. Google showed 44% beat both parents.  
**Strategic Bet:** Proven by Google. Breakthrough discovery rate is highest with recombination.  
**Features:** #22 (recombination)  
**Tasks:** 2 · **Tests:** +10 · **Effort:** ~5h

### BATCH-167: Error Analysis, Guard Commands & Plateau Detection
**Cycle:** STANDARD  
**Goal:** Store rejection reasons. Guard secondary metrics during optimization. Detect plateaus.  
**Strategic Bet:** Autoresearch's modify→verify→keep loop. Pipeline learns from failures.  
**Features:** #24 (error analysis), #28 (budget controls), #43 (plateau detection), #44 (guard commands)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~7h

### BATCH-168: MCP Server Completion & External Integration
**Cycle:** STANDARD  
**Goal:** Complete MCP server. Register pipeline tools. Expose to external AI systems.  
**Strategic Bet:** Makes Elephant Rock a tool within other AI workflows, not just standalone.  
**Features:** #26 (MCP server), #39 (Overleaf — partial)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~8h

### BATCH-169: Domain-Specific Prompts & Budget/Time Controls
**Cycle:** STANDARD  
**Goal:** Expand from 3 to 6+ domain prompt files. User-configurable budget and time limits with graceful degradation.  
**Strategic Bet:** Generic prompts = generic output. Domain specialization = higher quality.  
**Features:** #27 (domain prompts), #28 (budget controls)  
**Tasks:** 3 · **Tests:** +12 · **Effort:** ~7h

### BATCH-170: Citation Graph Visualization & Frontend Polish
**Cycle:** STANDARD  
**Goal:** Interactive citation graph. Cross-model consensus wiring. Adversarial verification two-pass. Provenance tracking.  
**Strategic Bet:** Knowledge graph exists but is abstract. Citation graph is what researchers want to see.  
**Features:** #13 (cross-model consensus), #29 (citation graph), #32 (adversarial verification), #33 (provenance)  
**Tasks:** 4 · **Tests:** +16 · **Effort:** ~14h

### BATCH-171: Internal Alpha — Full E2E Verification
**Cycle:** STANDARD  
**Goal:** Start platform. Run 3 real pipelines. Verify all 170+ features work together. Zero P0 bugs required for sign-off.  
**Strategic Bet:** Everything above is theory until live-tested. This batch is the reality check.  
**Features:** Integration verification of all 41 features  
**Tasks:** 3 · **Tests:** +20 · **Effort:** ~8h

---

## Summary Statistics

| Metric | Value |
|:-------|:------|
| **Total Batches** | 21 (B151–B171) |
| **Total Tasks** | ~63 |
| **Total New Tests** | ~260 |
| **Total Effort** | ~182h |
| **Expected Test Baseline at Completion** | ~2,740 |
| **P0 Features Covered** | All 3 (adversarial review, Docker, LaTeX paper) |
| **P1 Features Covered** | All 11 |
| **P2 Features Covered** | 14 of 18 (4 deferred to Phase 11) |
| **P3 Features Deferred** | All 9 (R&D dual agent, BFTS, OR-Tools, rebuttal, monitoring, Overleaf, PWA, i18n pipeline, news) |

---

*Roadmap complete. 21 batches covering 41 features. 3 P0 + 11 P1 + 14 P2. BATCH-151 specimen follows.*
