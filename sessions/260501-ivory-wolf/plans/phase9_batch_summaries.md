# Phase 9 Batch Summaries — B122 through B130

## BATCH-122: Claim Storage & Query Layer
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 2 new + 1 mod

**Goal:** Persist extracted claims in SQLite and make them queryable via a ClaimStore service. Add `claims` table to the database with columns matching the Claim dataclass schema. Create a ClaimStore class with methods: `store_claims(paper_id, claims)`, `get_claims(paper_id)`, `find_similar_claims(claim, top_k)`, `get_claims_by_type(claim_type)`. Wire vector embeddings for semantic claim search.

**Strategic Bet:** Claims indexed at scale enable cross-paper discovery. The vector embedding of claim descriptions makes semantic search fast.

**Key Decisions:**
- Claims table uses claim_id as primary key, source_paper_id as FK
- Claim embeddings use the same 768-dim model as papers
- ClaimStore is a standalone service, not wired into orchestrator yet

---

## BATCH-123: Wiki Generation Service
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 2 new

**Goal:** Create a WikiGenerator that produces a structured 30-field JSON wiki entry from paper text. The wiki schema covers: one_line_summary, problem_statement, method, key_insights, experiments, limitations, future_work, connections, code_and_resources, tags, novelty_assessment. Include a WikiVerifier that cross-checks wiki claims against source text and flags unsupported claims.

**Strategic Bet:** LLM can produce accurate structured summaries when given explicit JSON schema + verification pass.

**Key Decisions:**
- WikiGenerator uses structured_output with explicit JSON schema
- WikiVerifier checks each factual claim against source text
- Wiki stored as JSON in wiki_entries table (not individual columns)

---

## BATCH-124: Curation Rules Engine
**Cycle:** STANDARD | **Tests:** +6 | **Files:** 2 new

**Goal:** Create a CurationEngine that applies user-defined rules to filter and rank papers. Rules support: must_include (author, keyword, venue), must_exclude (keyword), semantic_threshold (cosine similarity to research statement), max_papers_per_day. Rules stored as JSON in config. Engine returns scored + ranked paper list.

**Strategic Bet:** Explicit rules + semantic filtering = personalized paper feed that doesn't miss important work.

**Key Decisions:**
- Rules loaded from config file (not database, for simplicity)
- Semantic similarity uses existing embedding infrastructure
- LLM relevance scoring is optional (can be slow)

---

## BATCH-125: Contradiction Detector
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 2 new

**Goal:** Create a ContradictionDetector that finds conflicting claims across papers. Query claims with same metric + dataset + method_name but different values. For each candidate pair, use LLM to verify genuine contradiction vs. legitimate variation (different settings, different versions). Return scored contradiction gaps.

**Strategic Bet:** Cross-paper claim matching reveals genuine scientific disagreements that humans would miss.

**Key Decisions:**
- Uses ClaimStore from B122 for efficient queries
- LLM verification step prevents false positives
- Contradictions stored as a new gap_type in research_gaps table

---

## BATCH-126: Method-Problem Gap Matrix
**Cycle:** STANDARD | **Tests:** +6 | **Files:** 2 new

**Goal:** Create a MethodProblemDetector that builds a method×problem applicability matrix. For each known method (from METHOD claims) and each known dataset/problem (from RESULT claims), check if the method has been applied to that problem. If not, use LLM to assess applicability. Score the gap by potential impact + feasibility.

**Strategic Bet:** Most method→problem transfer gaps are discoverable via structured queries, not just LLM intuition.

**Key Decisions:**
- Existing method-problem pairs extracted from RESULT claims
- Applicability assessment uses LLM with structured prompt
- Gaps sorted by (applicability_score × method_novelty × problem_importance)

---

## BATCH-127: Study Design with MVP
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 2 new

**Goal:** Extend the existing EvaluationPlanGenerator into a full StudyDesigner that produces: hypothesis (main + null + mechanistic rationale), experimental design (variables, controls, sample size), experiment list with code skeletons, MVP experiment with go/no-go criteria, risk assessment, publication strategy, timeline. Wire into the pipeline as a post-idea-generation stage.

**Strategic Bet:** Structured study designs with MVP experiments make gaps immediately actionable.

**Key Decisions:**
- Builds on existing EvaluationPlanGenerator (template mode)
- MVP experiment includes pseudocode + expected runtime
- Go/no-go criteria are explicit and measurable

---

## BATCH-128: Daily Auto-Ingestion Scheduler
**Cycle:** STANDARD | **Tests:** +5 | **Files:** 2 new

**Goal:** Create a SchedulerService that runs daily: fetch arXiv papers → apply curation rules → download PDFs → extract text → generate wiki → extract claims → update knowledge graph. Runs as a background task triggered by FastAPI startup or external cron. Tracks last-run timestamp to avoid re-processing.

**Strategic Bet:** Always-current library is essential for gap detection freshness.

**Key Decisions:**
- Uses APScheduler or simple asyncio loop for scheduling
- Configurable interval (default: 24h)
- Each run logs papers processed, claims extracted, errors encountered

---

## BATCH-129: Cross-Paper Connection Agent
**Cycle:** STANDARD | **Tests:** +6 | **Files:** 2 new

**Goal:** Create a ConnectionAgent that finds non-obvious relationships between papers. For each paper, search its claims against all other papers' claims. Classify connections as: builds_on (extends prior work), contradicts (challenges findings), complements (orthogonal approach). Store connections in knowledge graph as typed edges.

**Strategic Bet:** Automated connection finding surfaces research opportunities that manual reading would miss.

**Key Decisions:**
- Uses vector similarity on claim embeddings for candidate finding
- LLM classifies connection depth (trivial vs. deep)
- Connections added to existing knowledge graph (backend/pipeline/knowledge/graph.py)

---

## BATCH-130: Phase 9 Close + STATE.md Update
**Cycle:** SIMPLIFIED | **Tests:** +0 | **Files:** 0 new

**Goal:** Run all Phase 9 tests (B121-B129, ~60 new tests). Verify all new modules importable. Update STATE.md with Phase 9 module map. Write completion report. Commit final state.

**Strategic Bet:** Clean close ensures no regressions and accurate state for next phase.

**Key Decisions:**
- SIMPLIFIED cycle: 1 Task (validation only), no source modifications
- STATE.md updated with all Phase 9 modules
- Completion report covers all 10 batches
