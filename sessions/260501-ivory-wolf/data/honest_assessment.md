# Elephant Rock Platform — Honest Deep Assessment

**Date**: 2026-05-04
**Method**: Live API testing, database queries, code tracing, no guessing.

---

## Rating Scale

| Rating | Meaning |
|--------|---------|
| **A** | Works fully, production-quality |
| **B** | Works, has minor issues |
| **C** | Works partially, significant gaps |
| **D** | Implemented but never actually ran / produced output |
| **F** | Dead code, broken, or cosmetic |

---

## 1. PIPELINE EXECUTION — D

49 runs attempted. Results:

| Status | Count | % |
|--------|-------|---|
| Completed | 11 | 22% |
| Failed | 31 | 63% |
| Stuck "running" | 7 | 14% |

Of the 11 "completed" runs:
- 6 are "AI Empirical Validity" with **0 ideas, 0 gaps, 0 proposals** — they completed without producing anything
- Only **5 runs** actually produced research artifacts
- **31 runs failed** — 15 at `initializing`, 6 at `ingestion`, 5 at `feasibility_scoring`
- **7 runs are stuck in "running"** state forever — the background task died silently

**The pipeline has a ~10% success rate of producing research output.**

---

## 2. IDEAS — B

79 ideas generated. Quality breakdown:

| Metric | Value | Rating |
|--------|-------|--------|
| Score range | 0.50–0.85 (mean 0.74) | B |
| Has novelty report | 76/79 (96%) | A |
| Has feasibility report | 76/79 (96%) | A |
| Has source gap traceability | 79/79 (100%) | A |
| Novelty report has arguments | Yes, 100+ chars each | B |
| Novelty report has closest_matches | **0/79** | F |
| Has mechanical_metrics | **0/79** | F |

**Ideas are well-structured and traceable, but novelty checking never finds closest matches from the vector store, and mechanical metrics were never computed on a real run.**

---

## 3. PROPOSALS — F

37 proposals exist. Every single one:

- **100% have "Synthesis failed. Manual writing required."** as the introduction
- **0/37 have related_work** section
- **0/37 have evaluation_plan** section
- **0/37 have references** section
- **0/37 have risk_mitigation** section
- Average word count: ~170 words (should be 2,000+)
- Average sections: 4 out of 10 required

**The proposal synthesizer was completely broken for all 37 proposals. The fix committed today (free-text generation) has never been tested on a real run.**

---

## 4. RESEARCH GAPS — C+

80 gaps identified. Quality:

| Metric | Value | Rating |
|--------|-------|--------|
| Confidence range | 0.75–0.95 | B |
| Gap types distributed | 4 types (theoretical, methodological, empirical, cross-domain) | B |
| Has canonical_id (dedup) | 80/80 | A |
| User-rated | **0/80** | F |
| Status | All "identified", none progressed | D |

**Truth values are fake**: Every gap has truth_confidence=0.50, evidence_count=1. The OpenNARS-inspired truth value system is cosmetic — it just copies gap confidence to truth_frequency and sets default values for the rest. No actual evidence accumulation happens.

---

## 5. LITERATURE SEARCH — B-

717 papers indexed. Quality:

| Metric | Value | Rating |
|--------|-------|--------|
| Sources | Semantic Scholar (218), OpenAlex (414), arXiv (85) | B |
| Has substantive abstract | 633/717 (88%) | B |
| Has year | 715/717 (99%) | A |
| Has citation count | 589/717 (82%) | B |
| Duplicate titles | **24 duplicates** | C |

Semantic Scholar is rate-limited (429) without API key — works sometimes, fails often.

---

## 6. KNOWLEDGE GRAPH — C+

884 entities, 694 relationships.

| Metric | Value | Rating |
|--------|-------|--------|
| Entity types | paper (642), concept (242) | B |
| Truth values vary | 32 unique frequencies | B |
| Relationship types | **only PROPOSES_METHOD** | F |

**Critical flaw**: 694 relationships and every single one is `PROPOSES_METHOD`. No CITES, USES_METHOD, EXTENDS, CONTRADICTS relationships. The graph is a flat list of paper→concept links, not a real knowledge graph with diverse relationship types.

---

## 7. API LAYER — B-

92 endpoints registered. Live test of 17 endpoints:

| Result | Count |
|--------|-------|
| 200 OK | 12 |
| 422 Validation Error | 1 |
| 404 Not Found | 1 |
| 503 Service Unavailable | 2 |
| Internal Error | 1 |

Broken endpoints:
- `GET /costs/summary` — **NoneType error** (cost tracker not initialized)
- `GET /traces/summary` — 503
- `GET /governance/pending` — 503
- `GET /pipeline/sessions` — 404
- `GET /literature/search` — 422 (parameter name wrong)

---

## 8. COGNITIVE ARCHITECTURE — D

| Subsystem | In Code | In Orchestrator | Ever Ran | Rating |
|-----------|---------|-----------------|----------|--------|
| ConsciousnessStateMachine | Yes | 10 refs | Maybe | C |
| CuriosityDriver | Yes | 10 refs | Maybe | C |
| GoalManager | Yes | 4 refs | Never (no goals data) | D |
| EvolutionEngine | Yes | 4 refs | **Never** (no data dir) | F |
| FaithfulnessChecker | Yes | 6 refs | Maybe | C |
| SandboxManager | Yes | 3 refs | Never (experiment_enabled=false) | D |
| TreeSearchEngine | Yes | 2 refs | **Never** (0 tree_data runs) | F |
| MechanicalMetrics | Yes | Stage registered | **Never** (0 ideas have metrics) | F |
| ImpasseDetector | Yes | **0 refs in orchestrator** | Never | F |
| NegotiationAgent | Yes | **0 refs in orchestrator** | Used in DAG executor only | D |
| MetacognitiveMonitor | Yes | **0 refs in orchestrator** | Never | F |

**The self-improvement engine has never run.** No frontier data, no parameter evolution, no quality ratchet. The directory doesn't even exist.

**Tree search has never run.** Zero runs have tree_data_json. Zero ideas have parent_idea_ids.

**Mechanical metrics have never been computed.** Zero ideas have them.

---

## 9. FRONTEND — B

20 pages, 343 tests pass.

| Aspect | Rating | Notes |
|--------|--------|-------|
| Pages render | A | All 20 pages load |
| Test coverage | B | 72 test files, 343 tests |
| Interaction tests | C | Only 36/72 test files have interaction, rest are render-only |
| Proposal rendering | D | Only fixed today — never tested with real data |
| Real-time updates | C | SSE wired but rarely tested with live runs |
| i18n | B | 9 locales, but only nav/common keys translated |
| Accessibility | C | WCAG audit done, but not verified by real users |

---

## 10. DATABASE — B

10 tables, 5 migrations.

| Table | Populated | Rating |
|-------|-----------|--------|
| papers | 717 rows | B |
| ideas | 79 rows | B |
| proposals | 37 rows (all stubs) | D |
| pipeline_runs | 49 rows | B |
| research_gaps | 80 rows | B |
| experiment_results | **0 rows** | F |
| comments | **0 rows** | F |
| shared_ideas | **0 rows** | F |
| notifications | 71 rows | B |
| users | Depends on auth config | N/A |

---

## 11. TEST QUALITY — C

| Suite | Count | Honest Rating |
|-------|-------|---------------|
| Backend | 1,598 pass | **C** — Many tests mock everything and test that mocks return what they're told |
| Frontend | 343 pass | **C** — 50% are render-only, no real user flows |
| E2E | 1 mock test | **D** — Not a real E2E test |

---

## SUMMARY SCORECARD

| Component | Rating | What's Real |
|-----------|--------|-------------|
| Pipeline execution | **D** | 10% success rate, 7 stuck runs |
| Idea generation | **B** | Good structure, traceable, scored |
| Novelty checking | **C+** | Dimensions + arguments work, but 0 closest matches |
| Feasibility scoring | **B** | 7-dimension reports, real timelines |
| Proposal synthesis | **F** | 37/37 are stubs. Fix committed, untested |
| Gap analysis | **C+** | Good identification, fake truth values |
| Literature search | **B-** | 3 sources work, 24 duplicates, S2 rate-limited |
| Knowledge graph | **C+** | 884 entities, but only 1 relationship type |
| Self-improvement | **F** | Never ran, no data |
| Tree search | **F** | Never ran, 0 tree data |
| Mechanical metrics | **F** | Never computed on real data |
| Experiment execution | **F** | 0 results, experiment_enabled=false |
| API layer | **B-** | 12/17 endpoints work, 5 broken |
| Frontend | **B** | Renders well, interaction coverage thin |
| Test suite | **C** | Pass but many test mocks, not real behavior |
| i18n | **B** | 9 locales for nav keys only |

---

## THE CORE PROBLEM

The platform has **extensive architecture** but **minimal validated output**.

- 67 batches built 699 files and 86,667 LOC
- But only **5 pipeline runs** ever produced research artifacts
- All 37 proposals are broken stubs
- The three headline innovations (tree search, mechanical metrics, self-improvement) have **never produced a single real result**
- The two "research papers" were hand-written by the Lead, not pipeline output

The ratio of **implementation to validation** is severely inverted. Every subsystem was built and tested in isolation with mocks, but the end-to-end pipeline that connects them has a 90% failure rate.
